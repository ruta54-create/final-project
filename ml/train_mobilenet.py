"""Train the waste classifier (MobileNetV2) on a normal laptop CPU and export it for the ESP32.

    ml\\.venv\\Scripts\\python ml\\train_mobilenet.py                 # 128x128, alpha 0.35 (default, best for ESP32-S3)
    ml\\.venv\\Scripts\\python ml\\train_mobilenet.py --size 96       # faster on a classic ESP32-CAM, less accurate

Designed for: Intel Core i5 (2 cores), 8 GB RAM, no GPU  ->  about 15 minutes (128) or 7 minutes (96).

Pipeline
  1. images from ml/datasets/processed (made by prepare_dataset.py)
  2. MobileNetV2 alpha=0.35, ImageNet weights (transfer learning)
       phase 1: train only the new classifier head (base frozen)
       phase 2: fine-tune the top of MobileNetV2 with a small learning rate
  3. test on images never seen in training: accuracy, confusion matrix, per class + per compartment
  4. full-integer (int8) quantisation -> model_int8.tflite (~0.6 MB) -> test it again
  5. outputs in ml/output/: model_int8.tflite, model_data.h, labels.txt, metrics.json, *.png, MODEL_CARD.md

Deploy: upload model_int8.tflite to Edge Impulse ("Bring your own model") -> Arduino library -> esp32_cam.ino.
"""

import argparse
import json
import os
import time
from pathlib import Path

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
import numpy as np  # noqa: E402
import tensorflow as tf  # noqa: E402

keras = tf.keras
ROOT = Path(__file__).resolve().parent
DATA = ROOT / "datasets" / "processed"
OUT = ROOT / "output"
ORDER = ["organic", "paper", "plastic", "metal", "background"]
BIN_OF = {"organic": "organic", "paper": "organic", "plastic": "inorganic", "metal": "inorganic", "background": "none"}


def datasets(size, batch, seed):
    classes = [c for c in ORDER if (DATA / "train" / c).is_dir()]
    common = dict(labels="inferred", label_mode="int", class_names=classes, image_size=(size, size),
                  batch_size=batch, interpolation="bilinear")
    train = keras.utils.image_dataset_from_directory(DATA / "train", validation_split=0.15, subset="training",
                                                     seed=seed, shuffle=True, **common)
    val = keras.utils.image_dataset_from_directory(DATA / "train", validation_split=0.15, subset="validation",
                                                   seed=seed, shuffle=True, **common)
    test = keras.utils.image_dataset_from_directory(DATA / "test", shuffle=False, **common)
    return classes, train, val, test


def augmenter():
    """Variations the camera will really see: position, rotation, distance, light."""
    return keras.Sequential([
        keras.layers.RandomFlip("horizontal_and_vertical"),
        keras.layers.RandomRotation(0.15, fill_mode="reflect"),
        keras.layers.RandomZoom((-0.15, 0.2), fill_mode="reflect"),
        keras.layers.RandomTranslation(0.1, 0.1, fill_mode="reflect"),
        keras.layers.RandomBrightness(0.25, value_range=(0, 255)),
        keras.layers.RandomContrast(0.25),
    ], name="augmentation")


def build_model(size, n_classes, alpha):
    inputs = keras.Input((size, size, 3), name="image")             # raw pixels 0..255 (what the camera gives)
    x = keras.layers.Rescaling(1 / 127.5, offset=-1, name="to_minus1_1")(inputs)  # MobileNet expects -1..1
    base = keras.applications.MobileNetV2(input_shape=(size, size, 3), alpha=alpha, include_top=False,
                                          weights="imagenet")
    base.trainable = False
    x = base(x, training=False)                                      # BatchNorm stays in inference mode
    x = keras.layers.GlobalAveragePooling2D()(x)
    x = keras.layers.Dropout(0.3)(x)
    outputs = keras.layers.Dense(n_classes, activation="softmax", name="waste_class")(x)
    return keras.Model(inputs, outputs, name="smartbin_mobilenetv2"), base


def class_weights(train, n):
    counts = np.zeros(n)
    for _, y in train.unbatch():
        counts[int(y)] += 1
    w = counts.sum() / (n * np.maximum(counts, 1))
    return {i: float(w[i]) for i in range(n)}, counts


def report(y_true, y_pred, classes):
    n = len(classes)
    cm = np.zeros((n, n), dtype=int)
    for t, p in zip(y_true, y_pred):
        cm[t, p] += 1
    per_class = {}
    for i, c in enumerate(classes):
        tp = cm[i, i]
        prec = tp / cm[:, i].sum() if cm[:, i].sum() else 0.0
        rec = tp / cm[i, :].sum() if cm[i, :].sum() else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        per_class[c] = {"precision": round(prec, 3), "recall": round(rec, 3), "f1": round(f1, 3), "support": int(cm[i, :].sum())}
    bins_true = [BIN_OF[classes[t]] for t in y_true]
    bins_pred = [BIN_OF[classes[p]] for p in y_pred]
    return {
        "accuracy": round(float(np.trace(cm) / cm.sum()), 4),
        "compartment_accuracy": round(float(np.mean([a == b for a, b in zip(bins_true, bins_pred)])), 4),
        "per_class": per_class,
        "confusion_matrix": cm.tolist(),
    }


