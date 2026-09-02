"""
Shared configuration for the word-level (WLASL-based) recognition pipeline.

This module is intentionally separate from the project's existing
static-pose pipeline (create_dataset.py / train_model.py / model.pkl),
which is left completely untouched. Everything in word_level/ is additive.
"""

import os

# -----------------------------------------------------------------
# Vocabulary
# -----------------------------------------------------------------
# The words this pipeline targets: every WLASL gloss class with >= 9
# real clips available (a curated, well-covered subset -- see
# word_level/README.md "Vocabulary" for the full rationale and the
# analysis behind this threshold), UNIONED with every word the app
# already depended on before this expansion (the original static-pose
# vocabulary, the emergency words, and everything with a sign image in
# static/sign_images) so nothing existing breaks even though a few of
# those (e.g. "hello", "i", "emergency") have fewer than 9 clips.
#
# This was a deliberate middle ground versus training on the full
# WLASL-2000 (2,000 classes, median 6 clips/class -- see
# word_level/README.md for the full time/accuracy analysis of why that
# wasn't a good idea for this architecture): 220 words, 9-16 clips
# each, real per-class data density instead of a diluted 2000-way
# classifier trained on 5-6 examples per class.
#
# To extend the vocabulary later: add a gloss word here (it must match
# a WLASL gloss label, all lowercase), then re-run wlasl_fetch.py,
# extract_features.py and train_word_model.py in that order.
VOCAB = [
    'help', 'i', 'need', 'water'
]

# Words that trigger emergency alarm/WhatsApp alert
EMERGENCY_WORDS = ["help", "danger"]

# -----------------------------------------------------------------
# WLASL source (public, no-login Hugging Face mirror of WLASL)
# -----------------------------------------------------------------
HF_DATASET_REPO = "Voxel51/WLASL"
HF_BASE_URL = f"https://huggingface.co/datasets/{HF_DATASET_REPO}/resolve/main"
HF_SAMPLES_URL = f"{HF_BASE_URL}/samples.json"

# Max clips downloaded per word (keeps the download small & practical;
# WLASL only has a handful of clips for most words anyway).
MAX_CLIPS_PER_WORD = 20

# -----------------------------------------------------------------
# Paths
# -----------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

WLASL_SAMPLES_JSON = os.path.join(BASE_DIR, "wlasl_samples.json")
WLASL_RAW_DIR = os.path.join(BASE_DIR, "wlasl_raw")       # downloaded WLASL clips
WEBCAM_RAW_DIR = os.path.join(BASE_DIR, "webcam_raw")     # optional user-recorded clips

DATA_DIR = os.path.join(BASE_DIR, "data")
X_PATH = os.path.join(DATA_DIR, "X.npy")
Y_PATH = os.path.join(DATA_DIR, "y.npy")
LABELS_PATH = os.path.join(DATA_DIR, "labels.json")

MODEL_DIR = os.path.join(BASE_DIR, "model")
# HDF5 (.h5), not the newer .keras zip format: this project's pinned
# keras==2.13.1 has a known bug re-hydrating an optimizer from the
# native .keras format (AttributeError: 'Adam' object has no attribute
# 'build') -- .h5 saving/loading is stable on this version.
MODEL_PATH = os.path.join(MODEL_DIR, "word_model.h5")

# Prediction output consumed by the Flask app (separate from the
# existing prediction.json used by the static-pose recognizer, so the
# two modes never clash).
WORD_PREDICTION_JSON = os.path.join(
    os.path.dirname(BASE_DIR), "word_prediction.json"
)

# Reuses the existing alarm sound from the project root. Referenced as
# an absolute path (not a bare "alarm.mp3") because this script can be
# launched with a different working directory than the project root
# (app.py's /start-word-recognition route runs it with cwd=word_level/).
ALARM_PATH = os.path.join(os.path.dirname(BASE_DIR), "alarm.mp3")

# -----------------------------------------------------------------
# Sequence / feature settings
# -----------------------------------------------------------------
SEQUENCE_LENGTH = 30   # every clip is resampled to exactly this many frames

# MediaPipe Holistic landmark counts
NUM_POSE_LANDMARKS = 33
NUM_HAND_LANDMARKS = 21

# 3 coords (x, y, z) per landmark; pose + left hand + right hand
FEATURES_PER_FRAME = (
    NUM_POSE_LANDMARKS + NUM_HAND_LANDMARKS + NUM_HAND_LANDMARKS
) * 3   # = 225
