"""
Fixes tracking glitches found by validate_animations.mjs: a handful of
words have a landmark whose position jumps far more than the rest of
that SAME word's own motion ever does, for one or more consecutive
frames, then returns -- a MediaPipe mis-detection (its Z/depth
estimate in particular is known to be less stable than X/Y), not real
motion. Confirmed by inspection (see sign_animation/README.md, "Pass
4") that this is a real, sustained multi-frame anomaly for some words,
not just a single-frame spike -- so this uses a per-word ADAPTIVE
threshold (median + 6x median-absolute-deviation of that landmark's
OWN frame-to-frame step sizes in that word), not one fixed constant
for every word. That matters: a fixed global cutoff either misses
genuine anomalies in slow/calm signs or clips real fast motion in
energetic ones (an earlier version of this script made exactly that
mistake -- caught by re-checking rather than assuming the fix was
correct just because the validator went green). The adaptive
threshold scales to each word's own typical motion, so genuine fast
signing is left untouched and only what's anomalous *for that word*
gets repaired.

Any contiguous run of anomalous frames for a point is replaced by
linear interpolation between the last good frame before the run and
the first good frame after it.

Usage:
    python sign_animation/smooth_outliers.py
"""

import json
import os

import numpy as np

import config

MAD_MULTIPLIER = 6.0   # "way more than this landmark's own typical step"
MIN_ABS_THRESHOLD_M = 0.25  # never flag steps smaller than this regardless
                             # of MAD (guards tiny/near-static landmarks
                             # whose MAD could be ~0)


def repair_part(frames_part):
    """frames_part: list of (N_points, 3) arrays or None, one per frame.
    Mutates in place. Returns count of frames repaired."""
    valid_idx = [i for i, f in enumerate(frames_part) if f is not None]
    if len(valid_idx) < 4:
        return 0

    num_points = len(frames_part[valid_idx[0]])
    repaired = 0

    for p in range(num_points):
        traj = np.array([frames_part[i][p] for i in valid_idx])  # (K, 3)
        steps = np.linalg.norm(np.diff(traj, axis=0), axis=1)     # (K-1,)
        if len(steps) < 3:
            continue

        median = np.median(steps)
        mad = np.median(np.abs(steps - median)) or 1e-6
        threshold = max(median + MAD_MULTIPLIER * mad, MIN_ABS_THRESHOLD_M)

        # A frame k (1..K-2) is anomalous if BOTH the step into it and
        # the step out of it are outliers -- a frame that's only far
        # from one neighbor is where a genuine fast move starts/ends,
        # not a glitch.
        is_bad = np.zeros(len(valid_idx), dtype=bool)
        for k in range(1, len(valid_idx) - 1):
            if steps[k - 1] > threshold and steps[k] > threshold:
                is_bad[k] = True

        if not is_bad.any():
            continue

        # Repair each maximal run of bad frames by linear interpolation
        # between the last good frame before it and the first good
        # frame after it.
        k = 0
        while k < len(valid_idx):
            if not is_bad[k]:
                k += 1
                continue
            run_start = k
            while k < len(valid_idx) and is_bad[k]:
                k += 1
            run_end = k  # exclusive

            before = run_start - 1
            after = run_end if run_end < len(valid_idx) else None
            if before < 0 or after is None:
                continue  # can't safely interpolate at a clip's very edge

            p0 = np.array(frames_part[valid_idx[before]][p])
            p1 = np.array(frames_part[valid_idx[after]][p])
            span = valid_idx[after] - valid_idx[before]

            for j in range(run_start, run_end):
                t = (valid_idx[j] - valid_idx[before]) / span
                interp = (p0 + (p1 - p0) * t).round(4).tolist()
                frames_part[valid_idx[j]][p] = interp
                repaired += 1

    return repaired


def smooth_word_file(path):
    with open(path) as f:
        data = json.load(f)

    frames = data["frames"]
    total_fixed = 0

    for key in ("pose", "left_hand", "right_hand", "face"):
        parts = [f.get(key) for f in frames]
        fixed = repair_part(parts)
        total_fixed += fixed
        for f, p in zip(frames, parts):
            f[key] = p

    if total_fixed:
        with open(path, "w") as f:
            json.dump(data, f)

    return total_fixed


def main():
    total = 0
    changed_words = []

    for fname in sorted(os.listdir(config.WORDS_DIR)):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(config.WORDS_DIR, fname)
        fixed = smooth_word_file(path)
        if fixed:
            total += fixed
            changed_words.append((fname[:-5], fixed))

    print(f"Repaired {total} anomalous point(s) across {len(changed_words)}/220 word(s):")
    for word, fixed in changed_words:
        print(f"  {word}: {fixed} point(s)")


if __name__ == "__main__":
    main()
