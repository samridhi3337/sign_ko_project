"""
Shared configuration for the Text -> Sign Animation feature. Separate
module, additive to the rest of the project -- reuses data already on
disk from word_level/ and the alphabet dataset, doesn't duplicate or
modify either.
"""

import json
import os
import string

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

# -----------------------------------------------------------------
# Source data (reused, not duplicated)
# -----------------------------------------------------------------
WORD_LEVEL_LABELS_PATH = os.path.join(PROJECT_ROOT, "word_level", "data", "labels.json")
WLASL_RAW_DIR = os.path.join(PROJECT_ROOT, "word_level", "wlasl_raw")

# Same external alphabet dataset used by alphabet/config.py.
ALPHABET_DATASET_SOURCE = "/Users/samiii/Desktop/asl_alphabet_dataset 2"
ALPHABET_LABELS_CSV = os.path.join(ALPHABET_DATASET_SOURCE, "labels.csv")

LETTERS = list(string.ascii_uppercase)

# -----------------------------------------------------------------
# Derived animation data (this module's own output)
# -----------------------------------------------------------------
DATA_DIR = os.path.join(BASE_DIR, "data")
WORDS_DIR = os.path.join(DATA_DIR, "words")     # <word>.json
LETTERS_DIR = os.path.join(DATA_DIR, "letters")  # <LETTER>.json

# Real professional motion-capture clips for a subset of known words,
# sourced from the Studio Galt Sign Language Mocap Archive (CC0) --
# see fetch_mocap_words.py and README.md "Pass 6".
MOCAP_DIR = os.path.join(DATA_DIR, "mocap")            # <word>.fbx
MOCAP_MANIFEST_PATH = os.path.join(DATA_DIR, "mocap_manifest.json")

# Real ASL SiGML data + CWASA avatar engine, vendored unmodified from
# the open-source Kozha project -- see kozha.py and README.md "Pass 7".
KOZHA_DIR = os.path.join(DATA_DIR, "kozha")


def mocap_manifest():
    """word -> {file, source_url, source_repo, license} for every known
    word that has a real mocap FBX clip available."""
    if not os.path.exists(MOCAP_MANIFEST_PATH):
        return {}
    with open(MOCAP_MANIFEST_PATH) as f:
        return json.load(f)


def mocap_words():
    """Set of known words that have a real mocap FBX clip available."""
    return set(mocap_manifest().keys())

# Avatar-space scale: captured landmarks are remapped so the figure is
# roughly this many units tall (Three.js units, arbitrary but
# consistent with a human-scale camera/lighting setup).
AVATAR_HEIGHT_UNITS = 1.7

_known_words_cache = None


def known_words():
    global _known_words_cache
    if _known_words_cache is None:
        if os.path.exists(WORD_LEVEL_LABELS_PATH):
            with open(WORD_LEVEL_LABELS_PATH) as f:
                _known_words_cache = json.load(f)
        else:
            _known_words_cache = []
    return _known_words_cache
