# Model card: Edge-AI Smart Dustbin waste classifier

* Model: MobileNetV2 alpha=0.35, input 128x128 RGB, transfer learning from ImageNet
* Classes: organic, paper, plastic, metal  →  organic compartment: organic + paper; inorganic: plastic + metal
* Training images: 4082 (+15 % validation), test images: 1198 (never seen in training)
* int8 TFLite size: 609 KB, 415,332 parameters
* Trained on a laptop CPU in 21.8 min

| Metric (test set) | float32 | int8 (on the ESP32) |
|---|---|---|
| Accuracy, 4 classes | 83.6% | 81.0% |
| Correct compartment | 90.6% | 87.6% |
| Accuracy on the v1 benchmark (709 photos the first model was tested on) | 85.2% | 82.8% |

| Class | Precision | Recall | F1 | Test images |
|---|---|---|---|---|
| organic | 0.85 | 0.96 | 0.90 | 299 |
| paper | 0.74 | 0.85 | 0.79 | 299 |
| plastic | 0.84 | 0.64 | 0.73 | 300 |
| metal | 0.82 | 0.79 | 0.81 | 300 |

![Confusion matrix](confusion_matrix.png)

![Training curves](training_curves.png)

**Data:** see `ml/datasets/processed/integration_report.md` (sources, subtypes, licences). **Limits:** trained mostly on public photos. Accuracy inside the real bin depends on adding your own ESP32 photos (see docs/DATASET_GUIDE.md, section 5) and retraining.
