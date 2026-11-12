"""Build the Edge-AI Smart Dustbin dataset (4 classes) from public datasets + your own photos.

    ml\\.venv\\Scripts\\python ml\\prepare_dataset.py            (defaults are fine)
    ml\\.venv\\Scripts\\python ml\\prepare_dataset.py --per-class 900 --size 160

Inputs (put any of them in ml/datasets/raw/ - zip files or folders):
  * RealWaste (UCI)             realwaste.zip
  * TrashNet / "Garbage classification" (Kaggle / Hugging Face)   trashnet-resized.zip, garbage-classification.zip
  * Your own photos taken by the ESP32 camera in the bin           ml/datasets/own/<label>/*.jpg
    (also what the dashboard exports: Detections -> "Download reviewed photos")

Output (ml/datasets/processed/):
  train/<label>/<label>.<source>_<n>.jpg     80 %   (file name starts with the label = Edge Impulse format)
  test/<label>/...                           20 %   never used for training
  manifest.csv, summary.json, upload_to_edge_impulse.bat

The 4 classes and the 2 compartments of the bin:
  organic compartment  <- organic (food, peels, leaves)  + paper (paper, cardboard)
  inorganic compartment<- plastic + metal
"""

import argparse
import csv
import hashlib
import io
import json
import random
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "datasets" / "raw"
OWN = ROOT / "datasets" / "own"
OUT = ROOT / "datasets" / "processed"

LABELS = ["organic", "paper", "plastic", "metal"]
BIN_OF = {"organic": "organic", "paper": "organic", "plastic": "inorganic", "metal": "inorganic"}

# folder name in a source dataset  ->  our label   (None = not used: glass, textile, mixed trash...)
CLASS_MAP = {
    # RealWaste (UCI): Cardboard, Food Organics, Glass, Metal, Miscellaneous Trash, Paper, Plastic, Textile Trash, Vegetation
    "cardboard": "paper", "food organics": "organic", "vegetation": "organic", "metal": "metal",
    "paper": "paper", "plastic": "plastic", "glass": None, "miscellaneous trash": None, "textile trash": None,
    # TrashNet / Garbage classification (6 classes): cardboard, glass, metal, paper, plastic, trash
    "trash": None,
    # Garbage classification 12 classes (Kaggle): biological, brown-glass, cardboard, clothes, green-glass,
    # metal, paper, plastic, shoes, trash, white-glass, battery
    "biological": "organic", "battery": None, "clothes": None, "shoes": None,
    "brown-glass": None, "green-glass": None, "white-glass": None,
    # your own photos / dashboard export use our label names directly
    "organic": "organic", "food": "organic", "food_waste": "organic", "fruit_peel": "organic", "leaves": "organic",
    "background": "background",  # optional 5th class: empty tray (helps the camera say "nothing here")
}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def norm(name):
    return re.sub(r"[\s_]+", " ", name.strip().lower()).replace(" ", " ")


def label_for(path_parts):
    """Use the closest parent folder that we recognise."""
    for part in reversed(path_parts[:-1]):
        key = norm(part)
        for candidate in (key, key.replace(" ", "-"), key.replace(" ", "_")):
            if candidate in CLASS_MAP:
                return CLASS_MAP[candidate], True
    return None, False


def iter_source_images():
    """Yield (source_name, relative_path_parts, bytes) for every image in raw zips/folders and own photos."""
    for item in sorted(RAW.iterdir()) if RAW.exists() else []:
        source = re.sub(r"[^a-z0-9]+", "", item.stem.lower())[:16] or "src"
        if item.suffix.lower() == ".zip":
            with zipfile.ZipFile(item) as z:
                for info in z.infolist():
                    p = Path(info.filename)
                    if not info.is_dir() and p.suffix.lower() in IMAGE_EXT and "__MACOSX" not in p.parts:
                        yield source, p.parts, z.read(info)
                    elif p.suffix.lower() == ".zip" and not info.is_dir():  # zip inside the zip (RealWaste)
                        with zipfile.ZipFile(io.BytesIO(z.read(info))) as inner:
                            for i2 in inner.infolist():
                                p2 = Path(i2.filename)
                                if not i2.is_dir() and p2.suffix.lower() in IMAGE_EXT and "__MACOSX" not in p2.parts:
                                    yield source, p2.parts, inner.read(i2)
        elif item.is_dir():
            for f in item.rglob("*"):
                if f.suffix.lower() in IMAGE_EXT:
                    yield source, f.relative_to(item).parts, f.read_bytes()
    if OWN.exists():
        for f in OWN.rglob("*"):
            if f.suffix.lower() in IMAGE_EXT:
                yield "own", f.relative_to(OWN).parts, f.read_bytes()


def average_hash(img, size=8):
    """Tiny perceptual hash: finds the same photo even if re-saved or resized."""
    small = img.convert("L").resize((size, size), Image.BILINEAR)
    pixels = list(small.tobytes())
    avg = sum(pixels) / len(pixels)
    return "".join("1" if p > avg else "0" for p in pixels)


