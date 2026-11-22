"""Build the Edge-AI Smart Dustbin dataset (4 classes) from public datasets + your own photos.

    ml\\.venv\\Scripts\\python ml\\prepare_dataset.py                 (defaults are fine)
    ml\\.venv\\Scripts\\python ml\\prepare_dataset.py --target 1500   (images per class, train + test)

Inputs (never modified, read straight from the zip files):
  ml/datasets/raw/           realwaste.zip (UCI RealWaste), trashnet-resized.zip (TrashNet)
  ml/datasets/raw_external/  king.zip (Kaggle alistairking, Recyclable & Household Waste)
                             gdv2.zip (Kaggle sumn2u, Garbage Dataset v2)
  ml/datasets/own/<label>/[<subtype>/]*.jpg   photos from the bin's own camera (always kept)

What it does
  1. maps every source folder to  label / subtype group  (SOURCES below; glass, textile, shoes... are skipped,
     ambiguous folders such as paper cups are skipped and listed in the report)
  2. removes duplicates: identical files (MD5) and near-identical photos, also ACROSS datasets
     (16x16 difference hash -> candidates, confirmed by pixel correlation, so different objects on
     the same plain background are NOT treated as duplicates any more)
  3. keeps the v1 benchmark test set (benchmark_v1.csv, 709 photos) in the test split, so old and new
     models can be compared on exactly the same photos, and never trains on them
  4. balances each class by SUBTYPE: every subtype group gets a share of the class (weights in SOURCES),
     so one kind of object (garden waste, envelopes, clear bottles...) can no longer dominate a class
  5. centre-crops to a square and resizes (same framing as the camera firmware), JPEG quality 90
  6. writes ml/datasets/processed/: train/, test/, manifest.csv (with the ORIGINAL file of every image),
     summary.json, integration_report.md, upload_to_edge_impulse.bat

Organic compartment <- organic + paper.  Inorganic compartment <- plastic + metal.
Paper always stays its own class (never merged into organic).
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

import numpy as np
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent
RAW_DIRS = [ROOT / "datasets" / "raw", ROOT / "datasets" / "raw_external"]
OWN = ROOT / "datasets" / "own"
OUT = ROOT / "datasets" / "processed"
BENCHMARK = ROOT / "benchmark_v1.csv"

LABELS = ["organic", "paper", "plastic", "metal"]
BIN_OF = {"organic": "organic", "paper": "organic", "plastic": "inorganic", "metal": "inorganic", "background": "none"}

# source dataset -> licence, and folder name -> (label, subtype group, weight)   None = not used, "review" = ambiguous
# weight = how big a share of its class this group may take (relative to the other groups of that class)
SOURCES = {
    "realwaste": {"license": "CC BY 4.0 (Single et al. 2023, UCI)", "folders": {
        "food organics": ("organic", "rw_food", 2.0), "vegetation": ("organic", "rw_garden", 1.0),
        "paper": ("paper", "rw_paper", 1.0), "cardboard": ("paper", "rw_cardboard", 1.0),
        "plastic": ("plastic", "rw_plastic", 1.5), "metal": ("metal", "rw_metal", 1.5),
        "glass": None, "miscellaneous trash": None, "textile trash": None}},
    "trashnetresized": {"license": "MIT (Thung & Yang 2016)", "folders": {
        "paper": ("paper", "tn_flyer_envelope", 0.7), "cardboard": ("paper", "tn_cardboard", 0.7),
        "plastic": ("plastic", "tn_bottle_container", 1.0), "metal": ("metal", "tn_can_tin_foil", 1.0),
        "glass": None, "trash": None}},
    # Visually checked (24 random photos per folder, 21 Nov 2026): mostly WEB STOCK photos, not waste on a surface.
    # Folders whose photos are mostly not the object itself (office scenes, magazine covers with faces, coffee beans,
    # spraying aerosols) are excluded; the rest get moderate weights so the real-waste photos stay the majority.
    "king": {"license": "Kaggle: MIT; data card: educational/research/non-commercial use (A. King)", "folders": {
        # organic
        "food waste": ("organic", "food_waste", 2.0), "eggshells": ("organic", "eggshells", 0.5),
        "tea bags": ("organic", "tea_bags", 0.4), "coffee grounds": None,          # coffee beans/cups, not waste
        # paper
        "newspaper": ("paper", "newspaper", 1.0), "office paper": None,              # office scenes, clipart
        "magazines": None,                                                            # glossy covers with faces
        "cardboard boxes": ("paper", "cardboard_boxes", 0.7),
        "cardboard packaging": ("paper", "cardboard_packaging", 0.7),
        "paper cups": "review",                       # plastic-lined: not clearly paper
        # plastic
        "plastic water bottles": ("plastic", "water_bottles", 1.2), "plastic soda bottles": ("plastic", "soda_bottles", 1.5),
        "plastic detergent bottles": ("plastic", "detergent_bottles", 0.4),
        "plastic shopping bags": ("plastic", "shopping_bags", 1.5), "plastic trash bags": ("plastic", "trash_bags", 0.4),
        "plastic food containers": ("plastic", "food_containers", 0.6), "plastic cup lids": ("plastic", "cup_lids", 0.2),
        "disposable plastic cutlery": ("plastic", "cutlery", 0.2), "plastic straws": None,  # too small for the tray,
        "styrofoam cups": ("plastic", "styrofoam", 0.2), "styrofoam food containers": ("plastic", "styrofoam", 0.2),
        # metal
        "aluminum soda cans": ("metal", "soda_cans", 1.5), "aluminum food cans": ("metal", "food_tins", 1.0),
        "steel food cans": ("metal", "food_tins", 1.0), "aerosol cans": None,         # mostly spraying in action
        # not used
        "glass beverage bottles": None, "glass cosmetic containers": None, "glass food jars": None,
        "clothing": None, "shoes": None}},
    "gdv2": {"license": "MIT (S. Kunwar, Garbage Dataset v2)", "folders": {
        # checked by eye: biological = fresh/rotten fruit, vegetables, bread, cooked food (stock/market photos);
        # cardboard = about 1/3 drink cartons (Tetra Pak: paper + plastic + foil), ambiguous for this bin -> not used.
        # EXPERIMENT 22 Nov 2026: adding biological ("organic", "gd_biological", 2.0) made the model WORSE on the
        # 709-photo v1 benchmark in two training runs (82.8 % and 84.1 % vs 86.6 % without it; plastic confused
        # more often, see ml/output/v3_128_seed42 and v3_128_seed7). So it is switched off.
        # EXPERIMENT 22 Nov 2026 (v4): paper/plastic/metal (real phone photos, weights 1.5/2.0/1.5) plus more King
        # plastic folders scored 82.4 % vs 86.6 % / 84.5 % for v2 (two runs), plastic recall 71 % vs 78-79 %
        # (ml/output/v4_128_seed42). Also switched off. To try again, put back e.g. ("plastic", "gd_plastic", 2.0).
        "biological": None, "paper": None, "cardboard": None, "plastic": None, "metal": None,
        "battery": None, "glass": None, "trash": None, "shoes": None, "clothes": None}},
}
# GD v2 ships the same photos 3 times (original + padded 256 + padded 384): read only the originals
PATH_FILTER = {"gdv2": lambda parts: not any(p.lower().startswith("standardized") for p in parts)}
# fallback for datasets not listed in SOURCES (folder names = our labels)
GENERIC = {"organic": "organic", "food": "organic", "biological": "organic", "paper": "paper", "cardboard": "paper",
           "plastic": "plastic", "metal": "metal", "background": "background"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
PRIORITY = {"own": 0, "realwaste": 1, "trashnetresized": 2, "king": 3, "gdv2": 4}   # who wins a duplicate group


def norm(name):
    return re.sub(r"[\s_\-]+", " ", name.strip().lower())


def source_key(path):
    return re.sub(r"[^a-z0-9]+", "", path.stem.lower())[:16] or "src"


def classify(source, parts):
    """-> (label, group, weight) | None (not used) | 'review' | 'unknown'"""
    if source == "own":
        label = norm(parts[0]) if len(parts) > 1 else ""
        if label in LABELS + ["background"]:
            sub = norm(parts[1]).replace(" ", "_") if len(parts) > 2 else "mixed"
            return label, f"own_{sub}", 0.0
        return "unknown"
    folders = SOURCES.get(source, {}).get("folders")
    for part in reversed(parts[:-1]):
        key = norm(part)
        if folders is not None and key in folders:
            return folders[key]
        if folders is None and key in GENERIC:
            return GENERIC[key], f"{source}_{key.replace(' ', '_')}", 1.0
    return "unknown"


def iter_source_images(read=True):
    """Yield (source, parts, bytes-or-None) for every image in the zips/folders and own photos."""
    for raw in RAW_DIRS:
        for item in sorted(raw.iterdir()) if raw.exists() else []:
            source = source_key(item)
            keep = PATH_FILTER.get(source, lambda parts: True)
            if item.suffix.lower() == ".zip":
                with zipfile.ZipFile(item) as z:
                    for info in z.infolist():
                        p = Path(info.filename)
                        if info.is_dir() or "__MACOSX" in p.parts or p.name.startswith("."):
                            continue
                        if p.suffix.lower() in IMAGE_EXT and keep(p.parts):
                            yield source, p.parts, z.read(info) if read else None
                        elif p.suffix.lower() == ".zip":   # zip inside the zip
                            with zipfile.ZipFile(io.BytesIO(z.read(info))) as inner:
                                for i2 in inner.infolist():
                                    p2 = Path(i2.filename)
                                    if not i2.is_dir() and p2.suffix.lower() in IMAGE_EXT and "__MACOSX" not in p2.parts:
                                        yield source, p2.parts, inner.read(i2) if read else None
            elif item.is_dir():
                for f in sorted(item.rglob("*")):
                    if f.suffix.lower() in IMAGE_EXT and keep(f.relative_to(item).parts):
                        yield source, f.relative_to(item).parts, f.read_bytes() if read else None
    if OWN.exists():
        for f in sorted(OWN.rglob("*")):
            if f.suffix.lower() in IMAGE_EXT:
                yield "own", f.relative_to(OWN).parts, f.read_bytes() if read else None


def to_square(img, size):
    """Centre-crop to a square and resize: same framing as the camera above the tray."""
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "P"):                # transparent PNGs: put them on white, not black
        img = img.convert("RGBA")
        bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
        img = Image.alpha_composite(bg, img)
    img = img.convert("RGB")
    return ImageOps.fit(img, (size, size), Image.BILINEAR, centering=(0.5, 0.5))


def fingerprint(sq):
    """256-bit difference hash (4 x uint64) + 32x32 grey DETAIL thumbnail for confirmation.
    The detail map (thumbnail minus its blurred version) ignores lighting gradients, so two different white
    sheets on the same white board are not mistaken for one photo."""
    g = np.asarray(sq.convert("L").resize((17, 16), Image.BILINEAR), dtype=np.int16)
    bits = (g[:, 1:] > g[:, :-1]).flatten()
    words = np.packbits(bits).view(">u8").astype(np.uint64)
    grey = sq.convert("L").resize((32, 32), Image.BILINEAR)
    low = grey.resize((6, 6), Image.BILINEAR).resize((32, 32), Image.BILINEAR)
    t = (np.asarray(grey, dtype=np.float32) - np.asarray(low, dtype=np.float32)).flatten()
    t = (t - t.mean()) / (t.std() + 1e-6)
    return words, t.astype(np.float16)


def find_duplicates(hashes, thumbs, max_bits=40, min_corr=0.93):
    """Pairs (i, j) of near-identical photos: dHash close AND grey thumbnails strongly correlated."""
    pairs = []
    n = len(hashes)
    for i in range(n - 1):
        d = np.bitwise_count(hashes[i + 1:] ^ hashes[i]).sum(1)
        for j in np.nonzero(d <= max_bits)[0] + i + 1:
            corr = float(np.dot(thumbs[i].astype(np.float32), thumbs[j].astype(np.float32))) / thumbs.shape[1]
            if corr >= min_corr:
                pairs.append((i, int(j), int(d[j - i - 1]), round(corr, 3)))
    return pairs


def allocate(available, weights, total):
    """Share `total` among groups by weight; a group never gets more than it has (water-filling)."""
    alloc, active, left = {}, {g for g in available if available[g] > 0 and weights[g] > 0}, total
    while active and left > 0:
        wsum = sum(weights[g] for g in active)
        share = {g: left * weights[g] / wsum for g in active}
        full = {g for g in active if available[g] <= share[g]}
        if not full:
            base = {g: int(share[g]) for g in sorted(active)}          # sorted: same result in every run
            rest = left - sum(base.values())
            for g in sorted(sorted(active), key=lambda g: share[g] - base[g], reverse=True)[:rest]:
                base[g] += 1
            alloc.update(base)
            break
        for g in sorted(full):
            alloc[g] = available[g]
            left -= available[g]
        active -= full
    return alloc


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--size", type=int, default=160, help="saved image size (train at 96 or 128 later)")
    ap.add_argument("--target", "--per-class", type=int, default=1500,
                    help="public images per class, train + test (own photos are always added on top)")
    ap.add_argument("--test", type=float, default=0.2, help="fraction of each class kept for testing")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--from-manifest", type=Path, default=None,
                    help="rebuild exactly the images and train/test split listed in a saved manifest.csv "
                         "(e.g. ml/dataset_v2_manifest.csv, the data of the current model)")
    args = ap.parse_args()
    rng = random.Random(args.seed)
    fixed = None
    if args.from_manifest:
        with open(args.from_manifest, encoding="utf8") as f:
            fixed = {(r["source"], r["orig_path"]): r["split"] for r in csv.DictReader(f)}

    bench = {}
    if BENCHMARK.exists():
        with open(BENCHMARK, encoding="utf8") as f:
            bench = {(r["source"], r["orig_path"]): r["split_v1"] for r in csv.DictReader(f)}

    # ---- pass 1: read everything, classify, fingerprint (images are not kept in memory)
    items, hashes, thumbs, seen_md5 = [], [], [], {}
    skipped, review, unknown, exact_dupes, unreadable = Counter(), Counter(), Counter(), 0, 0
    for n_read, (source, parts, data) in enumerate(iter_source_images(), 1):
        if n_read % 2000 == 0:
            print(f"  read {n_read} images...", flush=True)
        c = classify(source, parts)
        folder = f"{source}/{parts[-2] if len(parts) > 1 else ''}"
        if c is None:
            skipped[folder] += 1
            continue
        if c == "review":
            review[folder] += 1
            continue
        if c == "unknown":
            unknown[folder] += 1
            continue
        md5 = hashlib.md5(data).hexdigest()
        if md5 in seen_md5:
            exact_dupes += 1
            first = items[seen_md5[md5]]
            # with --from-manifest: if THIS copy is the one listed in the manifest, it replaces the earlier copy
            if not (fixed is not None and (source, "/".join(parts)) in fixed
                    and (first["source"], first["orig_path"]) not in fixed):
                continue
            first["drop"] = "duplicate_of:" + source + "/" + "/".join(parts)
        try:
            sq = to_square(Image.open(io.BytesIO(data)), args.size)
        except Exception:
            unreadable += 1
            continue
        seen_md5[md5] = len(items)
        h, t = fingerprint(sq)
        label, group, weight = c
        path = "/".join(parts)
        items.append({"source": source, "orig_path": path, "label": label, "group": group, "weight": weight,
                      "v1": bench.get((source, path), ""), "md5": md5})
        hashes.append(h)
        thumbs.append(t)
    if not items:
        raise SystemExit("No images found. Put dataset zips in ml/datasets/raw/ or raw_external/ (docs/DATASET_GUIDE.md).")
    print(f"  {len(items)} candidate images, finding near-duplicates (also across datasets)...", flush=True)

    # ---- near-duplicates: union groups, keep the best copy of each
    pairs = find_duplicates(np.stack(hashes), np.stack(thumbs))
    parent = list(range(len(items)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i, j, _, _ in pairs:
        parent[root(i)] = root(j)
    clusters = defaultdict(list)
    for i in range(len(items)):
        clusters[root(i)].append(i)
    removed_dupes, conflicts, cross_dataset = [], [], 0
    for members in clusters.values():
        if len(members) == 1:
            continue
        labels = {items[i]["label"] for i in members}
        # keep: benchmark-test copy first, then own, then by dataset priority
        # (with --from-manifest, the copy listed in the manifest always wins, so a saved dataset can be rebuilt exactly)
        members.sort(key=lambda i: (fixed is not None and (items[i]["source"], items[i]["orig_path"]) not in fixed,
                                    items[i]["v1"] != "test", PRIORITY.get(items[i]["source"], 9)))
        if len({items[i]["source"] for i in members}) > 1:
            cross_dataset += 1
        listed = fixed is not None and any((items[i]["source"], items[i]["orig_path"]) in fixed for i in members)
        if len(labels) > 1 and not listed and not any(items[i]["v1"] == "test" or items[i]["source"] == "own"
                                                      for i in members):
            conflicts.append([items[i]["orig_path"] for i in members])   # same photo, different labels: drop all
            for i in members:
                items[i]["drop"] = "label_conflict"
            continue
        for i in members[1:]:
            items[i]["drop"] = "duplicate_of:" + items[members[0]]["source"] + "/" + items[members[0]]["orig_path"]
            removed_dupes.append(i)
    pool = [it for it in items if "drop" not in it]

    # ---- select per class, balanced by subtype group, benchmark test forced into test
    selected = []
    if fixed is not None:                      # reproduce a saved dataset exactly
        for it in pool:
            split = fixed.get((it["source"], it["orig_path"]))
            if split:
                it["split"] = split
                selected.append(it)
        missing = len(fixed) - len(selected)
        print(f"  from manifest: {len(selected)} images found, {missing} missing", flush=True)
    for label in sorted({it["label"] for it in pool}) if fixed is None else []:
        own = [it for it in pool if it["label"] == label and it["source"] == "own"]
        public = [it for it in pool if it["label"] == label and it["source"] != "own"]
        forced_test = [it for it in public if it["v1"] == "test"]
        rest = [it for it in public if it["v1"] != "test"]
        by_group = defaultdict(list)
        for it in rest:
            by_group[it["group"]].append(it)
        weights = {g: by_group[g][0]["weight"] for g in by_group}
        alloc = allocate({g: len(v) for g, v in by_group.items()}, weights, max(0, args.target - len(forced_test)))
        chosen = []
        for g, k in alloc.items():
            rng.shuffle(by_group[g])
            # v1-train photos first (they are already known to be fine), then new ones
            by_group[g].sort(key=lambda it: it["v1"] != "train")
            chosen += by_group[g][:k]
        # test split: the benchmark photos + enough NEW photos (from every group) to reach the test fraction
        n_test_total = round((len(chosen) + len(forced_test)) * args.test)
        new = [it for it in chosen if it["v1"] == ""]
        extra = max(0, n_test_total - len(forced_test))
        q = min(1.0, extra / len(new)) if new else 0
        new_by_group = defaultdict(list)
        for it in new:
            new_by_group[it["group"]].append(it)
        for g, members in new_by_group.items():
            rng.shuffle(members)
            for k, it in enumerate(members):
                it["split"] = "test" if k < round(len(members) * q) else "train"
        for it in chosen:
            it.setdefault("split", "train")        # v1-train photos stay in train
        for it in forced_test:
            it["split"] = "test"
        rng.shuffle(own)
        n_own_test = max(1, round(len(own) * args.test)) if len(own) > 1 else 0
        for k, it in enumerate(own):
            it["split"] = "test" if k < n_own_test else "train"
        selected += forced_test + chosen + own

    # ---- pass 2: write the selected images
    if OUT.exists():
        for f in sorted(OUT.rglob("*"), reverse=True):
            f.unlink() if f.is_file() else f.rmdir()
    want = {(it["source"], it["orig_path"]): it for it in selected}
    counters, rows = Counter(), []
    print(f"  writing {len(selected)} images...", flush=True)
    for source, parts, data in iter_source_images():
        it = want.get((source, "/".join(parts)))
        if it is None or it.get("written") or hashlib.md5(data).hexdigest() != it["md5"]:
            continue
        it["written"] = True
        img = to_square(Image.open(io.BytesIO(data)), args.size)
        folder = OUT / it["split"] / it["label"]
        folder.mkdir(parents=True, exist_ok=True)
        key = (it["split"], it["label"], it["source"])
        name = f"{it['label']}.{it['source']}_{counters[key]:04d}.jpg"
        counters[key] += 1
        img.save(folder / name, "JPEG", quality=90)
        rows.append({"file": f"{it['split']}/{it['label']}/{name}", "label": it["label"],
                     "bin": BIN_OF.get(it["label"], "none"), "source": it["source"], "subtype": it["group"],
                     "split": it["split"], "benchmark_v1": it["v1"] or "-", "orig_path": it["orig_path"],
                     "license": SOURCES.get(it["source"], {}).get("license", "own photo" if it["source"] == "own" else "?")})
    rows.sort(key=lambda r: r["file"])
    with open(OUT / "manifest.csv", "w", newline="", encoding="utf8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    # ---- summary + report
    summary = {"size": args.size, "target_per_class": args.target, "bins": BIN_OF, "classes": {},
               "candidates": len(items), "exact_duplicates": exact_dupes, "near_duplicates_removed": len(removed_dupes),
               "duplicate_groups_across_datasets": cross_dataset, "label_conflicts_dropped": len(conflicts),
               "unreadable": unreadable, "skipped_folders": dict(skipped), "review_folders": dict(review),
               "unknown_folders": dict(unknown)}
    for label in sorted({r["label"] for r in rows}):
        lr = [r for r in rows if r["label"] == label]
        avail = Counter(it["group"] for it in pool if it["label"] == label)
        summary["classes"][label] = {
            "train": sum(r["split"] == "train" for r in lr), "test": sum(r["split"] == "test" for r in lr),
            "benchmark_v1_test": sum(r["benchmark_v1"] == "test" for r in lr),
            "own_photos": sum(r["source"] == "own" for r in lr),
            "sources": dict(Counter(r["source"] for r in lr)),
            "subtypes": {g: {"used": n, "available": avail[g]} for g, n in Counter(r["subtype"] for r in lr).most_common()},
        }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf8")
    with open(OUT / "duplicates.csv", "w", newline="", encoding="utf8") as f:
        w = csv.writer(f)
        w.writerow(["removed_source", "removed_path", "kept"])
        for i in removed_dupes:
            w.writerow([items[i]["source"], items[i]["orig_path"], items[i]["drop"].split(":", 1)[1]])
        for c in conflicts:
            w.writerow(["label_conflict", " | ".join(c), "-"])

    lines = ["# Dataset integration report", "",
             f"Built by `ml/prepare_dataset.py` (seed {args.seed}, {args.size}px, target {args.target} public images per class).", "",
             "| Class | Compartment | Train | Test | of which v1 benchmark | Sources |", "|---|---|---|---|---|---|"]
    for label, c in summary["classes"].items():
        lines.append(f"| {label} | {BIN_OF.get(label)} | {c['train']} | {c['test']} | {c['benchmark_v1_test']} | "
                     + ", ".join(f"{k} {v}" for k, v in c["sources"].items()) + " |")
    lines += ["", "## Subtype groups (used / available after de-duplication)", ""]
    for label, c in summary["classes"].items():
        lines.append(f"* **{label}**: " + ", ".join(f"{g} {v['used']}/{v['available']}" for g, v in c["subtypes"].items()))
    lines += ["", "## Removed", "",
              f"* exact duplicates (same file): {exact_dupes}",
              f"* near-duplicates (same photo re-saved/resized): {len(removed_dupes)} "
              f"({cross_dataset} duplicate groups span two datasets), list in `duplicates.csv`",
              f"* same photo with different labels (dropped): {len(conflicts)}",
              f"* unreadable: {unreadable}",
              "* folders not used (not one of the 4 categories): "
              + ", ".join(f"{k} {v}" for k, v in sorted(skipped.items())),
              "* ambiguous folders left out (manual decision): " + (", ".join(f"{k} {v}" for k, v in review.items()) or "none"),
              "* unknown folders: " + (", ".join(f"{k} {v}" for k, v in unknown.most_common(10)) or "none"),
              "", "Licences: " + "; ".join(f"{k}: {v['license']}" for k, v in SOURCES.items())]
    (OUT / "integration_report.md").write_text("\n".join(lines) + "\n", encoding="utf8")

    labels_present = sorted(summary["classes"])
    bat = ["@echo off", "REM Uploads the prepared dataset to your Edge Impulse project.",
           "REM First time: npm install -g edge-impulse-cli   then   edge-impulse-uploader --clean", 'cd /d "%~dp0"']
    for split, category in (("train", "training"), ("test", "testing")):
        for label in labels_present:
            bat.append(f"call edge-impulse-uploader --category {category} --label {label} {split}\\{label}\\*.jpg")
    bat.append("pause")
    (OUT / "upload_to_edge_impulse.bat").write_text("\r\n".join(bat) + "\r\n", encoding="utf8")

    print("\n" + "\n".join(lines))
    print(f"\nNext: ml\\.venv\\Scripts\\python ml\\train_mobilenet.py   or upload with {OUT / 'upload_to_edge_impulse.bat'}")


if __name__ == "__main__":
    main()
