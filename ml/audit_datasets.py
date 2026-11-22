"""Audit the previously downloaded datasets (READ-ONLY: the zips in ml/datasets/raw/ are never changed).

    ml\\.venv\\Scripts\\python ml\\audit_datasets.py              # inventory + quality + duplicates + contact sheets
    ml\\.venv\\Scripts\\python ml\\audit_datasets.py --subtypes   # also guess the object type (ImageNet MobileNetV2)

For every original image it records: source dataset, original path and class, our label, size, format,
MD5 / perceptual hashes, brightness / contrast / sharpness, and what happened to it in the CURRENT
training set built by prepare_dataset.py (it replays that script exactly, same seed):

    used_train / used_test   -> in ml/datasets/processed/
    unused_cap               -> useful, but cut by the 900-per-class cap (never trained on)
    dup_exact / dup_near     -> removed as a duplicate (of the image in column dup_of)
    skipped_class            -> class not used by the bin (glass, textile, trash...)

Output: ml/datasets/audit/  inventory.csv, audit_summary.json, contact_sheets/<source>_<class>.jpg
"""

import argparse
import csv
import hashlib
import io
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

# --- v1 helpers copied from prepare_dataset.py as it was when the v1 dataset was built (commit 65a92a0),
#     so this audit keeps replaying exactly what v1 did even after prepare_dataset.py changes.
import re
import zipfile
from types import SimpleNamespace
from PIL import ImageOps

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



prep = SimpleNamespace(ROOT=ROOT, RAW=RAW, iter_source_images=iter_source_images, label_for=label_for,
                       to_square=to_square, average_hash=average_hash)

AUDIT = prep.ROOT / "datasets" / "audit"


def dhash(img, size=8):
    g = np.asarray(img.convert("L").resize((size + 1, size), Image.BILINEAR), dtype=np.int16)
    return "".join("1" if b else "0" for b in (g[:, 1:] > g[:, :-1]).flatten())


def quality(img):
    g = img.convert("L")
    a = np.asarray(g, dtype=np.float32)
    lap = np.asarray(g.filter(ImageFilter.FIND_EDGES), dtype=np.float32)
    return round(float(a.mean()), 1), round(float(a.std()), 1), round(float(lap.var()), 1)


def flags(w, h, bright, contrast, sharp):
    f = []
    if min(w, h) < 200: f.append("low_res")
    if bright < 40: f.append("too_dark")
    if bright > 225: f.append("too_bright")
    if contrast < 18: f.append("low_contrast")
    if sharp < 15: f.append("blurry")
    return "|".join(f)