def to_square(img, size):
    """Centre-crop to a square and resize: same framing as the camera above the tray."""
    img = ImageOps.exif_transpose(img).convert("RGB")
    return ImageOps.fit(img, (size, size), Image.BILINEAR, centering=(0.5, 0.5))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--size", type=int, default=160, help="saved image size (train at 96 or 128 later)")
    ap.add_argument("--per-class", type=int, default=900, help="max PUBLIC images per class (own photos always kept)")
    ap.add_argument("--test", type=float, default=0.2, help="fraction kept for testing")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    random.seed(args.seed)

    seen_md5, seen_ahash = set(), set()
    by_label = defaultdict(list)          # label -> [(source, PIL image)]
    skipped, dupes, unknown_folders = Counter(), 0, Counter()

    for source, parts, data in iter_source_images():
        label, known = label_for(parts)
        if not known:
            unknown_folders["/".join(parts[:-1])[:60]] += 1
            continue
        if label is None:
            skipped[norm(parts[-2])] += 1
            continue
        md5 = hashlib.md5(data).hexdigest()
        if md5 in seen_md5:
            dupes += 1
            continue
        try:
            img = to_square(Image.open(io.BytesIO(data)), args.size)
        except Exception:
            skipped["unreadable"] += 1
            continue
        ah = average_hash(img)
        if ah in seen_ahash and source != "own":
            dupes += 1
            continue
        seen_md5.add(md5)
        seen_ahash.add(ah)
        by_label[label].append((source, img))

    if not by_label:
        raise SystemExit(f"No images found. Put dataset zips in {RAW} (see docs/DATASET_GUIDE.md).")

    # fresh output folder
    if OUT.exists():
        for f in sorted(OUT.rglob("*"), reverse=True):
            f.unlink() if f.is_file() else f.rmdir()
    rows, summary = [], {"size": args.size, "classes": {}, "bins": BIN_OF, "skipped": dict(skipped), "duplicates": dupes}

    for label in sorted(by_label):
        items = by_label[label]
        own = [x for x in items if x[0] == "own"]
        public = [x for x in items if x[0] != "own"]
        random.shuffle(public)
        public = public[: args.per_class]  # balance the public part
        for group in (own, public):        # split own and public separately, so both appear in test
            random.shuffle(group)
            n_test = max(1, round(len(group) * args.test)) if len(group) > 1 else 0
            for i, (source, img) in enumerate(group):
                split = "test" if i < n_test else "train"
                folder = OUT / split / label
                folder.mkdir(parents=True, exist_ok=True)
                name = f"{label}.{source}_{i:04d}.jpg"
                img.save(folder / name, "JPEG", quality=90)
                rows.append({"file": f"{split}/{label}/{name}", "label": label, "bin": BIN_OF.get(label, "none"),
                             "source": source, "split": split})
        counts = Counter(r["split"] for r in rows if r["label"] == label)
        summary["classes"][label] = {"train": counts["train"], "test": counts["test"],
                                     "own_photos": len(own), "sources": dict(Counter(s for s, _ in own + public))}

    with open(OUT / "manifest.csv", "w", newline="", encoding="utf8") as f:
        w = csv.DictWriter(f, fieldnames=["file", "label", "bin", "source", "split"])
        w.writeheader()
        w.writerows(rows)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf8")

    # Edge Impulse upload script (needs: npm install -g edge-impulse-cli)
    lines = ["@echo off", "REM Uploads the prepared dataset to your Edge Impulse project.",
             "REM First time: npm install -g edge-impulse-cli   then   edge-impulse-uploader --clean",
             f'cd /d "%~dp0"']
    for split, category in (("train", "training"), ("test", "testing")):
        for label in sorted(by_label):
            lines.append(f"call edge-impulse-uploader --category {category} --label {label} {split}\\{label}\\*.jpg")
    lines.append("pause")
    (OUT / "upload_to_edge_impulse.bat").write_text("\r\n".join(lines) + "\r\n", encoding="utf8")

    # report
    print(f"\nPrepared dataset in {OUT}  (images {args.size}x{args.size})\n")
    print(f"{'class':<12}{'bin':<11}{'train':>7}{'test':>7}{'own':>6}   sources")
    for label in sorted(summary["classes"]):
        c = summary["classes"][label]
        print(f"{label:<12}{BIN_OF.get(label, '-'):<11}{c['train']:>7}{c['test']:>7}{c['own_photos']:>6}   {c['sources']}")
    print(f"\nskipped (not used): {dict(skipped)}   duplicates removed: {dupes}")
    if unknown_folders:
        print("folders not recognised (add them to CLASS_MAP if useful):", dict(unknown_folders.most_common(8)))
    print(f"\nNext: ml\\.venv\\Scripts\\python ml\\train_mobilenet.py   or upload with {OUT / 'upload_to_edge_impulse.bat'}")


if __name__ == "__main__":
    main()
