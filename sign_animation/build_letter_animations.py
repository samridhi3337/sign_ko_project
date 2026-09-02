"""
Extracts one static hand-shape frame per letter (A-Z) for the
fingerspelling fallback in Text -> Sign Animation -- real MediaPipe
Hands landmarks from the SAME source image alphabet/prepare_assets.py
already uses for the alphabet dictionary thumbnails, so the avatar's
fingerspelled letters match what's shown elsewhere in the app.

Fingerspelling genuinely is a sequence of held letter shapes (not
continuous motion), so a single static frame per letter is accurate,
not a shortcut.

Usage:
    python sign_animation/build_letter_animations.py
"""

import csv
import json
import os

import cv2

import config
from landmarks3d import make_hands

AVATAR_HAND_HEIGHT_UNITS = 0.22  # a hand is roughly this tall relative
                                  # to config.AVATAR_HEIGHT_UNITS (1.7)

WRIST, MIDDLE_MCP = 0, 9


def load_rows(csv_path):
    with open(csv_path, newline="") as f:
        return list(csv.DictReader(f))


def remap_hand_points(points):
    wrist = points[WRIST]
    middle_mcp = points[MIDDLE_MCP]

    hand_len = ((wrist[0] - middle_mcp[0]) ** 2 + (wrist[1] - middle_mcp[1]) ** 2) ** 0.5
    hand_len = max(hand_len, 1e-4)
    scale = AVATAR_HAND_HEIGHT_UNITS / hand_len

    out = []
    for p in points:
        x = (p[0] - wrist[0]) * scale
        y = -(p[1] - wrist[1]) * scale
        z = -(p[2] - wrist[2]) * scale
        out.append([round(x, 4), round(y, 4), round(z, 4)])
    return out


def main():
    os.makedirs(config.LETTERS_DIR, exist_ok=True)

    rows = load_rows(config.ALPHABET_LABELS_CSV)
    by_letter = {}
    for row in rows:
        by_letter.setdefault(row["label"], []).append(row)

    hands_detector = make_hands(static_image_mode=True)

    written = []
    missing = []

    for letter in config.LETTERS:
        candidates = by_letter.get(letter, [])
        saved = False

        for row in candidates[:10]:
            src = os.path.join(config.ALPHABET_DATASET_SOURCE, row["filepath"])
            image = cv2.imread(src)
            if image is None:
                continue

            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            result = hands_detector.process(rgb)
            if not result.multi_hand_landmarks:
                continue

            hand = result.multi_hand_landmarks[0]
            points = [[lm.x, lm.y, lm.z] for lm in hand.landmark]
            remapped = remap_hand_points(points)

            out_path = os.path.join(config.LETTERS_DIR, f"{letter}.json")
            with open(out_path, "w") as f:
                json.dump({"letter": letter, "hand": remapped}, f)

            written.append(letter)
            saved = True
            break

        if not saved:
            missing.append(letter)

    hands_detector.close()

    print(f"Wrote {len(written)}/{len(config.LETTERS)} letter animation files "
          f"-> {config.LETTERS_DIR}")
    if missing:
        print(f"WARNING: no usable hand detected for: {missing}")


if __name__ == "__main__":
    main()
