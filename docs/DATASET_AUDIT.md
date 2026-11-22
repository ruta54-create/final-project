# Dataset Audit & Integration Plan (Section 3.1)

*Audit date: 21 November 2026.*

> **Update, 21 Nov 2026: integration v2 done (approved by the project owner).**
> * **King** (Kaggle) was downloaded. The download was cut off at 505 of 965 MB, so the 8,747 complete images were
>   recovered (all folders up to *plastic soda bottles*). Each folder was checked by eye: office paper, magazines,
>   coffee grounds and aerosol cans were **excluded** (photos mostly not the object). King contained
>   1,164 identical and 565 near-identical repeats, which were removed.
> * **GD v2** was downloaded completely (1.15 GB). Its cardboard folder is ≈⅓ drink cartons, so it was not used.
>   Its food photos (v3, two runs: 82.8 % / 84.1 %) and its paper/plastic/metal photos (v4: 82.4 %) were **tested and
>   rejected**: both lowered accuracy on the 709-photo benchmark compared with v2 (86.6 % / 84.5 %, two runs),
>   mainly plastic recall. Full table: [DATASET_GUIDE.md](DATASET_GUIDE.md) section 3.
> * `prepare_dataset.py` now does what section D describes: subtype balancing, a better duplicate check
>   (23 genuine duplicates removed in RealWaste/TrashNet instead of 57 mostly wrong ones), provenance, and the
>   v1 benchmark kept in the test set. Result: **4,746 training / 1,185 test images**.
> * **Retrained model (v2)**, same size (609 KB) and 23 min on the laptop: on the same 709 photos the first
>   model was tested on, **86.6 % material / 92.8 % compartment** (v1: 83.8 % / 90.5 %). Paper recall rose from 76 % to 86 %.
>   See [DATASET_GUIDE.md](DATASET_GUIDE.md) section 8.
> * Still missing (no public data, must be photographed): mango peels, local leftovers, exercise books, local
>   bottle and can brands, bottle caps, and above all photos from the bin's own camera (section E5).
>
> The text below is the original audit, written before any download.

This report re-examines the datasets already downloaded for the Smart Dustbin, compares them with other
public datasets, and decides what still has to be photographed. It covers the four sorting categories:
**Organic, Paper, Plastic, Metal**. (Paper stays its own class even though it shares the organic
compartment. Biodegradable paper is **not** merged into Organic.)

### How it was checked (what is verified and what is not)

| Check | Method | Coverage |
|---|---|---|
| Inventory, labels, counts, size, format | `ml/audit_datasets.py` reads every image in both raw zips (read-only) | **all 7,279 images** |
| Which images reached training | the script replays `prepare_dataset.py` (same seed). 40 random replayed images were compared pixel by pixel with `ml/datasets/processed/`: all match (difference ≤ 3.5 grey levels = JPEG re-save) | **all images** |
| Duplicates | exact (MD5) + perceptual hash, then a **visual check of all 57 removed pairs** (`duplicate_pairs.jpg`) | all |
| Quality (dark, bright, blurry, low contrast, low resolution) | automatic measurements | all |
| Subtypes (banana peel, cans, bottles…) | **visual review of a random sample of 96 images per class** (`contact_sheets/*.jpg`). Percentages below are **estimates from that sample**, not exact counts. An ImageNet classifier was also tried; it was too unreliable for waste (it labels food scraps as "slug" or "dung beetle"), so it was **not** used for conclusions | 96 per class, 12 sheets |
| External datasets | official pages read on 21 Nov 2026 (Kaggle through a browser, Mendeley, GitHub, arXiv, Roboflow). **None downloaded.** Image contents of external sets have therefore **not** been inspected yet | page facts only |

Reproduce: `ml\.venv\Scripts\python ml\audit_datasets.py` → `ml/datasets/audit/` (`inventory.csv` has one row per
original image with its source path, status and quality flags; `audit_summary.json`; `contact_sheets/`;
`duplicate_pairs.jpg`). The audit folder is git-ignored like the rest of `ml/datasets/`.

---

## A. The previously downloaded datasets