def plot(history_list, metrics, classes):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    acc = sum((h.history["accuracy"] for h in history_list), [])
    val = sum((h.history["val_accuracy"] for h in history_list), [])
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(acc, label="training")
    ax.plot(val, label="validation")
    ax.axvline(len(history_list[0].history["accuracy"]) - 0.5, color="gray", ls="--", lw=1)
    ax.text(len(history_list[0].history["accuracy"]) - 0.3, min(acc + val), "fine-tuning", color="gray", fontsize=8)
    ax.set(xlabel="epoch", ylabel="accuracy", title="Training of the waste classifier")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / "training_curves.png", dpi=120)

    cm = np.array(metrics["int8"]["confusion_matrix"])
    fig, ax = plt.subplots(figsize=(5.2, 4.6))
    ax.imshow(cm, cmap="Greens")
    ax.set_xticks(range(len(classes)), classes)
    ax.set_yticks(range(len(classes)), classes)
    ax.set(xlabel="predicted", ylabel="true", title=f"Test set, int8 model (accuracy {metrics['int8']['accuracy']:.1%})")
    for i in range(len(classes)):
        for j in range(len(classes)):
            ax.text(j, i, cm[i, j], ha="center", va="center", color="white" if cm[i, j] > cm.max() / 2 else "black")
    fig.tight_layout()
    fig.savefig(OUT / "confusion_matrix.png", dpi=120)


def representative(train_plain, n=1000, seed=42):
    """Calibration images for int8: many, shuffled, from every class (300 in-order images lost ~6 % accuracy)."""
    def gen():
        for images, _ in train_plain.unbatch().shuffle(3000, seed=seed).batch(1).take(n):
            yield [tf.cast(images, tf.float32)]
    return gen


def to_int8_tflite(model, rep):
    export_dir = OUT / "checkpoints" / "saved_model"
    model.export(str(export_dir), verbose=False)
    conv = tf.lite.TFLiteConverter.from_saved_model(str(export_dir))
    conv.optimizations = [tf.lite.Optimize.DEFAULT]
    conv.representative_dataset = rep
    conv.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    conv.inference_input_type = tf.int8
    conv.inference_output_type = tf.int8
    return conv.convert()


def evaluate_tflite(tflite_bytes, test):
    interp = tf.lite.Interpreter(model_content=tflite_bytes, num_threads=2)
    interp.allocate_tensors()
    inp, out = interp.get_input_details()[0], interp.get_output_details()[0]
    s_in, z_in = inp["quantization"]
    y_true, y_pred, times = [], [], []
    for images, labels in test.unbatch().batch(1):
        x = np.clip(np.round(images.numpy() / s_in + z_in), -128, 127).astype(np.int8)
        interp.set_tensor(inp["index"], x)
        t0 = time.perf_counter()
        interp.invoke()
        times.append((time.perf_counter() - t0) * 1000)
        y_pred.append(int(np.argmax(interp.get_tensor(out["index"])[0])))
        y_true.append(int(labels.numpy()[0]))
    return y_true, y_pred, float(np.median(times))


