"""Real-world accuracy of the AI, measured from detections that a person reviewed on the dashboard.

Public datasets give a "lab" accuracy; this is the accuracy INSIDE the real bin, with its camera,
light and waste. It is the honest number for the project report.
"""

from collections import Counter

from ..models import BIN_OF, INORGANIC, MATERIALS

LABELS = [m for m, _ in MATERIALS] + ["other"]


def quality(detections):
    """detections: queryset/list of reviewed Detection objects (true_label set)."""
    rows = [(d.label, d.true_label, d.sorted_to) for d in detections if d.true_label]
    n = len(rows)
    if not n:
        return {"reviewed": 0, "accuracy": None, "compartment_accuracy": None,
                "labels": LABELS, "confusion": [], "mistakes": []}

    correct = sum(1 for pred, true, _ in rows if pred == true)
    right_bin = sum(1 for _, true, sorted_to in rows if BIN_OF.get(true, INORGANIC) == sorted_to)
    index = {label: i for i, label in enumerate(LABELS)}
    confusion = [[0] * len(LABELS) for _ in LABELS]          # rows = real material, columns = AI prediction
    for pred, true, _ in rows:
        if true in index and pred in index:
            confusion[index[true]][index[pred]] += 1
    mistakes = Counter((true, pred) for pred, true, _ in rows if pred != true).most_common(5)

    return {
        "reviewed": n,
        "correct": correct,
        "accuracy": round(correct / n, 3),
        "compartment_accuracy": round(right_bin / n, 3),
        "labels": LABELS,
        "confusion": confusion,
        "mistakes": [{"true": t, "predicted": p, "count": c} for (t, p), c in mistakes],
    }
