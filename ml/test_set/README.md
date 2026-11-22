# Held-out test set (1,185 photos), dataset v2

The photos the waste model was **tested** on and **never trained** on, exactly as produced by
`ml/prepare_dataset.py` (centre-cropped, 160×160 JPEG). Used by `ml/verify_model_colab.ipynb`
so anyone can reproduce the reported accuracy.

| Folder | Photos | of which v1 benchmark | Compartment |
|---|---|---|---|
| organic | 286 | 169 | organic |
| paper | 299 | 180 | organic |
| plastic | 300 | 180 | inorganic |
| metal | 300 | 180 | inorganic |

* **v1 benchmark** = the 709 photos the first model (v1) was tested on (`benchmark_v1` column in `manifest.csv`).
  Both models can be compared on exactly these photos.
* `manifest.csv` gives, for every photo, the source dataset, subtype, **original file** and licence.
* File names show the source dataset (`realwaste_…`, `trashnetresized_…` or `king_…`).

**Credits / licences**
* RealWaste: S. Single, S. Iranmanesh, R. Raad, *Information* 14(12):633, 2023. UCI Machine Learning Repository, **CC BY 4.0**.
* TrashNet: G. Thung, M. Yang, Stanford CS229, 2016. **MIT licence**.
* Recyclable and Household Waste Classification: A. King, Kaggle. Kaggle licence field **MIT**; the data card asks
  for educational, research and non-commercial use, with citation.
Images were resized and cropped.