Only **two** datasets were ever downloaded (both still intact in `ml/datasets/raw/`, unchanged).
The optional Kaggle "12 classes" set mentioned in `DATASET_GUIDE.md` was **never downloaded**.
No other waste datasets were found on this computer (Downloads folder checked).

| Dataset | File | Images | Format | License |
|---|---|---|---|---|
| RealWaste (UCI, Single et al. 2023) | `realwaste.zip` (689 MB) | 4,752 | 524×524 JPEG, all identical size | CC BY 4.0 |
| TrashNet "dataset-resized" (Thung & Yang 2016) | `trashnet-resized.zip` (43 MB) | 2,527 | 512×384 JPEG, all identical size | MIT |

### A1. Where every image went

| Original class | Images | → our label | Trained / tested | **Downloaded but never used** | Removed as "duplicate" |
|---|---|---|---|---|---|
| RealWaste Food Organics | 411 | organic | 323 / 85 | 0 | 3 |
| RealWaste Vegetation | 436 | organic | 352 / 84 | 0 | 0 |
| RealWaste Paper | 500 | paper | 180 / 50 | **270** | 0 |
| RealWaste Cardboard | 461 | paper | 159 / 41 | **260** | 1 |
| TrashNet paper | 594 | paper | 236 / 49 | **296** | 13 |
| TrashNet cardboard | 403 | paper | 145 / 40 | **217** | 1 |
| RealWaste Plastic | 921 | plastic | 472 / 125 | **310** | 14 |
| TrashNet plastic | 482 | plastic | 248 / 55 | **172** | 7 |
| RealWaste Metal | 790 | metal | 481 / 122 | **180** | 7 |
| TrashNet metal | 410 | metal | 239 / 58 | **102** | 11 |
| RealWaste Glass / Textile / Misc. Trash | 420 / 318 / 495 | not used | n/a | n/a | n/a |
| TrashNet glass / trash | 501 / 137 | not used | n/a | n/a | n/a |

**Answer to E1, "what useful images already exist":** **1,807 good, correctly-labelled images were downloaded but never
trained on** (paper 1,043 · plastic 482 · metal 282). The 900-per-class cap in `prepare_dataset.py`
threw them away at random, without looking at what kind of object they were. **Organic is the only class
where everything was already used.**

### A2. Problems found

1. **The duplicate filter removed good images.** `prepare_dataset.py` compares an 8×8 "average hash".
   With one small object on a plain background, many *different* photos get the same hash. On visual
   review of all 57 removed pairs, only **about 12 are real duplicates** (for example TrashNet `paper294`/`paper58`/`paper539`,
   `metal148`/`metal152`, RealWaste `Food Organics_81`/`_82`, `Plastic_216`/`_217`). The other ~45 were different
   objects, and **23 "pairs" even had different labels** (e.g. a plastic tray "duplicate" of crumpled foil).
   No cross-dataset duplicates exist between RealWaste and TrashNet (3 hash matches, none real on inspection).
   16 more near-identical pairs (same 64-bit dHash) were *not* caught and are flagged `same_dhash_as:` in `inventory.csv`.
2. **Provenance is lost.** `manifest.csv` records only `realwaste`/`trashnetresized`, not the original
   file name, so a training image cannot be traced back. (`inventory.csv` now provides that mapping.)
3. **Quality:** no images are dark, over-exposed, blurry or low-resolution by the thresholds used. 28 used images
   have low contrast (mostly transparent plastic on a white background). They are hard but **valid**, so keep them.
4. **Possible wrong labels (need a manual pass):** in the RealWaste *Cardboard* sample, about 10 of 96 look like
   glossy **plastic or foil-laminated snack wrappers**, not cardboard. A few in RealWaste *Paper* also look like this. In the TrashNet
   *metal* sample, 2–3 metallised **plastic** wrappers appear. Beverage cartons (Tetra Pak, which is paper + plastic + foil)
   are labelled cardboard. Decide one rule for them (recommendation: exclude, since they are ambiguous for this bin).
5. **Irrelevant for a tray camera:** heaps of **soil / compost** (about 6% of RealWaste *Vegetation*) and large
   piles of grass clippings that would not fit on the tray.
