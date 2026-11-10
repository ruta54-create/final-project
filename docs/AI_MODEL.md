# AI & Analytics

The system uses three kinds of intelligence:

| Part | Where it runs | Technique |
|---|---|---|
| **Waste classification** (organic / inorganic) | on the ESP32-CAM (edge) | Convolutional neural network (MobileNetV1/V2 transfer learning) trained in Edge Impulse, int8-quantised |
| **Time-to-full prediction** | Django server | Least-squares linear regression on fill readings since the last emptying, with 7-day history fallback |
| **Recommendations** | Django server | Rule-based expert system on levels, predictions, gas, temperature and AI confidence |

## 1. Why edge AI?

* Works even when Wi-Fi is slow or down: sorting never waits for the internet.
* Fast (≈ 0.5 s on the ESP32-CAM), cheap, and private: only the result and one small photo are sent.

## 2. Dataset

Train with photos that look like what the camera will really see.

1. **Your own photos (most important):** build the inspection box first, then take **≥ 300 photos per class**
   of real campus waste on the tray, with the ESP32-CAM, the LED on and the lid closed.
   Vary position, rotation and the amount of waste. In Edge Impulse use *Data acquisition → Connect a device*
   (ESP32-CAM via the Edge Impulse firmware or your phone) or upload the JPEGs.
2. **Public data to add variety:** *Waste Classification Data* (Kaggle, `techsash/waste-classification-data`),
   which has classes **O** (organic) and **R** (recyclable/inorganic). Use a few hundred per class, not all,
   so your own photos stay important.
3. Classes (labels) **exactly**: `organic`, `inorganic`.
   (The firmware also accepts detailed labels such as `fruit_peel` or `plastic_bottle`: list the organic
   ones in `ORGANIC_LABELS` in `esp32_cam.ino`.)
4. Split 80 % training / 20 % testing (Edge Impulse does this automatically).

Organic examples: food leftovers, fruit/vegetable peels, leaves, bread, eggshells, paper tissue with food.
Inorganic examples: plastic bottles/bags/wrappers, cans, glass, paper cups (plastic coated), metal caps.

## 3. Training in Edge Impulse (studio.edgeimpulse.com)

1. **Create impulse:** Image data 96 × 96, *Fit shortest axis* → **Image** processing block (RGB) →
   **Transfer Learning (Images)** learning block.
2. **Image:** colour depth **RGB** → *Generate features*.
3. **Transfer learning:** model **MobileNetV2 96×96 0.35** (or V1 0.25 if RAM is short), 30–50 cycles,
   learning rate 0.0005, **Data augmentation: ON** → *Start training*.
4. Check the **confusion matrix** and the on-device estimate (RAM < 300 kB, latency < 1 s on ESP32).
5. **Model testing** tab → classify all test data. Target **≥ 90 % accuracy**.
6. **Deployment:** *Arduino library*, **Quantized (int8)**, EON Compiler **ON** → *Build* → download the `.zip`.
7. Arduino IDE → *Sketch → Include Library → Add .ZIP Library*. Change the first `#include` in
   `esp32_cam.ino` to the library's header name, for example `#include <smart_dustbin_inferencing.h>`.
8. Update `MODEL_VERSION` in `esp32_cam.ino` each time you retrain: the dashboard shows it.

## 4. Improving accuracy after deployment

* Dashboard → **Detections → Uncertain only** shows the items the AI was unsure about, with photos.
* Download those photos (right-click → save), add them to Edge Impulse with the right label, retrain, re-flash.
* The dashboard raises an **"AI often uncertain"** alert and a recommendation when ≥ 30 % of the last 20 items were uncertain.
* **Minimum confidence** (Settings, default 0.70): higher = fewer mistakes in compost, more items to inorganic.

## 5. Safety rule

```
if confidence >= min_confidence:  compartment = predicted category
else:                             compartment = inorganic   (item flagged "uncertain")
```
A plastic bag in the compost is much worse than a banana peel in the inorganic bin, so doubt goes to inorganic.

## 6. Fill-level measurement

```
level % = (empty_depth − measured_distance) / empty_depth × 100      (clamped 0–100)
```
`empty_depth` is measured with **Control Panel → Calibrate** while the compartment is empty.
Each telemetry value is the **median of 5** ultrasonic readings to remove spikes.

## 7. Time-to-full prediction

For each compartment (`backend/bins/services/prediction.py`):

1. Take readings since the last **collection** (or the last sudden drop > 25 %, which means the bin was emptied), max 48 h.
2. Fit `level = rate × hours + b` by least squares. `rate` = filling speed in %/hour.
3. If there are fewer than 3 points or less than 30 minutes of data → use the **average filling rate of the last 7 days**.
4. `hours_to_full = (full_level − current_level) / rate`. If `rate ≤ 0.05 %/h` the compartment is "not filling".

Example: organic at 62 %, rate 3.5 %/h, full level 90 % → (90 − 62) / 3.5 = **8 h**.

## 8. Recommendation engine

`backend/bins/services/recommendations.py`. Rules, highest priority first:

| Condition | Recommendation |
|---|---|
| no data from the controller for > 90 s | Bin is offline: check power / Wi-Fi |
| level ≥ full level | Empty the compartment now (button: *Mark as emptied*) |
| predicted full within 12 h | Schedule collection before *time* |
| gas ≥ threshold | Bad smell: empty organic within 24 h and wash it |
| temperature ≥ 32 °C | Empty organic waste more often / move to shade |
| ≥ 30 % of last 20 items uncertain | Clean lens, check LED, retrain with uncertain photos |
| ≥ 60 % of the week's waste organic | Composting opportunity / bigger organic compartment |
| ≤ 30 % organic | Partner with a recycler |
| maintenance mode on | Switch back to Automatic |
| nothing else | Everything is OK |

## 9. Evaluation for the report

* **Classification:** place 100 labelled items (50/50). Record the predicted class and where each one physically
  fell. Report accuracy, precision and recall per class, and a confusion matrix. Use the CSV export from Analytics.
* **Fill level:** compare the dashboard % with a ruler at 0, 25, 50, 75, 100 %.
* **Prediction:** note the predicted "full at" time and compare it with the real time the bin became full.
* **Latency:** item placed → item sorted (stopwatch); AI inference time is shown on the dashboard (`AI took … ms`).
