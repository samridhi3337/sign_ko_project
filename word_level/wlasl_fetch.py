"""
Downloads real WLASL clips for the words in config.VOCAB.

Source: the public, no-login-required Hugging Face mirror of WLASL
(Voxel51/WLASL, 11,980 clips / 2000 gloss classes), which serves the
clips as plain .mp4 files over HTTPS plus a samples.json metadata file
mapping each clip's filepath to its gloss (word) label.

WLASL is released for academic / computational use only (see
word_level/README.md for the license note) -- this project uses it for
non-commercial, educational purposes.

Usage:
    python word_level/wlasl_fetch.py
"""

import json
import os
import ssl
import sys
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import config

# I/O-bound (network) work -- threads are fine here despite the GIL.
# Kept comfortably under the HF endpoint's observed ~10 req/s rate
# limit (see word_level/README.md) to avoid throttling/errors.
DOWNLOAD_WORKERS = 8

try:
    import certifi
    _SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CONTEXT = ssl.create_default_context()


def download(url, dest_path, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "sign-project/1.0"})
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CONTEXT) as resp:
        data = resp.read()
    with open(dest_path, "wb") as f:
        f.write(data)
    return len(data)


def ensure_samples_json():
    if os.path.exists(config.WLASL_SAMPLES_JSON):
        print(f"Using cached metadata: {config.WLASL_SAMPLES_JSON}")
        return

    print(f"Downloading WLASL metadata from {config.HF_SAMPLES_URL} ...")
    size = download(config.HF_SAMPLES_URL, config.WLASL_SAMPLES_JSON)
    print(f"  saved {size / 1024:.0f} KB -> {config.WLASL_SAMPLES_JSON}")


def main():
    os.makedirs(config.WLASL_RAW_DIR, exist_ok=True)

    ensure_samples_json()

    with open(config.WLASL_SAMPLES_JSON) as f:
        meta = json.load(f)

    samples = meta["samples"]

    by_word = defaultdict(list)
    vocab_set = set(config.VOCAB)
    for s in samples:
        label = s["gloss"]["label"]
        if label in vocab_set:
            by_word[label].append(s["filepath"])

    missing = vocab_set - set(by_word.keys())
    if missing:
        print(f"WARNING: no WLASL clips found for: {sorted(missing)}")

    # Build the full list of (word, filepath, dest) jobs up front, then
    # fan them out across a thread pool -- this is what makes fetching
    # hundreds/thousands of clips (vs. the original 23-word/173-clip
    # vocabulary) practical instead of taking tens of minutes serially.
    jobs = []
    for word in config.VOCAB:
        filepaths = by_word.get(word, [])[: config.MAX_CLIPS_PER_WORD]
        if not filepaths:
            continue

        word_dir = os.path.join(config.WLASL_RAW_DIR, word.replace(" ", "_"))
        os.makedirs(word_dir, exist_ok=True)

        for filepath in filepaths:
            fname = os.path.basename(filepath)
            dest = os.path.join(word_dir, fname)
            jobs.append((word, filepath, fname, dest))

    total_downloaded = 0
    total_skipped = 0
    total_failed = 0

    def do_job(job):
        word, filepath, fname, dest = job
        if os.path.exists(dest) and os.path.getsize(dest) > 0:
            return ("skipped", word, fname, None)

        url = f"{config.HF_BASE_URL}/{filepath}"
        try:
            size = download(url, dest)
            return ("ok", word, fname, size)
        except Exception as e:
            return ("failed", word, fname, str(e))

    print(f"\nFetching {len(jobs)} clip(s) across {len(config.VOCAB)} words "
          f"with {DOWNLOAD_WORKERS} parallel workers...")

    with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as pool:
        futures = [pool.submit(do_job, job) for job in jobs]
        for i, future in enumerate(as_completed(futures), 1):
            status, word, fname, extra = future.result()

            if status == "ok":
                total_downloaded += 1
            elif status == "skipped":
                total_skipped += 1
            else:
                total_failed += 1
                print(f"  FAILED [{word}] {fname}: {extra}", file=sys.stderr)

            if i % 100 == 0 or i == len(jobs):
                print(f"  progress: {i}/{len(jobs)} "
                      f"(ok={total_downloaded}, skipped={total_skipped}, failed={total_failed})")

    print("\n==============================")
    print(f"Downloaded: {total_downloaded}")
    print(f"Already present (skipped): {total_skipped}")
    print(f"Failed: {total_failed}")
    print(f"Clips stored under: {config.WLASL_RAW_DIR}")
    print("==============================")


if __name__ == "__main__":
    main()
