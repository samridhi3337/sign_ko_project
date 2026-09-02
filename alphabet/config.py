"""
Shared configuration for the alphabet (fingerspelling) recognition
pipeline. Separate module from word_level/ and from the original
static-word pipeline (create_dataset.py / train_model.py / model.pkl)
-- all of those are left completely untouched.
"""

import os
import string

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

# -----------------------------------------------------------------
# Source dataset (lives outside the project -- see alphabet/README.md)
# -----------------------------------------------------------------
# The user's own dataset: 26 letters, two paired subsets (clean hand
# images for hand-shape training, and personal face captures with
# emotion labels for the expression thumbnails). Not copied into the
# project wholesale -- only small derived assets are (see below).
DATASET_SOURCE = "/Users/samiii/Desktop/asl_alphabet_dataset 2"
HAND_IMAGES_DIR = os.path.join(DATASET_SOURCE, "images")
PERSONAL_CAPTURES_DIR = os.path.join(DATASET_SOURCE, "personal_captures")
LABELS_CSV = os.path.join(DATASET_SOURCE, "labels.csv")
PERSONAL_CAPTURES_CSV = os.path.join(DATASET_SOURCE, "personal_captures.csv")

LETTERS = list(string.ascii_uppercase)  # A-Z

# Cap on how many hand images per letter to run through MediaPipe for
# training (78,000 total images exist; this keeps feature extraction
# to a few minutes while still being a real, non-trivial sample).
MAX_TRAIN_IMAGES_PER_LETTER = 300

DEFAULT_EXPRESSION_EMOTION = "neutral"

# -----------------------------------------------------------------
# Derived assets kept inside the project
# -----------------------------------------------------------------
DATA_DIR = os.path.join(BASE_DIR, "data")
X_PATH = os.path.join(DATA_DIR, "X.npy")
Y_PATH = os.path.join(DATA_DIR, "y.npy")
LABELS_PATH = os.path.join(DATA_DIR, "labels.json")

MODEL_DIR = os.path.join(BASE_DIR, "model")
MODEL_PATH = os.path.join(MODEL_DIR, "alphabet_model.pkl")

STATIC_DIR = os.path.join(PROJECT_ROOT, "static")
ALPHABET_IMAGES_DIR = os.path.join(STATIC_DIR, "alphabet_images")       # <LETTER>.jpg
ALPHABET_EXPRESSIONS_DIR = os.path.join(STATIC_DIR, "alphabet_expressions")  # <LETTER>.jpg

ALPHABET_PREDICTION_JSON = os.path.join(PROJECT_ROOT, "alphabet_prediction.json")

ALARM_PATH = os.path.join(PROJECT_ROOT, "alarm.mp3")
EMERGENCY_WORDS = ["HELP"]
