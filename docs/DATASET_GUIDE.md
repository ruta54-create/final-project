# Dataset & AI Guide: Edge-AI Smart Dustbin System

How the smart dustbin recognises waste, which data it learns from, how to train the model
**on a normal laptop**, how to put it on the **ESP32-S3-CAM**, and how the bin keeps getting smarter.

---

## 1. What the AI does

The camera above the tray takes one photo of each item. A small neural network (**MobileNetV2**) running
**on the ESP32-S3-CAM itself** (edge AI: no internet needed) says which of **4 materials** it is.
The material decides the compartment:

| Material the AI recognises | Examples | Compartment | Why |
|---|---|---|---|
| **organic** | food leftovers, fruit/vegetable peels, leaves, bread | **ORGANIC** | rots, compostable |
| **paper** | paper, newspaper, cardboard, paper bags | **ORGANIC** | biodegradable, can be composted or recycled with organics |
| **plastic** | bottles, bags, wrappers, cups | **INORGANIC** | does not rot |
| **metal** | drink cans, tins, bottle caps, foil | **INORGANIC** | does not rot |

Why 4 materials and not just "organic / inorganic"? Paper and food look completely different, and so do a
bottle and a can. Learning 4 *visual* classes is easier for a small network than learning 2 mixed groups,
and the dashboard can show **what kind** of waste people throw away (for recycling partners).

**Safety rule:** if the AI is less than 70 % sure (setting *Minimum AI confidence*), the item goes to
**inorganic**. Plastic in the compost is much worse than a peel in the inorganic bin.

---

## 2. How the whole system works, step by step

```
 1. Hand near the lid ─────────▶ lid opens (ultrasonic sensor), item dropped on the tray
 2. IR sensor sees the item ───▶ main ESP32 closes the lid (steady light) and sends "CAPTURE" to the camera
 3. ESP32-S3-CAM ──────────────▶ LED ring on, photo 320×240, centre crop → 96×96 (or 128×128)
 4. MobileNetV2 (int8) ────────▶ scores: organic 0.06 · paper 0.88 · plastic 0.04 · metal 0.02
 5. Decision ──────────────────▶ paper (88 % ≥ 70 %) → ORGANIC compartment   (unsure → INORGANIC)
 6. Camera answers "SORT organic 0.880" over UART ─▶ main ESP32 tilts the tray (servo), item falls
 7. Camera uploads photo + result to Django ───────▶ dashboard shows it within 3 s
 8. Ultrasonic sensors measure both compartments every 30 s ─▶ fill level, prediction, email when full
 9. A cleaner checks the photo on the dashboard: ✓ correct, or "it was plastic"   ("teach the AI")
10. Checked photos are exported and added to the dataset ─▶ retrain ─▶ new, better model on the camera
```

Steps 9–10 are the **continuous-learning loop**: the bin collects its own training data while it is used.

---

## 3. The datasets

Public datasets give the AI a good start. Your own photos (section 5) make it work *in your bin*.

| Dataset | Images | Classes we use → our label | Classes skipped | Look of the photos | License |
|---|---|---|---|---|---|
| **RealWaste** (UCI ML Repository, 2023) | 4,752 | Cardboard, Paper → **paper** · Food Organics, Vegetation → **organic** · Plastic → **plastic** · Metal → **metal** | Glass, Textile Trash, Miscellaneous Trash | real waste from a landfill, 524×524, varied backgrounds | CC BY 4.0 |
| **TrashNet / "Garbage Classification"** (Thung & Yang, Stanford 2016) | 2,527 | cardboard, paper → **paper** · plastic → **plastic** · metal → **metal** | glass, trash | one object on a white board, 512×384 | MIT |
| *Optional:* **Garbage Classification 12 classes** (Kaggle, mostafaabla) | 15,150 | biological → **organic** · cardboard, paper · plastic · metal | glass, clothes, shoes, battery, trash | web photos | ODbL |

Download links:
* RealWaste: https://archive.ics.uci.edu/dataset/908/realwaste → *Download* (`realwaste.zip`, 690 MB)
* TrashNet: https://huggingface.co/datasets/garythung/trashnet → `dataset-resized.zip` (43 MB)
* Kaggle 12 classes (needs a free Kaggle account): https://www.kaggle.com/datasets/mostafaabla/garbage-classification

Put the zip files in **`ml/datasets/raw/`**. You don't need to unzip them.

**Please cite** in your report:
* S. Single, S. Iranmanesh, R. Raad, "RealWaste: A Novel Real-Life Data Set for Landfill Waste Classification
  Using Deep Learning", *Information*, 14(12), 633, 2023.
* G. Thung, M. Yang, "Classification of Trash for Recyclability Status", CS229 project report, Stanford, 2016.