6. **Useful images hidden in skipped classes:** TrashNet *trash* (137) contains **clear plastic bags and zip bags (~17)**
   and **snack wrappers (~45)**, which are both plastic and both almost missing from our Plastic class, plus 2 apple cores (organic).
   RealWaste *Miscellaneous Trash* is genuinely mixed (cloths, toys, ceramics, pens, wipes): correctly excluded.

### A3. What each class really contains (sample of 96 images per source class, estimated)

| Class | Dominant subtypes | Thin or missing |
|---|---|---|
| **Organic** (844 used) | **52% garden waste** (grass, leaves, twigs, soil) · food 48%: whole/cut fruit & vegetables, lettuce/cabbage, bread & biscuits, mixed scraps | banana peel ~6% of food, citrus peel ~3%, **mango peel 0**, cooked food leftovers (rice, beans, ugali, matoke) rare, avocado skins few |
| **Paper** (900 used) | TrashNet: **flyers/adverts ~50%, envelopes ~35%** · RealWaste: printed sheets, flyers, tissue; cardboard: **printed cereal/food boxes ~60%**, corrugated ~20% | **exercise books & notebook pages ~0**, newspaper ~5–10%, paper bags ~3%, cement/sugar sacks 0, egg trays few |
| **Plastic** (900 used) | RealWaste: **food trays/clamshells ~40%**, bottles ~25% (incl. detergent, milk jugs), caps ~8% · TrashNet: **clear water bottles ~45%, clamshells ~40%** | **plastic bags ~3%**, soft-drink bottles (Fanta/Coke style, coloured) few, juice bottles few, sachets/wrappers few |
| **Metal** (900 used) | RealWaste: **drink cans ~30%, foil ~20%, aerosol cans ~15%**, food tins ~10%, wire/misc ~10% · TrashNet: food tins ~40%, foil ~30%, drink cans ~25% | **bottle caps ~2%**, local can brands 0 |

**Answer to E4, "which categories are dominated by one kind of object":**
* **Organic is half garden waste.** A dustbin mostly receives food. The model learned "green, leafy, on concrete" as organic.
* **Paper (TrashNet half) is mostly adverts and envelopes**, with almost no notebooks or newspaper.
* **Plastic is mostly rigid containers and clear water bottles.** Bags, wrappers and coloured soda bottles are rare.
* **Metal is cans, foil and aerosols.** Aerosols (~15% of RealWaste metal) are rare in a household bin in Rwanda.
* **Background bias in every class:** RealWaste is always grey or blue concrete in daylight; TrashNet is always a white board. Neither looks like the bin tray under the LED ring.

---

## B/C. Additional public datasets (verified pages, not downloaded)

Facts come from the pages listed in the *Source* column, read on 21 Nov 2026. "n/s" = not stated on the page.

