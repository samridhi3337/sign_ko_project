"""
Builds the training dataset (X.npy / y.npy / labels.json) for the
alphabet hand-shape classifier: runs MediaPipe Hands over a sample of
the clean images/<LETTER>/ subset (config.MAX_TRAIN_IMAGES_PER_LETTER
per letter) from the external dataset, using the exact same
single-frame landmark normalization as the project's original
create_dataset.py, so the alphabet classifier follows the same
architecture as the rest of the codebase.

Usage:
    python alphabet/extract_features.py
"""

import csv
import json
import os

import cv2
import mediapipe as mp
import numpy as np

import config

mp_hands = mp.solutions.hands


def load_rows(csv_path):
    with open(csv_path, newline="") as f:
        return list(csv.DictReader(f))


def extract_landmarks(image, hands):
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    result = hands.process(rgb)

    if not result.multi_hand_landmarks:
        return None

    hand = result.multi_hand_landmarks[0]

    features = []
    base_x = hand.landmark[0].x
    base_y = hand.landmark[0].y

    for lm in hand.landmark:
        features.append(lm.x - base_x)
        features.append(lm.y - base_y)

    max_value = max(max(abs(v) for v in features), 1e-6)
    return [v / max_value for v in features]


def main():
    os.makedirs(config.DATA_DIR, exist_ok=True)

    rows = load_rows(config.LABELS_CSV)
    by_letter = {}
    for row in rows:
        by_letter.setdefault(row["label"], []).append(row)

    hands = mp_hands.Hands(
        static_image_mode=True,
        max_num_hands=1,
        min_detection_confidence=0.5,
    )

    X, y = [], []
    per_letter_used = {}
    per_letter_no_hand = {}

    for letter in config.LETTERS:
        candidates = by_letter.get(letter, [])[: config.MAX_TRAIN_IMAGES_PER_LETTER]
        if not candidates:
            print(f"[{letter}] no source rows found")
            continue

        used = 0
        no_hand = 0

        for row in candidates:
            src = os.path.join(config.DATASET_SOURCE, row["filepath"])
            image = cv2.imread(src)
            if image is None:
                continue

            feats = extract_landmarks(image, hands)
            if feats is None:
                no_hand += 1
                continue

            X.append(feats)
            y.append(letter)
            used += 1

        per_letter_used[letter] = used
        per_letter_no_hand[letter] = no_hand
        print(f"[{letter}] used {used}/{len(candidates)} (no hand detected in {no_hand})")

    hands.close()

    if not X:
        raise SystemExit("No usable samples extracted -- check config.DATASET_SOURCE.")

    X = np.array(X, dtype=np.float32)
    labels_sorted = sorted(set(y))
    label_to_idx = {label: i for i, label in enumerate(labels_sorted)}
    y_idx = np.array([label_to_idx[label] for label in y], dtype=np.int64)

    np.save(config.X_PATH, X)
    np.save(config.Y_PATH, y_idx)
    with open(config.LABELS_PATH, "w") as f:
        json.dump(labels_sorted, f, indent=2)

    print("\n==============================")
    print(f"X shape: {X.shape}")
    print(f"y shape: {y_idx.shape}")
    print(f"Classes ({len(labels_sorted)}): {labels_sorted}")
    print(f"Per-letter used: {per_letter_used}")
    print(f"Saved -> {config.X_PATH}, {config.Y_PATH}, {config.LABELS_PATH}")
    print("==============================")


if __name__ == "__main__":
    main()