### What we actually used (after cleaning)

`ml/prepare_dataset.py` centre-crops every photo to a square, removes duplicates, and balances the classes:

| Class | Compartment | Training | Test | Sources |
|---|---|---|---|---|
| organic | organic | 675 | 169 | RealWaste 844 (TrashNet has no food) |
| paper | organic | 720 | 180 | TrashNet 470 · RealWaste 430 |
| plastic | inorganic | 720 | 180 | RealWaste 597 · TrashNet 303 |
| metal | inorganic | 720 | 180 | RealWaste 603 · TrashNet 297 |
| **total** | | **2,835** | **709** | 57 duplicates removed; 1,871 glass/textile/trash images skipped |

The **test set is never used for training**, so its accuracy is an honest estimate.

---

## 4. Prepare the dataset

```powershell
# one time: Python 3.12 environment for machine learning (TensorFlow does not support 3.14 yet)
py -3.12 -m venv ml\.venv
ml\.venv\Scripts\python -m pip install -r ml\requirements.txt

# every time the photos change
ml\.venv\Scripts\python ml\prepare_dataset.py          # options: --size 160 --per-class 900
```

What it does:
1. Reads every image in `ml/datasets/raw/*.zip` (also zips inside zips) and `ml/datasets/own/<label>/`.
2. Maps folder names to our 4 labels (`CLASS_MAP` in the script; add a line to support another dataset).
3. Removes exact duplicates (MD5) and near-duplicates (perceptual hash).
4. **Centre-crops to a square and resizes**, exactly like the camera firmware does before the AI runs
   (`crop_and_interpolate_rgb888`). Training and the camera then see images framed the same way.
5. Balances the public photos (max 900 per class). **Your own photos are always kept.**
6. Splits 80 % training / 20 % test, separately for public and own photos.
7. Writes `ml/datasets/processed/` with `train/`, `test/`, `manifest.csv`, `summary.json`, and
   `upload_to_edge_impulse.bat`. File names start with the label (`plastic.realwaste_0012.jpg`), which is
   what Edge Impulse expects.

---

## 5. Your own photos: the most important part

Public photos are taken in other light, on other backgrounds, by other cameras. Inside your bin the
camera sees one item on **your tray**, under **your LED ring**. This difference (the *domain gap*) is the
main reason a model that scores 85 % on public data can score much less in the bin. A few hundred photos
from your own camera close most of the gap.

**How many:** start with **50 per class**, aim for **200+ per class**.
**How to take them**, choose one:

* **A. Through the dashboard (easiest, and it keeps improving):** put items on the tray as normal
  (*Control Panel → Capture & classify*, or just use the bin). On **Detections**, press **Correct** or choose
  what the item really was. Then **Download checked photos (ZIP)** and unzip it into `ml/datasets/own/`.
* **B. Edge Impulse data acquisition:** flash the Edge Impulse ESP32 firmware, open *Data acquisition*,
  and take photos with the label set.

**Tips:** use real local waste (banana peels, maize husks, sachets, water bottles, Fanta/Primus cans,
newspaper, cement-bag paper). Vary position, rotation, how crumpled it is, dry or wet, and the amount.
Keep the lid closed and the LED on, exactly like in use.
**Optional 5th class `background`:** 50 photos of the **empty tray**. The camera then answers
`EMPTY` instead of guessing when the IR sensor triggers by mistake, and the firmware already handles it.

---

## 6. Train the model

### Option A: on your laptop (what was used for this project)

```powershell
ml\.venv\Scripts\python ml\train_mobilenet.py               # 128×128 (default, best for ESP32-S3), ~15 min
ml\.venv\Scripts\python ml\train_mobilenet.py --size 96     # faster on a classic ESP32-CAM, ~7 min, less accurate
```

Designed for an **Intel Core i5-3427U, 2 cores, 8 GB RAM, no GPU**:

| Choice | Why it fits a small laptop and a small chip |
|---|---|
| **MobileNetV2, width 0.35** | 415k parameters (ResNet50 has 25 million): trains on a CPU, 600 KB as int8 |
| **Transfer learning** from ImageNet | the network already knows edges, textures and shapes; only the top is taught "waste" |
| **Phase 1**: new head only (base frozen) | ~35 s (96 px) / ~70 s (128 px) per epoch on the i5; reaches ~80 % |
| **Phase 2**: fine-tune the top 40 layers, learning rate 1e-4 | adapts the features to waste, +3–5 % |
| **BatchNorm kept frozen** | stable training with a few thousand images |
| **Augmentation**: flips, ±15° rotation, zoom, shift, brightness/contrast ±25 % | imitates the camera's variation, reduces overfitting |
| **Class weights** | organic has fewer photos but counts the same |
| **Early stopping** on validation accuracy | stops before overfitting, keeps the best epoch |
| **Full-integer (int8) quantisation**, 1,000 calibration images | 4× smaller and much faster on the ESP32 than float |
| Pixel scaling **inside** the model | the ESP32 feeds raw 0–255 pixels, so there is nothing to get wrong in C++ |

