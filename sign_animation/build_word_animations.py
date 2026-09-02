"""
Extracts real, full per-frame 3D motion (pose + both hands) for one
representative clip per word -- the SAME clip word_video_lookup.py
already serves for video preview, so the animation and the video
preview agree -- and saves it as sign_animation/data/words/<word>.json
for the Text -> Sign Animation avatar to play back.

Does not re-download anything: reads clips already fetched by
word_level/wlasl_fetch.py. Parallelized across processes the same way
as word_level/extract_features.py, since MediaPipe Holistic per-frame
is the dominant cost (measured ~173ms/frame single-process).

Usage:
    python sign_animation/build_word_animations.py
"""

import json
import multiprocessing as mp
import os
import sys

import cv2

import config

sys.path.insert(0, config.PROJECT_ROOT)
import word_video_lookup  # noqa: E402

from landmarks3d import (  # noqa: E402
    compute_anchor_and_scale, holistic_frame_to_raw, make_holistic, remap_frame,
)

NUM_WORKERS = max(1, (os.cpu_count() or 4) - 1)

_worker_holistic = None


def _init_worker():
    global _worker_holistic
    _worker_holistic = make_holistic()


def extract_clip(video_path, holistic):
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0

    raw_frames = []
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        results = holistic.process(rgb)
        raw_frames.append(holistic_frame_to_raw(results))
    cap.release()

    if not raw_frames:
        return None

    anchor, scale = compute_anchor_and_scale(raw_frames)
    frames = [remap_frame(f, anchor, scale) for f in raw_frames]

    return {"fps": fps, "frames": frames}


def _process_word(word):
    clip_dir = word_video_lookup.clip_dir_for_word(word)
    filename = word_video_lookup.first_clip_filename(word)
    if not filename:
        return (word, None, "no clip found")

    video_path = os.path.join(clip_dir, filename)
    try:
        data = extract_clip(video_path, _worker_holistic)
    except Exception as e:
        return (word, None, str(e))

    if data is None:
        return (word, None, "no frames read")

    data["word"] = word
    data["source_clip"] = filename
    return (word, data, None)


def main():
    os.makedirs(config.WORDS_DIR, exist_ok=True)

    words = config.known_words()
    if not words:
        raise SystemExit(
            "No words found in word_level/data/labels.json -- "
            "run the word_level pipeline first."
        )

    print(f"Building animation data for {len(words)} words "
          f"with {NUM_WORKERS} worker process(es)...")

    done = 0
    failed = []

    with mp.Pool(processes=NUM_WORKERS, initializer=_init_worker) as pool:
        for word, data, err in pool.imap_unordered(_process_word, words, chunksize=2):
            done += 1
            if err is not None:
                failed.append((word, err))
                print(f"  WARNING [{word}]: {err}")
            else:
                out_path = os.path.join(config.WORDS_DIR, f"{word}.json")
                with open(out_path, "w") as f:
                    json.dump(data, f)

            if done % 25 == 0 or done == len(words):
                print(f"  progress: {done}/{len(words)}")

    print("\n==============================")
    print(f"Wrote {len(words) - len(failed)}/{len(words)} word animation files "
          f"-> {config.WORDS_DIR}")
    if failed:
        print(f"Failed ({len(failed)}): {failed}")
    print("==============================")


if __name__ == "__main__":
    main()
