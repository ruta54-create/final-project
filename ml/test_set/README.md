# Held-out test set (709 photos)

The photos the waste model was **tested** on and **never trained** on, exactly as produced by
`ml/prepare_dataset.py` (centre-cropped, 160×160 JPEG). Used by `ml/verify_model_colab.ipynb`
so anyone can reproduce the reported accuracy.

| Folder | Photos | Compartment |
|---|---|---|
| organic | 169 | organic |
| paper | 180 | organic |
| plastic | 180 | inorganic |
| metal | 180 | inorganic |

File names show the source dataset (`realwaste_…` or `trashnetresized_…`).

**Credits / licences**
* RealWaste: S. Single, S. Iranmanesh, R. Raad, *Information* 14(12):633, 2023. UCI Machine Learning Repository, **CC BY 4.0**.
* TrashNet: G. Thung, M. Yang, Stanford CS229, 2016. **MIT licence**.
Images were resized and cropped.
