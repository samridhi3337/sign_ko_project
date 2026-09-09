
"""
Shared helper connecting the 220-word WLASL dataset (downloaded into
word_level/wlasl_raw/ by word_level/wlasl_fetch.py) to the Flask app:
used by app.py (to serve clips and list the vocabulary) and by
text_to_sign_web.py (to fall back to a real sign video for any of the
220 words that don't have a static reference image).

Does not duplicate the ~956MB of video into static/ -- clips are
served directly from word_level/wlasl_raw/ via a dedicated Flask route
(see app.py's /word-clip/<word>).
"""

import glob
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

LABELS_PATH = os.path.join(BASE_DIR, "word_level", "data", "labels.json")
WLASL_RAW_DIR = os.path.join(BASE_DIR, "word_level", "wlasl_raw")

VIDEO_EXTS = (".mp4", ".mov", ".avi", ".mkv")

_words_cache = None


def word_key(word):
    return word.strip().lower().replace(" ", "_")


def list_words():
    """Sorted list of all 220 WLASL words available in word_level/wlasl_raw/."""
    global _words_cache
    if _words_cache is None:
        words_found = set()
        if os.path.isdir(WLASL_RAW_DIR):
            for entry in os.listdir(WLASL_RAW_DIR):
                full_p = os.path.join(WLASL_RAW_DIR, entry)
                if os.path.isdir(full_p):
                    words_found.add(entry.replace("_", " "))

        if os.path.exists(LABELS_PATH):
            with open(LABELS_PATH) as f:
                for w in json.load(f):
                    words_found.add(w)

        _words_cache = sorted(words_found)
    return _words_cache


def is_known_word(word):
    return word.strip().lower() in list_words()


def clip_dir_for_word(word):
    return os.path.join(WLASL_RAW_DIR, word_key(word))


def first_clip_filename(word):
    """Returns just the filename (not full path) of one representative
    clip for this word, or None if the word is unknown / has no clips
    on disk. Deterministic (sorted) so the same clip is always served
    for a given word."""
    if not is_known_word(word):
        return None

    d = clip_dir_for_word(word)
    if not os.path.isdir(d):
        return None

    for ext in VIDEO_EXTS:
        matches = sorted(glob.glob(os.path.join(d, f"*{ext}")))
        if matches:
            return os.path.basename(matches[0])

    return None
