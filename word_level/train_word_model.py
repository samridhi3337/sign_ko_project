"""
Trains an ExtraTrees motion sequence classifier on 220-word WLASL landmark data,
capturing hand shape, finger positions, wrist rotation, movement direction, speed,
and timing over time. Saves the model bundle to word_level/model/word_model.pkl.

Usage:
    python word_level/train_word_model.py
"""

import json
import os
import pickle
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.model_selection import train_test_split

import config
from landmarks import extract_sequence_features


def main():
    X = np.load(config.X_PATH)
    y = np.load(config.Y_PATH)
    with open(config.LABELS_PATH) as f:
        labels = json.load(f)

    num_classes = len(labels)
    print(f"Dataset: X={X.shape}, y={y.shape}, classes={num_classes}")

    print("Extracting sequence motion features (hand shape, finger positions, trajectories, velocity)...")
    X_engineered = np.array([extract_sequence_features(s) for s in X], dtype=np.float32)
    print(f"Engineered feature shape: {X_engineered.shape}")

    try:
        X_train, X_val, y_train, y_val = train_test_split(
            X_engineered, y, test_size=0.15, random_state=42, stratify=y
        )
    except ValueError:
        X_train, X_val, y_train, y_val = train_test_split(
            X_engineered, y, test_size=0.15, random_state=42
        )

    print("Training ExtraTrees Motion Sequence Ensemble (300 trees)...")
    clf = ExtraTreesClassifier(n_estimators=300, random_state=42, n_jobs=-1)
    clf.fit(X_train, y_train)

    val_acc = (clf.predict(X_val) == y_val).mean()
    train_acc = (clf.predict(X_engineered) == y).mean()
    print(f"\nValidation accuracy: {val_acc*100:.2f}%")
    print(f"Overall dataset accuracy: {train_acc*100:.2f}%")

    pkl_path = os.path.join(config.MODEL_DIR, "word_model.pkl")
    with open(pkl_path, "wb") as f:
        pickle.dump({"model": clf, "labels": labels}, f)

    print(f"Saved model bundle -> {pkl_path}")
    print(f"Labels ({num_classes}) -> {config.LABELS_PATH}")


if __name__ == "__main__":
    main()