def contact_sheet(paths_imgs, out, cols=12, cell=110, max_n=96):
    items = paths_imgs[:max_n]
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell, max(rows, 1) * cell), "white")
    for i, im in enumerate(items):
        sheet.paste(im.resize((cell - 4, cell - 4)), ((i % cols) * cell + 2, (i // cols) * cell + 2))
    sheet.save(out, "JPEG", quality=85)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=160)       # same defaults as prepare_dataset.py
    ap.add_argument("--per-class", type=int, default=900)
    ap.add_argument("--test", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--subtypes", action="store_true")
    args = ap.parse_args()

    (AUDIT / "contact_sheets").mkdir(parents=True, exist_ok=True)
    rows, md5_first, ahash_first = [], {}, {}
    by_label = defaultdict(list)     # label -> [row index]   (exactly like prepare_dataset.by_label)
    sheets = defaultdict(list)
    squares = {}                     # row index -> 224px square for subtype guessing
    rng_sheet = random.Random(1)

    for source, parts, data in prep.iter_source_images():
        label, known = prep.label_for(parts)
        orig_class = parts[-2] if len(parts) > 1 else ""
        r = {"source": source, "path": "/".join(parts), "orig_class": orig_class,
             "label": label if known else "?", "status": "", "dup_of": "", "split": ""}
        rows.append(r)
        idx = len(rows) - 1
        try:
            raw = Image.open(io.BytesIO(data))
            r["format"], (r["width"], r["height"]) = raw.format, raw.size
            r["bytes"] = len(data)
            full = raw.convert("RGB")
            r["brightness"], r["contrast"], r["sharpness"] = quality(full.resize((256, 256)))
            r["flags"] = flags(r["width"], r["height"], r["brightness"], r["contrast"], r["sharpness"])
        except Exception:
            r["status"] = "unreadable"
            continue
        md5 = hashlib.md5(data).hexdigest()
        r["md5"] = md5
        sq = prep.to_square(Image.open(io.BytesIO(data)), args.size)
        ah = prep.average_hash(sq)
        r["ahash"], r["dhash"] = ah, dhash(sq)
        if not known or label is None:
            r["status"] = "skipped_class" if known else "unknown_folder"
            continue
        # replay prepare_dataset.py's duplicate logic in the same order
        if md5 in md5_first:
            r["status"], r["dup_of"] = "dup_exact", rows[md5_first[md5]]["path"]
            continue
        if ah in ahash_first and source != "own":
            r["status"], r["dup_of"] = "dup_near", rows[ahash_first[ah]]["path"]
            continue
        md5_first[md5] = idx
        ahash_first.setdefault(ah, idx)
        by_label[label].append(idx)
        sheets[(source, orig_class)].append(idx)
        if args.subtypes:
            squares[idx] = sq

    # replay the balancing + split (same RNG calls as prepare_dataset.main)
    random.seed(args.seed)
    for label in sorted(by_label):
        items = by_label[label]
        own = [i for i in items if rows[i]["source"] == "own"]
        public = [i for i in items if rows[i]["source"] != "own"]
        random.shuffle(public)
        kept, cut = public[: args.per_class], public[args.per_class:]
        for i in cut:
            rows[i]["status"] = "unused_cap"
        for group in (own, kept):
            random.shuffle(group)
            n_test = max(1, round(len(group) * args.test)) if len(group) > 1 else 0
            for k, i in enumerate(group):
                split = "test" if k < n_test else "train"
                rows[i]["status"], rows[i]["split"] = f"used_{split}", split
                rows[i]["processed_file"] = f"{split}/{label}/{label}.{rows[i]['source']}_{k:04d}.jpg"

    # cross-dataset near duplicates that the 64-bit aHash missed: same dHash
    dh = defaultdict(list)
    for i, r in enumerate(rows):
        if r.get("dhash") and r["status"].startswith(("used", "unused")):
            dh[r["dhash"]].append(i)
    for group in dh.values():
        if len(group) > 1:
            for i in group[1:]:
                rows[i]["flags"] = (rows[i].get("flags", "") + "|same_dhash_as:" + rows[group[0]]["path"]).strip("|")

    # optional: guess the object type with an ImageNet classifier (rough proxy for waste subtype)
    if args.subtypes and squares:
        import tensorflow as tf
        model = tf.keras.applications.MobileNetV2(weights="imagenet")
        pre = tf.keras.applications.mobilenet_v2.preprocess_input
        dec = tf.keras.applications.mobilenet_v2.decode_predictions
        ids = list(squares)
        for s in range(0, len(ids), 64):
            batch = ids[s:s + 64]
            x = pre(np.stack([np.asarray(squares[i].resize((224, 224)), dtype=np.float32) for i in batch]))
            for i, top in zip(batch, dec(model.predict(x, verbose=0), top=3)):
                rows[i]["imagenet_top1"], rows[i]["imagenet_p1"] = top[0][1], round(float(top[0][2]), 3)
                rows[i]["imagenet_top3"] = " ".join(t[1] for t in top)
            print(f"  subtypes {min(s + 64, len(ids))}/{len(ids)}", end="\r")
        print()

    # contact sheets: random sample of each original class (for manual review)
    for (source, cls), idxs in sheets.items():
        sample = rng_sheet.sample(idxs, min(96, len(idxs)))
        ims = []
        for i in sample:
            ims.append(squares[i] if i in squares else None)
        if any(im is None for im in ims):   # load again if subtypes were not computed
            ims = []
            for i in sample:
                ims.append(_reload(rows[i], args.size))
        contact_sheet(ims, AUDIT / "contact_sheets" / f"{source}_{cls.replace(' ', '_')}.jpg")
        with open(AUDIT / "contact_sheets" / f"{source}_{cls.replace(' ', '_')}.txt", "w", encoding="utf8") as f:
            f.write("\n".join(rows[i]["path"] for i in sample))

    fields = ["source", "path", "orig_class", "label", "status", "split", "processed_file", "dup_of", "format",
              "width", "height", "bytes", "brightness", "contrast", "sharpness", "flags", "md5", "ahash", "dhash",
              "imagenet_top1", "imagenet_p1", "imagenet_top3"]
    with open(AUDIT / "inventory.csv", "w", newline="", encoding="utf8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    summ = {"per_source_class": defaultdict(Counter), "per_label_status": defaultdict(Counter),
            "resolutions": defaultdict(Counter), "flags": defaultdict(Counter), "subtypes": defaultdict(Counter)}
    for r in rows:
        key = f"{r['source']}/{r['orig_class']}"
        summ["per_source_class"][key][r["status"]] += 1
        summ["per_label_status"][str(r["label"])][r["status"]] += 1
        summ["resolutions"][r["source"]][f"{r.get('width')}x{r.get('height')} {r.get('format')}"] += 1
        for fl in (r.get("flags") or "").split("|"):
            if fl and not fl.startswith("same_dhash"):
                summ["flags"][key][fl] += 1
            elif fl:
                summ["flags"][key]["same_dhash_other"] += 1
        if r.get("imagenet_top1"):
            summ["subtypes"][str(r["label"])][r["imagenet_top1"]] += 1
    out = {k: {kk: dict(vv.most_common(40) if k == "subtypes" else vv) for kk, vv in v.items()} for k, v in summ.items()}
    (AUDIT / "audit_summary.json").write_text(json.dumps(out, indent=2), encoding="utf8")
    print(json.dumps(out["per_source_class"], indent=1))


_zip_cache = {}


def _reload(r, size):
    import zipfile
    z = _zip_cache.get(r["source"])
    if z is None:
        for item in prep.RAW.iterdir():
            if item.suffix.lower() == ".zip" and r["source"] == "".join(c for c in item.stem.lower() if c.isalnum())[:16]:
                z = _zip_cache[r["source"]] = zipfile.ZipFile(item)
    return prep.to_square(Image.open(io.BytesIO(z.read(r["path"]))), size).resize((224, 224))


if __name__ == "__main__":
    main()
