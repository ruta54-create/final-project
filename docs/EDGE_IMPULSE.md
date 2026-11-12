# Putting the model in Edge Impulse

**Can the model go into Edge Impulse? Yes.** `ml/output/model_int8.tflite` is a standard
TensorFlow Lite model, fully quantised to int8, with one image input and one classification output.
That's exactly the format Edge Impulse accepts with **"Bring your own model" (BYOM)**. Edge Impulse then:
* shows how much **RAM, flash and time** it needs on your chip (ESP32-S3) before you buy anything,
* lets you **test it with photos** in the browser,
* builds the **Arduino library** that `device/esp32_cam/esp32_cam.ino` uses.

There are two ways. **Use A** to put this exact model (the one tested on the dashboard) in Edge Impulse.
Use B only if you also want Edge Impulse to train its own version for comparison.

---

## A. Upload this model (Bring your own model)

**What you need:** a free Edge Impulse account (https://studio.edgeimpulse.com) and these 2 files:

| File | What it is |
|---|---|
| `ml/output/model_int8.tflite` | the model (609 KB) |
| `ml/output/labels.txt` | the class order: `organic, paper, plastic, metal` |

**Steps**
1. Edge Impulse Studio → **Create new project** → name it `edge-ai-smart-dustbin`.
2. On the project **Dashboard**, choose **Upload your model** (Bring your own model).
3. **Upload** `model_int8.tflite`. When asked, say the model is **quantized (int8)**.
4. **Model configuration**: enter exactly these values:

| Setting | Value | Why |
|---|---|---|
| Model input | **Image** | |
| Input size | **128 × 128**, **RGB** | the model was trained at 128×128 (see `ml/output/metrics.json`) |
| Input scaling | **Pixels ranging 0..255 (not normalized)** | the scaling to -1..1 is *inside* our model; choosing another option gives wrong answers |
| Resize mode | **Fit shortest axis** (centre crop) | the same crop as training and the dashboard test page |
| Model output | **Classification** | |
| Output labels | `organic, paper, plastic, metal` | **this order**, from `labels.txt` |

5. **Check model behaviour**: upload 2–3 photos (for example `frontend/public/samples/*.jpg`). The answers should
   match the dashboard's *Test the AI* page.
6. **Target device** (top right) → **Espressif ESP-EYE (ESP32-S3)** or the closest ESP32-S3 entry. Edge Impulse then
   shows the estimated **inference time, RAM and flash**. Write these numbers in your report.
7. **Deployment** → **Arduino library** → *Quantized (int8)* → EON Compiler **on** → **Build** → you get a `.zip`.
8. Arduino IDE → *Sketch → Include Library → Add .ZIP Library* → choose that zip.
9. In `esp32_cam.ino`, change the first line to the library's header, for example
   `#include <edge-ai-smart-dustbin_inferencing.h>`.

> On the camera, `crop_and_interpolate_rgb888` crops the centre square and resizes it to 128×128, the
> same preparation the model was trained with. You don't need to change anything else in the sketch.

## B. Let Edge Impulse train its own model (optional comparison)

1. `npm install -g edge-impulse-cli`
2. Double-click `ml\datasets\processed\upload_to_edge_impulse.bat` (created by `prepare_dataset.py`; the first
   time it asks you to log in and choose the project). It uploads the 2,835 training and 709 test photos with labels.
3. **Create impulse**: Image data **128×128**, *Fit shortest axis* → **Image** (RGB) → **Transfer learning (Images)**.
4. **Transfer learning**: **MobileNetV2 0.35**, 30–40 training cycles, learning rate 0.0005, data augmentation on.
5. **Model testing** → *Classify all*, then compare with `ml/output/MODEL_CARD.md` (our model: 83.8 % material,
   90.5 % correct compartment, int8).
6. With a phone you can also use **Live classification**: scan the QR code under *Devices → Connect a new device →
   Use your mobile phone* and point the phone at real waste.

## Testing before you buy the hardware

| Where | How | What it shows |
|---|---|---|
| **Dashboard → Test the AI** | sample photos, upload, or the laptop webcam | the exact int8 model + the bin's rules (compartment, 70 % safety rule); "Send to the bin" puts the result on the dashboard |
| Edge Impulse → Check model behaviour / Model testing | upload photos | the same model inside Edge Impulse; proves the upload settings are right |
| Edge Impulse → Target device | choose ESP32-S3 | expected speed and memory on the real chip |

If the dashboard and Edge Impulse give different answers for the same photo, the **input scaling** or the
**label order** in step 4 is wrong.

## Notes

* Edge Impulse's menus change from time to time. If a button has moved, search the Edge Impulse docs for
  "Bring your own model". The settings in the table above stay the same.
* BYOM and Arduino library export were available on the free Developer plan when this guide was written.
* After retraining (`ml/train_mobilenet.py`), upload the new `model_int8.tflite` the same way and change
  `MODEL_VERSION` in `esp32_cam.ino`.
