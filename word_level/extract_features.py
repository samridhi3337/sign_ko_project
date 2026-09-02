"""
Builds the training dataset (X.npy / y.npy / labels.json) by running
MediaPipe Holistic over every downloaded clip -- both the real WLASL
clips fetched by wlasl_fetch.py (word_level/wlasl_raw/) and any extra
clips the user has recorded themselves (word_level/webcam_raw/).

Each clip becomes one fixed-length (SEQUENCE_LENGTH, FEATURES_PER_FRAME)
landmark sequence, matching exactly what predict_word_sign.py builds
live from the webcam, so the trained model sees the same feature space
at inference time.

Parallelized across processes (one MediaPipe Holistic instance per
worker, reused across that worker's clips) -- this is the dominant
cost in the whole pipeline (measured: ~173ms/frame single-process), so
at a few hundred words' worth of clips this step alone would take
hours single-threaded. See word_level/README.md for the measured
numbers behind this.

Usage:
    python word_level/extract_features.py
"""

import glob
import json
import multiprocessing as mp
import os

import cv2
import numpy as np

import config
from landmarks import extract_frame_features, make_holistic, resample_sequence

VIDEO_EXTS = (".mp4", ".mov", ".avi", ".mkv")

# Leave a core or two free for the OS/other work; this is the dominant
# cost in the pipeline so parallelism here matters most.
NUM_WORKERS = max(1, (os.cpu_count() or 4) - 1)

_worker_holistic = None  # one per worker process, created once in _init_worker


def iter_clips_for_word(word):
    word_key = word.replace(" ", "_")
    for base_dir in (config.WLASL_RAW_DIR, config.WEBCAM_RAW_DIR):
        word_dir = os.path.join(base_dir, word_key)
        if not os.path.isdir(word_dir):
            continue
        for ext in VIDEO_EXTS:
            for path in sorted(glob.glob(os.path.join(word_dir, f"*{ext}"))):
                yield path


def clip_to_sequence(video_path, holistic):
    cap = cv2.VideoCapture(video_path)
    frame_features = []

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        results = holistic.process(rgb)

        frame_features.append(extract_frame_features(results))

    cap.release()

    if not frame_features:
        return None

    return resample_sequence(frame_features)


def _init_worker():
    # Runs once per worker process. A MediaPipe Holistic instance can't
    # be pickled/shared across processes, so each worker builds and
    # keeps its own for the lifetime of the pool.
    global _worker_holistic
    _worker_holistic = make_holistic(static_image_mode=False)


def _process_clip(args):
    word, clip_path = args
    try:
        seq = clip_to_sequence(clip_path, _worker_holistic)
    except Exception as e:
        return (word, clip_path, None, str(e))
    return (word, clip_path, seq, None)


def main():
    os.makedirs(config.DATA_DIR, exist_ok=True)

    jobs = []
    per_word_total = {}
    for word in config.VOCAB:
        clips = list(iter_clips_for_word(word))
        per_word_total[word] = len(clips)
        for clip_path in clips:
            jobs.append((word, clip_path))

    if not jobs:
        raise SystemExit(
            "No clips were processed. Run word_level/wlasl_fetch.py first "
            "(and/or record clips with word_level/collect_webcam_words.py)."
        )

    print(f"Processing {len(jobs)} clip(s) across {len(config.VOCAB)} words "
          f"with {NUM_WORKERS} worker process(es)...")

    X = []
    y = []
    per_word_used = {word: 0 for word in config.VOCAB}
    done = 0

    with mp.Pool(processes=NUM_WORKERS, initializer=_init_worker) as pool:
        for word, clip_path, seq, err in pool.imap_unordered(_process_clip, jobs, chunksize=4):
            done += 1

            if err is not None:
                print(f"  WARNING: {clip_path} failed ({err})")
            elif seq is None:
                print(f"  WARNING: unreadable clip {clip_path}")
            else:
                X.append(seq)
                y.append(word)
                per_word_used[word] += 1

            if done % 50 == 0 or done == len(jobs):
                print(f"  progress: {done}/{len(jobs)}")

    if not X:
        raise SystemExit("No usable sequences extracted.")

    X = np.stack(X)             # (N, SEQUENCE_LENGTH, FEATURES_PER_FRAME)
    labels_sorted = sorted(set(y))
    label_to_idx = {label: i for i, label in enumerate(labels_sorted)}
    y_idx = np.array([label_to_idx[label] for label in y], dtype=np.int64)

    np.save(config.X_PATH, X)
    np.save(config.Y_PATH, y_idx)
    with open(config.LABELS_PATH, "w") as f:
        json.dump(labels_sorted, f, indent=2)

    zero_classes = [w for w in config.VOCAB if per_word_used.get(w, 0) == 0]

    print("\n==============================")
    print(f"Samples per word: {per_word_used}")
    print(f"X shape: {X.shape}")
    print(f"y shape: {y_idx.shape}")
    print(f"Classes ({len(labels_sorted)}): {labels_sorted}")
    if zero_classes:
        print(f"WARNING: 0 usable samples for: {zero_classes}")
    print(f"Saved -> {config.X_PATH}, {config.Y_PATH}, {config.LABELS_PATH}")
    print("==============================")


if __name__ == "__main__":
    main()