Outputs in `ml/output/`:

| File | Use |
|---|---|
| `model_int8.tflite` | the model for the ESP32 (upload to Edge Impulse, section 7) |
| `model_data.h` | the same model as a C array, for TensorFlow Lite Micro without Edge Impulse |
| `labels.txt` | class order |
| `metrics.json`, `MODEL_CARD.md` | all numbers for the report |
| `confusion_matrix.png`, `training_curves.png` | figures for the report |

### Option B: in Edge Impulse Studio (cloud training, no load on the laptop)

1. Create a project at https://studio.edgeimpulse.com.
2. `npm install -g edge-impulse-cli`, then double-click
   `ml\datasets\processed\upload_to_edge_impulse.bat` (log in the first time).
3. **Create impulse:** Image data **128×128** (or 96×96 for a classic ESP32-CAM), *Resize mode: Fit shortest axis* →
   **Image** block (RGB) → **Transfer Learning (Images)** block.
4. **Image:** colour depth RGB → *Generate features*.
5. **Transfer learning:** model **MobileNetV2 0.35** (128×128 input), 30–40 cycles, learning rate 0.0005,
   *Data augmentation* on → *Start training*.
6. **Model testing** → *Classify all*. Compare with the laptop results.

---

## 7. Put the model on the ESP32-S3-CAM

> **No hardware yet?** Test the model on the dashboard: **Test the AI** page (sample photos, upload or webcam).
> Step-by-step Edge Impulse instructions with the exact settings: **[EDGE_IMPULSE.md](EDGE_IMPULSE.md)**.

1. **Edge Impulse → Deployment → Arduino library**, *Quantized (int8)*, EON Compiler on → *Build*.
   (With Option A, first go to **Dashboard → Upload model** (BYOM), upload `model_int8.tflite`,
   input *Image 96×96 (or 128) RGB*, input scaling **0..255**, output *Classification* with the
   labels from `labels.txt`.)
2. Arduino IDE → *Sketch → Include Library → Add .ZIP Library*.
3. In `device/esp32_cam/esp32_cam.ino`, change the first `#include` to your library's header.
4. In `device/esp32_cam/camera_pins.h`, select your board:
   * `BOARD_ESP32S3_CAM`: ESP32-S3-CAM / Freenove ESP32-S3 (recommended, 8 MB PSRAM, AI 2–3× faster)
   * `BOARD_XIAO_ESP32S3`: Seeed XIAO ESP32S3 Sense
   * `BOARD_AI_THINKER`: classic ESP32-CAM
5. Tools: *ESP32S3 Dev Module*, **PSRAM: OPI PSRAM**, *Partition: Huge APP*, then Upload.
6. Serial Monitor (115200) shows for every item:
   `paper (organic) 88%  [2nd: plastic 7%]  310 ms -> organic`.

| | ESP32-S3 (240 MHz, vector instructions) | ESP32 (classic) |
|---|---|---|
| 96×96 MobileNetV2 0.35 int8 | about 0.2–0.4 s | about 0.8–1.2 s |
| 128×128 | about 0.4–0.7 s | about 1.5–2 s |
| RAM needed | ~350 KB (PSRAM) | ~350 KB (PSRAM) |

These are typical figures. Edge Impulse shows the exact estimate for your model before you deploy.
Either way, sorting takes less than the 3 s target.

> ⚠️ On ESP32-S3 boards **GPIO 4 is the camera's data line**. The old sketch used GPIO 4 for the flash
> LED (correct only on the AI-Thinker). The light pin now comes from `camera_pins.h`.

---

## 8. Results

Trained on the project laptop (Intel Core i5-3427U, 2 cores, 8 GB RAM, no GPU). Test set: **709 photos
never seen during training**. Full details: `ml/output/MODEL_CARD.md`, `ml/output/metrics.json`.

| Model | Training time | Size | Material correct (int8) | **Correct compartment (int8)** |
|---|---|---|---|---|
| MobileNetV2 0.35, **96×96**, 300 calibration images | 7 min | 609 KB | 77.9 % | 88.3 % |
| MobileNetV2 0.35, **128×128**, 1,000 calibration images (**chosen**) | 15 min | 609 KB | **83.8 %** | **90.5 %** |

The float32 version of the chosen model scores 85.5 % / 91.0 %, so int8 compression costs only 1.7 points.
The first run lost 5.9 points, because 300 unshuffled calibration images did not cover all classes.

