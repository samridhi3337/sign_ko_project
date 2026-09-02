"""
Generates the small, project-local display assets derived from the
external alphabet dataset (config.DATASET_SOURCE):

  static/alphabet_images/<LETTER>.jpg        - one clean hand-sign image
  static/alphabet_expressions/<LETTER>.jpg   - one face crop (HUD overlay
                                                removed) showing the
                                                user's own captured
                                                expression for that letter

Nothing from the source dataset's 85,800 images is bulk-copied into
the project -- only these 52 derived thumbnails.

Usage:
    python alphabet/prepare_assets.py
"""

import csv
import os
import shutil

import cv2
import mediapipe as mp

import config

mp_face = mp.solutions.face_detection


def load_rows(csv_path):
    with open(csv_path, newline="") as f:
        return list(csv.DictReader(f))


def build_hand_images():
    os.makedirs(config.ALPHABET_IMAGES_DIR, exist_ok=True)
    rows = load_rows(config.LABELS_CSV)

    by_letter = {}
    for row in rows:
        by_letter.setdefault(row["label"], []).append(row)

    created = []
    for letter in config.LETTERS:
        candidates = by_letter.get(letter)
        if not candidates:
            print(f"[hand] {letter}: no source rows found")
            continue

        src = os.path.join(config.DATASET_SOURCE, candidates[0]["filepath"])
        dest = os.path.join(config.ALPHABET_IMAGES_DIR, f"{letter}.jpg")

        if not os.path.exists(src):
            print(f"[hand] {letter}: source file missing ({src})")
            continue

        shutil.copyfile(src, dest)
        created.append(letter)

    print(f"[hand] wrote {len(created)}/{len(config.LETTERS)} images -> {config.ALPHABET_IMAGES_DIR}")


# The capture tool burns a HUD across the top (class/emotion/progress
# text) and a control caption across the bottom of every
# personal_capture frame. Keep the crop's top/bottom edges inside
# those bands regardless of where the detected face box sits, so
# caption text never leaks into the saved thumbnail.
HUD_BAND_HEIGHT = 100
FOOTER_BAND_HEIGHT = 40


def crop_face(image, detection, pad_ratio=0.35, bottom_pad_ratio=0.7):
    h, w = image.shape[:2]
    box = detection.location_data.relative_bounding_box

    x1 = int(max(box.xmin, 0) * w)
    y1 = int(max(box.ymin, 0) * h)
    bw = int(box.width * w)
    bh = int(box.height * h)

    pad_x = int(bw * pad_ratio)
    pad_top = int(bh * pad_ratio)
    pad_bottom = int(bh * bottom_pad_ratio)

    x1 = max(x1 - pad_x, 0)
    y1 = max(y1 - pad_top, HUD_BAND_HEIGHT)
    x2 = min(x1 + bw + 2 * pad_x, w)
    y2 = min(y1 + bh + pad_top + pad_bottom, h - FOOTER_BAND_HEIGHT)

    return image[y1:y2, x1:x2]


def build_expression_images():
    os.makedirs(config.ALPHABET_EXPRESSIONS_DIR, exist_ok=True)
    rows = load_rows(config.PERSONAL_CAPTURES_CSV)

    by_letter = {}
    for row in rows:
        by_letter.setdefault(row["label"], []).append(row)

    detector = mp_face.FaceDetection(model_selection=1, min_detection_confidence=0.5)

    created = []
    no_face = []

    for letter in config.LETTERS:
        candidates = by_letter.get(letter, [])
        if not candidates:
            print(f"[face] {letter}: no source rows found")
            continue

        # Prefer the default emotion, then fall back to whatever exists.
        preferred = [r for r in candidates if r["emotion"] == config.DEFAULT_EXPRESSION_EMOTION]
        ordered = preferred + [r for r in candidates if r not in preferred]

        dest = os.path.join(config.ALPHABET_EXPRESSIONS_DIR, f"{letter}.jpg")
        saved = False

        for row in ordered[:15]:  # try a handful of frames before giving up
            src = os.path.join(config.DATASET_SOURCE, row["filepath"])
            image = cv2.imread(src)
            if image is None:
                continue

            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            result = detector.process(rgb)
            if not result.detections:
                continue

            face_crop = crop_face(image, result.detections[0])
            if face_crop.size == 0:
                continue

            cv2.imwrite(dest, face_crop)
            created.append(letter)
            saved = True
            break

        if not saved:
            no_face.append(letter)

    detector.close()

    print(f"[face] wrote {len(created)}/{len(config.LETTERS)} expression crops -> {config.ALPHABET_EXPRESSIONS_DIR}")
    if no_face:
        print(f"[face] no face detected in any candidate frame for: {no_face}")


if __name__ == "__main__":
    build_hand_images()
    build_expression_images()
