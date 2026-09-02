"""
Generates a static reference image per vocabulary word for the
Text-to-Sign feature (static/sign_images/<Word>.jpg), using a real
frame extracted from an actual downloaded WLASL clip -- not a
fabricated image. Fills in words that never had a reference photo
(e.g. "You", "Please", "Doctor", ...) while leaving any existing
hand-picked images (Hello.jpg, Help.jpg, etc.) untouched.

Usage:
    python word_level/build_sign_images.py
"""

import glob
import os

import cv2

import config

STATIC_SIGN_IMAGES_DIR = os.path.join(
    os.path.dirname(config.BASE_DIR), "static", "sign_images"
)


def pick_frame(video_path):
    cap = cv2.VideoCapture(video_path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    target = max(total // 2, 0)

    frame = None
    idx = 0
    while True:
        ret, f = cap.read()
        if not ret:
            break
        if idx == target:
            frame = f
        idx += 1
    cap.release()
    return frame


def main():
    os.makedirs(STATIC_SIGN_IMAGES_DIR, exist_ok=True)

    created = []
    skipped_existing = []
    skipped_no_clip = []

    for word in config.VOCAB:
        if " " in word:
            # Text-to-Sign matches single whitespace-split tokens, so a
            # multi-word gloss like "thank you" can't be reached that
            # way -- skip generating an image for it.
            continue

        dest_name = word.capitalize() + ".jpg"
        dest_path = os.path.join(STATIC_SIGN_IMAGES_DIR, dest_name)

        if os.path.exists(dest_path):
            skipped_existing.append(dest_name)
            continue

        word_key = word.replace(" ", "_")
        clips = sorted(glob.glob(os.path.join(config.WLASL_RAW_DIR, word_key, "*.mp4")))
        if not clips:
            skipped_no_clip.append(word)
            continue

        frame = pick_frame(clips[0])
        if frame is None:
            skipped_no_clip.append(word)
            continue

        cv2.imwrite(dest_path, frame)
        created.append(dest_name)

    print(f"Created ({len(created)}): {created}")
    print(f"Already existed, left untouched ({len(skipped_existing)}): {skipped_existing}")
    print(f"No clip available ({len(skipped_no_clip)}): {skipped_no_clip}")


if __name__ == "__main__":
    main()
