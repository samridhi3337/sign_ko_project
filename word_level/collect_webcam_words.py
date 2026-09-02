"""
OPTIONAL: record extra word/phrase clips yourself with your webcam to
supplement the real WLASL clips (useful for words WLASL has very few
samples of, or to add a brand-new word to config.VOCAB).

This mirrors the interactive style of the existing collect_data.py:
you run it locally (it needs a real camera + display, so it must be
run on your own machine, not in an automated/headless environment).

Controls:
    R      start/stop recording the current clip
    N      move to the next word in config.VOCAB
    P      move to the previous word
    ESC    quit

Clips are saved to word_level/webcam_raw/<word>/clip_<n>.mp4, in the
same directory layout extract_features.py already scans, so simply
re-running extract_features.py + train_word_model.py afterwards will
fold them into training.

Usage:
    python word_level/collect_webcam_words.py
"""

import os
import time

import cv2

import config

CLIP_SECONDS = 2.0   # ~ typical WLASL clip length


def next_clip_index(word_dir):
    if not os.path.isdir(word_dir):
        return 0
    existing = [f for f in os.listdir(word_dir) if f.startswith("clip_")]
    return len(existing)


def main():
    os.makedirs(config.WEBCAM_RAW_DIR, exist_ok=True)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise SystemExit("Could not open webcam.")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    word_idx = 0
    recording = False
    writer = None
    record_start = None

    print("Controls: R = start/stop recording | N = next word | P = previous word | ESC = quit")

    while True:
        word = config.VOCAB[word_idx]
        word_key = word.replace(" ", "_")
        word_dir = os.path.join(config.WEBCAM_RAW_DIR, word_key)

        ret, frame = cap.read()
        if not ret:
            print("Camera error")
            break

        frame = cv2.flip(frame, 1)
        display = frame.copy()

        cv2.putText(display, f"Word: {word}", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        if recording:
            elapsed = time.time() - record_start
            cv2.circle(display, (30, 80), 10, (0, 0, 255), -1)
            cv2.putText(display, f"REC {elapsed:.1f}s", (50, 88),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            writer.write(frame)

            if elapsed >= CLIP_SECONDS:
                writer.release()
                writer = None
                recording = False
                print(f"Saved clip for '{word}'")

        cv2.imshow("Collect Word Clips", display)

        key = cv2.waitKey(1) & 0xFF

        if key == 27:
            break
        elif key == ord('n'):
            word_idx = (word_idx + 1) % len(config.VOCAB)
        elif key == ord('p'):
            word_idx = (word_idx - 1) % len(config.VOCAB)
        elif key == ord('r'):
            if not recording:
                os.makedirs(word_dir, exist_ok=True)
                idx = next_clip_index(word_dir)
                out_path = os.path.join(word_dir, f"clip_{idx}.mp4")
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                writer = cv2.VideoWriter(out_path, fourcc, fps, (width, height))
                recording = True
                record_start = time.time()
                print(f"Recording -> {out_path}")
            else:
                writer.release()
                writer = None
                recording = False
                print(f"Stopped early, saved clip for '{word}'")

    if writer is not None:
        writer.release()
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