def c_header(tflite_bytes, classes):
    hexes = ", ".join(f"0x{b:02x}" for b in tflite_bytes)
    names = ", ".join(f'"{c}"' for c in classes)
    return (f"// Edge-AI Smart Dustbin - MobileNetV2 int8 model ({len(tflite_bytes)} bytes)\n"
            f"// Generated by ml/train_mobilenet.py. For TensorFlow Lite Micro (alternative to Edge Impulse).\n"
            f"#pragma once\n#include <stdint.h>\n"
            f"const char* const MODEL_LABELS[] = {{{names}}};\nconst int MODEL_LABEL_COUNT = {len(classes)};\n"
            f"alignas(16) const uint8_t MODEL_DATA[] = {{{hexes}}};\n"
            f"const unsigned int MODEL_DATA_LEN = {len(tflite_bytes)};\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=128, choices=[96, 128, 160])
    ap.add_argument("--alpha", type=float, default=0.35, choices=[0.35, 0.5, 0.75, 1.0])
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--epochs-head", type=int, default=15)
    ap.add_argument("--epochs-fine", type=int, default=15)
    ap.add_argument("--fine-tune-layers", type=int, default=40, help="top MobileNet layers to retrain")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    tf.keras.utils.set_random_seed(args.seed)
    tf.config.threading.set_intra_op_parallelism_threads(os.cpu_count() or 2)
    OUT.mkdir(parents=True, exist_ok=True)
    t_start = time.time()

    classes, train_raw, val, test = datasets(args.size, args.batch, args.seed)
    print(f"classes: {classes}")
    weights, counts = class_weights(train_raw, len(classes))
    print("training images per class:", dict(zip(classes, counts.astype(int).tolist())))

    aug = augmenter()
    auto = tf.data.AUTOTUNE
    train_plain = train_raw.cache()
    def augment(x, y):
        return aug(x, training=True), y

    train = train_plain.shuffle(500, seed=args.seed).map(augment, num_parallel_calls=auto).prefetch(auto)
    val, test = val.cache().prefetch(auto), test.cache()

    model, base = build_model(args.size, len(classes), args.alpha)
    stop = keras.callbacks.EarlyStopping(monitor="val_accuracy", patience=4, restore_best_weights=True)

    print("\n=== phase 1: train the classifier head (MobileNetV2 frozen)")
    model.compile(optimizer=keras.optimizers.Adam(1e-3), loss="sparse_categorical_crossentropy", metrics=["accuracy"])
    h1 = model.fit(train, validation_data=val, epochs=args.epochs_head, class_weight=weights, callbacks=[stop], verbose=2)

    print(f"\n=== phase 2: fine-tune the top {args.fine_tune_layers} layers of MobileNetV2")
    base.trainable = True
    for layer in base.layers[:-args.fine_tune_layers]:
        layer.trainable = False
    for layer in base.layers:
        if isinstance(layer, keras.layers.BatchNormalization):
            layer.trainable = False  # keep BatchNorm statistics from ImageNet: more stable with small data
    model.compile(optimizer=keras.optimizers.Adam(1e-4), loss="sparse_categorical_crossentropy", metrics=["accuracy"])
    h2 = model.fit(train, validation_data=val, epochs=args.epochs_fine, class_weight=weights, callbacks=[stop], verbose=2)

    print("\n=== testing (images never seen during training)")
    probs = model.predict(test, verbose=0)
    y_true = np.concatenate([y.numpy() for _, y in test])
    metrics = {"float32": report(y_true.tolist(), probs.argmax(1).tolist(), classes)}

    print("=== int8 quantisation for the ESP32")
    tflite = to_int8_tflite(model, representative(train_plain))
    (OUT / "model_int8.tflite").write_bytes(tflite)
    t_true, t_pred, ms = evaluate_tflite(tflite, test)
    metrics["int8"] = report(t_true, t_pred, classes)
    metrics.update({
        "classes": classes, "bins": {c: BIN_OF[c] for c in classes},
        "input": {"width": args.size, "height": args.size, "channels": 3, "pixel_range": "0..255 (scaled inside the model)"},
        "model": f"MobileNetV2 alpha={args.alpha}", "params": int(model.count_params()),
        "tflite_bytes": len(tflite), "laptop_int8_ms_per_image": round(ms, 2),
        "train_minutes": round((time.time() - t_start) / 60, 1),
        "training_images": int(counts.sum()), "test_images": len(t_true),
    })
    (OUT / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf8")
    (OUT / "labels.txt").write_text("\n".join(classes) + "\n", encoding="utf8")
    (OUT / "model_data.h").write_text(c_header(tflite, classes), encoding="utf8")
    model.save(OUT / "smartbin_mobilenetv2.keras")
    plot([h1, h2], metrics, classes)

    m = metrics["int8"]
    lines = [
        "# Model card: Edge-AI Smart Dustbin waste classifier", "",
        f"* Model: MobileNetV2 alpha={args.alpha}, input {args.size}x{args.size} RGB, transfer learning from ImageNet",
        f"* Classes: {', '.join(classes)}  →  organic compartment: organic + paper; inorganic: plastic + metal",
        f"* Training images: {int(counts.sum())} (+15 % validation), test images: {len(t_true)} (never seen in training)",
        f"* int8 TFLite size: {len(tflite) / 1024:.0f} KB, {model.count_params():,} parameters",
        f"* Trained on a laptop CPU in {metrics['train_minutes']} min", "",
        "| Metric (test set) | float32 | int8 (on the ESP32) |", "|---|---|---|",
        f"| Accuracy, 4 classes | {metrics['float32']['accuracy']:.1%} | {m['accuracy']:.1%} |",
        f"| Correct compartment | {metrics['float32']['compartment_accuracy']:.1%} | {m['compartment_accuracy']:.1%} |", "",
        "| Class | Precision | Recall | F1 | Test images |", "|---|---|---|---|---|",
        *[f"| {c} | {v['precision']:.2f} | {v['recall']:.2f} | {v['f1']:.2f} | {v['support']} |" for c, v in m["per_class"].items()],
        "", "![Confusion matrix](confusion_matrix.png)", "", "![Training curves](training_curves.png)", "",
        "**Limits:** trained mostly on public photos (RealWaste, TrashNet). Accuracy inside the real bin depends on adding "
        "your own ESP32 photos (see docs/DATASET_GUIDE.md, section 5) and retraining.",
    ]
    (OUT / "MODEL_CARD.md").write_text("\n".join(lines) + "\n", encoding="utf8")

    print(f"\n4-class accuracy  float32 {metrics['float32']['accuracy']:.1%}  |  int8 {m['accuracy']:.1%}")
    print(f"correct compartment  float32 {metrics['float32']['compartment_accuracy']:.1%}  |  int8 {m['compartment_accuracy']:.1%}")
    print(f"int8 model: {len(tflite) / 1024:.0f} KB, {ms:.1f} ms/image on this laptop, trained in {metrics['train_minutes']} min")
    print(f"outputs in {OUT}")


if __name__ == "__main__":
    main()
