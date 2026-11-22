# Model card: Edge-AI Smart Dustbin waste classifier

* Model: MobileNetV2 alpha=0.35, input 128x128 RGB, transfer learning from ImageNet
* Classes: organic, paper, plastic, metal  →  organic compartment: organic + paper; inorganic: plastic + metal
* Training images: 4082 (+15 % validation), test images: 1198 (never seen in training)
* int8 TFLite size: 609 KB, 415,332 parameters
* Trained on a laptop CPU in 14.0 min

| Metric (test set) | float32 | int8 (on the ESP32) |
|---|---|---|
| Accuracy, 4 classes | 86.1% | 83.6% |
| Correct compartment | 91.6% | 89.1% |
| Accuracy on the v1 benchmark (709 photos the first model was tested on) | 86.7% | 84.1% |

| Class | Precision | Recall | F1 | Test images |
|---|---|---|---|---|
| organic | 0.92 | 0.95 | 0.94 | 299 |
| paper | 0.75 | 0.88 | 0.81 | 299 |
| plastic | 0.82 | 0.71 | 0.76 | 300 |
| metal | 0.86 | 0.80 | 0.83 | 300 |

![Confusion matrix](confusion_matrix.png)

![Training curves](training_curves.png)

**Data:** see `ml/datasets/processed/integration_report.md` (sources, subtypes, licences). **Limits:** trained mostly on public photos. Accuracy inside the real bin depends on adding your own ESP32 photos (see docs/DATASET_GUIDE.md, section 5) and retraining.