| Class (128×128, int8) | Precision | Recall | F1 |
|---|---|---|---|
| organic | 0.94 | 0.96 | 0.95 |
| paper | 0.88 | 0.76 | 0.81 |
| plastic | 0.79 | 0.77 | 0.78 |
| metal | 0.76 | 0.87 | 0.81 |

![Confusion matrix](../ml/output/confusion_matrix.png)

![Training curves](../ml/output/training_curves.png)

These numbers come from **public photos**. Inside your bin, expect lower accuracy at first, until the
teach-the-AI loop (section 9) adds your own photos. Measure it on *Analytics → AI accuracy in the real bin*.

**How to read the confusion:**
* **Plastic ↔ metal** is the most common mistake (shiny bottles look like cans at 96 pixels). It does
  **not** affect sorting: both go to the inorganic compartment. That's why *correct compartment* is much
  higher than *correct material*.
* **Paper ↔ plastic** is the mistake that matters (it crosses compartments). White plastic bags and paper
  look alike. Add your own photos of both (section 5).
* **Organic** is recognised best: food has unique colours and textures.

### Verify it yourself in Google Colab

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ruta54-create/final-project/blob/main/ml/verify_model_colab.ipynb)

`ml/verify_model_colab.ipynb` downloads this repository and tests the **same int8 file** that goes on the ESP32.
Open it, then *Runtime → Run all* (about 3 minutes, no GPU). Result of the last run:

| Check | Result |
|---|---|
| Model health (int8, 128×128, labels, 609 KB) | PASS |
| Only TensorFlow Lite Micro operations (67 ops, 7 kinds) | PASS |
| Material accuracy, 709 test photos | 84.8 % (model card 83.8 %) |
| Right compartment | 91.3 % |
| Plastic/metal ending up in the compost (with the 70 % rule) | 0.8 % |
| Darker, brighter, blur, rotation, low JPEG quality | compartment ≥ 85.5 % in all: PASS |
| Item small in the picture | 79.7 %: **WARNING**. Mount the camera so one item fills the picture. |
| Speed on a PC | about 3 ms per photo |
| **Verdict** | **14 passed, 1 warning, 0 failed: model verified** |

The last cells let you upload your own photos or use the webcam.

---

## 9. The "teach the AI" loop (new feature)

| Where | What happens |
|---|---|
| **Detections** page | Under every photo: *Was the AI right?* → **Correct**, or choose the real material. Filters **To review** and **AI mistakes**. |
| **Analytics** page | **AI accuracy in the real bin**: share of items in the right compartment and with the right material, a confusion matrix from real use, and the most common mistakes. This is the honest number for the report. |
| **Detections → Download checked photos (ZIP)** (administrators) | Photos sorted into `organic/ paper/ plastic/ metal/` folders, ready for `ml/datasets/own/`. |
| `prepare_dataset.py` + `train_mobilenet.py` | retrain with public + own photos → upload the new model → change `MODEL_VERSION` in the firmware. The dashboard shows which model version made each decision. |

A good routine: review ~20 items a day for two weeks, then retrain. Compare the "AI accuracy in the real
bin" before and after. That before/after comparison is strong evidence for your report.

---

## 10. Checklist to improve accuracy

1. **Own photos** (section 5): the biggest gain.
2. **Constant light:** closed inspection box, white LED ring, matte white tray.
3. **128×128 input** if plastic/metal or paper/plastic confusion is high and the ESP32-S3 is fast enough.
4. **`background` class** against false triggers.
5. **More fine-tuning layers** (`--fine-tune-layers 60`) once you have 300+ own photos per class.
6. **Check the mistakes** (*AI mistakes* filter). Are they blurry, dark, or two items at once? Fix the mechanics first.
7. **Raise *Minimum AI confidence*** (e.g. 0.8) if compost contamination matters more than inorganic volume.

## 11. Troubleshooting

| Problem | Fix |
|---|---|
| `pip install tensorflow` fails | use Python **3.12** (`py -3.12 -m venv ml\.venv`); TensorFlow has no wheels for 3.14 |
| Training is very slow | close Chrome and other programs; use `--size 96`; one epoch ≈ 35 s on an i5-3427U |
| `No images found` | zips must be in `ml/datasets/raw/`; your own photos in `ml/datasets/own/<label>/` |
| A new dataset is ignored | its folder names are printed as "not recognised": add them to `CLASS_MAP` |
| ESP32: "Camera init failed" | wrong board in `camera_pins.h`, or PSRAM not enabled |
| ESP32: everything is "inorganic" | confidence below the minimum: retrain with own photos, check the light |
| Edge Impulse BYOM: wrong predictions | input scaling must be **0..255** (scaling is inside our model) |