| # | Dataset & link | Classes (relevant → our label) | Images | Format | License (as shown) | Fit for this project |
|---|---|---|---|---|---|---|
| 1 | **Recyclable and Household Waste Classification**, A. King. [kaggle.com/datasets/alistairking/recyclable-and-household-waste-classification](https://www.kaggle.com/datasets/alistairking/recyclable-and-household-waste-classification) | 30 item folders. Data card names: plastic water bottles, soda bottles, detergent bottles, shopping bags, trash bags, food containers → **plastic**; newspaper, office paper, magazines, cardboard boxes, cardboard packaging → **paper**; aluminium soda cans, aluminium food cans, steel food cans, aerosol cans → **metal**; food waste, eggshells, coffee grounds, tea bags → **organic**; glass, clothing, shoes → excluded | 15,000 (500 per folder: 250 `default` studio + 250 `real_world`) | 256×256 PNG | Kaggle field: **MIT**; data card text: *"available for educational, research, and non-commercial purposes"*, cite the author | **Best match.** Folders *are* the subtypes we lack (soda bottles, shopping bags, newspaper, soda cans, food tins, food waste) and have a real-world half. Limits: low resolution, some web-style images, no mango peels or notebooks. Exact folder list to be confirmed after download |
| 2 | **Garbage Dataset (GD) v2**, S. Kunwar. [kaggle.com/datasets/sumn2u/garbage-classification-v2](https://www.kaggle.com/datasets/sumn2u/garbage-classification-v2), paper [arXiv:2602.10500](https://arxiv.org/abs/2602.10500) | biological 699 → **organic**; paper 1,336 + cardboard 1,411 → **paper**; plastic 1,597 → **plastic**; metal 930 → **metal**; battery, glass, trash, shoes, clothes → excluded | 13,348 (~1.3 GB) | JPEG, varied sizes (+ 256/384 standardised copies) | **MIT** (Kaggle) | Good volume, varied real backgrounds (floors, ground, tables). **Partly web-scraped and drawn from public repositories**, so overlap with TrashNet is likely and must be deduplicated. Subtypes are not labelled |
| 3 | **Garbage Classification (12 classes)**, M. Abla. [kaggle.com/datasets/mostafaabla/garbage-classification](https://www.kaggle.com/datasets/mostafaabla/garbage-classification) | biological → organic; paper, cardboard, plastic, metal; 3 glass, battery, clothes, shoes, trash excluded | 15,150 total (per-class n/s on page) | n/s | *"Database: Open Database, Contents: © Original Authors"* | **Low priority.** The page says ~29% comes from a Kaggle copy of TrashNet (**duplicates**) and the rest is **web-scraped**, with image copyright staying with the photographers. Use at most its *biological* class |
| 4 | **TrashNet++ / WasteVision**, Daffodil Intl. Univ. [data.mendeley.com/datasets/mr67c82zw7/2](https://data.mendeley.com/datasets/mr67c82zw7/2) | Plastic, Metal, **Can**, (Glass, Cable, E-waste, Medical excluded) | 2,600 images / 8,320 boxes | 640×640 JPEG, YOLO boxes | **CC BY 4.0** | Real waste photographed in **Bangladesh** (closer to Rwandan conditions than US/Australia). It is a *detection* set, so objects must be cropped from boxes first. Per-class counts n/s |
| 5 | **TACO**, Proença & Simões. [github.com/pedropro/TACO](https://github.com/pedropro/TACO) | Can, Bottle, Plastic bag, carton, paper… (crop from segmentation masks) | n/s on README (to check on its stats page) | varied, COCO masks | MIT (GitHub sidebar) | Litter "in the wild" (roads, beaches). Good for **plastic bags, cans, bottles** after cropping. Objects are often tiny and dirty. Medium priority |
| 6 | **Waste Classification Dataset** (Nnamoko et al., restructured Kaggle "techsash"). [data.mendeley.com/datasets/n3gtgm9jxj/3](https://data.mendeley.com/datasets/n3gtgm9jxj/3) | organic 13,880 → organic *after review*; recyclable 10,825 → **cannot be mapped** (paper, plastic and metal mixed) | 24,705 | JPEG, small | **CC BY 4.0** | Only the *organic* half is usable, and only after manual screening (web images, mixed quality). Use to diversify food leftovers if (1) and (2) are not enough |
| 7 | **NexTech14_Waste_Dataset**. [data.mendeley.com/datasets/p6hgv27jh4](https://data.mendeley.com/datasets/p6hgv27jh4) | food-waste, garden-waste, other-organic → organic; paper; plastic; metal; (battery, e-waste, glass, textile, trash excluded) | 8,996 total (per-class n/s) | 224×224 JPG/PNG | **CC BY-NC 4.0** (non-commercial; OK for a university project) | Separate *food-waste* vs *garden-waste* folders help fix the organic imbalance. Collected in Bangladesh (by affiliation). Medium priority |
| 8 | **EcoShreds**. [data.mendeley.com/datasets/9n25xjfjcz](https://data.mendeley.com/datasets/9n25xjfjcz) | 5 classes, **names not stated** on the page | 2,057 | n/s | **CC BY 4.0** | Built for **ESP32-CAM** smart bins, from KNUST, Ghana. Worth opening once its file list is visible. Unknown fit |

**Rejected after checking the page:**
* **FruitVision** ([Mendeley xkbjx8959c](https://data.mendeley.com/datasets/xkbjx8959c/2)): whole fresh or rotten fruit, not peels, and **CC BY-NC-ND** forbids derivatives.
* **Roboflow "Waste Items"** ([link](https://universe.roboflow.com/ipcvwastedetection/waste-items)): has banana-peel labels but only **53 images**.
* **Hugging Face 4w4kt/waste-dataset-image** ([link](https://huggingface.co/datasets/4w4kt/waste-dataset-image)): no license stated, and it is merged from 7 Kaggle sets including #2, so it is all duplicates.
* No public dataset was found with **mango peels**, **exercise books or notebook pages**, **Rwandan products** (Inyange bottles, local soda brands, sachets), or **African kitchen leftovers**.

---

## D. Integration strategy (to run **only after your approval**)

1. **Originals stay untouched** in `ml/datasets/raw/` (zips are read-only inputs). New downloads go to
   `ml/datasets/raw_external/<dataset>/`, also never modified.
2. **Working copy:** `ml/datasets/working/<label>/<subtype>/` holds copies, never moves.
3. **Class map with subtypes.** Each source folder maps to `label/subtype`, e.g.
   `plastic_soda_bottles → plastic/soda_bottle`, `aluminum_soda_cans → metal/drink_can`,
   `RealWaste Vegetation → organic/garden`. **Ambiguous folders go to `review/`** for a manual decision:
   paper cups (plastic-lined), beverage cartons, snack wrappers, tea bags, aerosol cans, styrofoam, tissues.
   Paper always stays **paper**, never organic.
4. **Better duplicate removal:** 16×16 perceptual hash, compared **only within the same label**, plus a visual check
   of each flagged pair. This replaces the 8×8 hash that removed ~45 good images. Cross-dataset dedup is
   mandatory for GD v2 and the Kaggle 12-class set (both contain TrashNet-derived images).
5. **Standardise exactly like the camera:** RGB, centre-crop square, 160 px, JPEG q90 (as now).
6. **Balance by subtype, not by class total:** cap each subtype (e.g. ≤ 150 per subtype), so the
   garden-waste or envelope share can no longer dominate a class.
7. **Provenance:** `manifest.csv` gains `orig_dataset, orig_path, orig_class, subtype, license`.
8. **Test set:** keep the current 709-image test set as "old benchmark", and add a **separate test set of own bin
   photos**. That is the honest measure of performance in the real bin.
9. **Report:** the script writes `integration_report.json/.md` (counts per source, label, subtype; removed images and why).

---

## E. Final decision before collecting new images

**E1. Useful images that already exist:** 1,807 unused but valid images (paper 1,043 · plastic 482 · metal 282),
~45 wrongly-removed "duplicates", and ~17 plastic bags + ~45 wrappers in TrashNet *trash* (after manual review).
Organic has **no** spare images. All of it was used.

**E2. Suitable public datasets:** **#1 King (first choice)**, **#2 GD v2** (after dedup), then **#7 NexTech14**
(food vs garden split) and **#4 TrashNet++** (crops). #5 TACO, #6 Mendeley organic and #8 EcoShreds are optional.
#3 only for its biological class.

**E3. Subtypes still missing after integration** (public data does not cover them): mango peels, local food leftovers
(rice, beans, ugali, matoke and cassava peels, avocado skins), exercise books and notebook pages, local newspapers, cement/sugar paper
sacks, Rwandan bottle brands (Inyange water and juice, Fanta/Coca-Cola from local bottlers), sachets, local can brands, and bottle caps.
Above all, **any photo taken by your own camera on your tray under the LED ring.**

**E4. Over-represented single types:** Organic = garden waste (52%). Paper = adverts and envelopes. Plastic = clamshells and clear
water bottles. Metal = cans, foil and aerosols. All public images use concrete or white-board backgrounds.

**E5. How many to collect yourself** (with the bin's ESP32-S3-CAM, tray, lid closed, LED on, varied position and crumpling):

| Class | Subtype | Photos | | Class | Subtype | Photos |
|---|---|---|---|---|---|---|
| Organic | banana peels | 60 | | Plastic | water bottles (local brands) | 50 |
| Organic | orange / citrus peels | 50 | | Plastic | Fanta / soda bottles | 60 |
| Organic | **mango peels** | 60 | | Plastic | juice bottles | 40 |
| Organic | vegetable scraps (cabbage, tomato, onion, cassava/matoke peels) | 60 | | Plastic | bags & sachets | 60 |
| Organic | cooked leftovers (rice, beans, ugali, bread) | 60 | | Plastic | containers / packaging | 40 |
| Organic | leaves / avocado skins / eggshells | 40 | | Metal | soft-drink cans | 50 |
| Paper | **exercise books & notebook pages** | 70 | | Metal | food tins | 50 |
| Paper | newspaper | 40 | | Metal | **bottle caps** | 60 |
| Paper | cardboard (boxes, egg trays) | 40 | | Metal | other (foil, lids) | 30 |
| Paper | paper bags / sacks / packaging | 50 | | **Background** | empty tray (optional 5th class) | 50 |

**Total ≈ 1,110 photos** (≈ 330 organic, 200 paper, 250 plastic, 190 metal, 50 empty tray). The minimum to start is
**30 per subtype** (≈ 560). The dashboard's "teach the AI" loop then adds more while the bin is in use.

**E6. Exclude:**
* All glass, textile, clothes, shoes, battery, e-waste and mixed-trash classes (not in the 4 categories).
* Soil and compost heaps, and grass piles too large for the tray.
* The ~12 genuine duplicates.
* Snack wrappers and beverage cartons inside *Cardboard*, *Paper* and *Metal*: move them after review (wrappers → plastic) or drop them (cartons).
* Any external image without a clear license, and FruitVision (no derivatives allowed).
* Do **not** exclude the 28 low-contrast transparent-plastic images; they are valid hard examples.

**E7. Recommended final structure**

```
ml/datasets/
  raw/                    originals (unchanged): realwaste.zip, trashnet-resized.zip
  raw_external/           new downloads, unchanged (after approval)
  own/<label>/<subtype>/  your bin photos (never capped, never deduplicated against public data)
  review/                 ambiguous images waiting for a manual decision
  working/<label>/<subtype>/   merged, deduplicated working copy
  processed/train|test/<label>/   final 160 px set + manifest.csv (with provenance)
  audit/                  this audit's outputs
labels: organic (food, peel, vegetable, leftovers, garden) · paper (notebook, newspaper, office, cardboard, bag)
        plastic (water_bottle, soda_bottle, juice_bottle, bag_sachet, container, packaging, cap)
        metal (drink_can, food_tin, bottle_cap, foil, other)        [+ optional background]
```

Target after integration: **about 1,200–1,500 images per class**, no subtype above ~150 public images, plus your own photos.

---

### Approval needed

Nothing has been downloaded, merged, or changed in the training set. Choose what to do next:
1. Download **#1 King** and **#2 GD v2** (needs a free Kaggle account, about 3 GB) into `raw_external/` and inspect their real contents.
2. Fix `prepare_dataset.py` (duplicate filter, subtype balancing, provenance) and recover the 1,807 unused + ~45 wrongly-removed images.
3. Manually review the `review/` candidates (wrappers, bags, cartons).

### References
* Single, Iranmanesh, Raad, "RealWaste…", *Information* 14(12):633, 2023. UCI ML Repository, CC BY 4.0.
* Thung & Yang, "Classification of Trash for Recyclability Status", Stanford CS229, 2016. MIT.
* King, A., Recyclable and Household Waste Classification, Kaggle (link above).
* Kunwar, S., "The Garbage Dataset (GD)…", arXiv:2602.10500, 2026.
* Abla, M., Garbage Classification (12 classes), Kaggle.
* Al Noman et al., TrashNet++ / WasteVision, Mendeley Data, DOI 10.17632/mr67c82zw7.2.
* Proença & Simões, "TACO: Trash Annotations in Context", arXiv:2003.06975.
* Nnamoko, Barrowclough, Procter, Waste Classification Dataset, Mendeley Data, DOI 10.17632/n3gtgm9jxj.3.
* Salam et al., NexTech14_Waste_Dataset, Mendeley Data, DOI 10.17632/p6hgv27jh4.1.
* Owusu Agyei, R., EcoShreds, Mendeley Data, DOI 10.17632/9n25xjfjcz.1.
