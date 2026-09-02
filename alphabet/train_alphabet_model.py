"""
Trains a RandomForest letter classifier on the landmark features built
by extract_features.py -- same shape as the project's existing
train_model.py, applied to the alphabet dataset (26 classes instead of
7 static words). Saved separately to alphabet/model/alphabet_model.pkl
-- does not touch or overwrite the original model.pkl.

IMPORTANT (see alphabet/README.md and the source dataset's own
README): these images come from continuous video, so consecutive
frames are near-duplicates. A random train/test split -- what this
script does, matching the style of the existing train_model.py --
reports optimistic accuracy versus a true signer-independent split.
Treat the printed accuracy as an upper bound, not a real-world number.

Usage:
    python alphabet/train_alphabet_model.py
"""

import json
import pickle

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split

import config


def main():
    X = np.load(config.X_PATH)
    y = np.load(config.Y_PATH)
    with open(config.LABELS_PATH) as f:
        labels = json.load(f)

    print(f"Dataset: X={X.shape}, y={y.shape}, classes={len(labels)}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = RandomForestClassifier(n_estimators=300, random_state=42)
    model.fit(X_train, y_train)

    pred = model.predict(X_test)
    acc = accuracy_score(y_test, pred)

    print(f"\nRandom-split accuracy: {acc:.4f}")
    print(
        "NOTE: this is a random split over near-duplicate video frames "
        "(see alphabet/README.md) -- treat this as optimistic, not a "
        "signer-independent number."
    )

    with open(config.MODEL_PATH, "wb") as f:
        pickle.dump({"model": model, "labels": labels}, f)

    print(f"Saved model -> {config.MODEL_PATH}")


if __name__ == "__main__":
    main()
