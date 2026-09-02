# Alphabet (Fingerspelling) Recognition

Letter-by-letter (A-Z) sign recognition that assembles words/sentences,
paired with the signer's own captured facial expression per letter.
Separate module from `word_level/` (whole-word, WLASL-based) and the
original static-pose recognizer (`model.pkl`) — nothing in either of
those was touched.

## Source dataset

Built from a dataset the user created at:

```
/Users/samiii/Desktop/asl_alphabet_dataset 2/
```

Two paired subsets (see that folder's own `README.md`/`dataset_info.json`
for full provenance):

- `images/<LETTER>/` — 3,000 clean hand-only images per letter (78,000
  total), no face, no overlay. Used to train the hand-shape classifier.
- `personal_captures/<LETTER>/` — 300 images per letter (7,800 total),
  **the dataset author's own face visible**, each labeled with an
  `emotion` (`neutral`/`happy`/`sad`). Each frame has a HUD (class
  name, hand skeleton, progress bar) burned in at the top and a control
  caption at the bottom — the face region itself is unobstructed.

**Nothing from the 85,800-image source is bulk-copied into this
project.** Training reads directly from the path above. Only small,
derived assets are written into `sign_project`:

- `alphabet/model/alphabet_model.pkl` — the trained classifier
- `alphabet/data/X.npy` / `y.npy` / `labels.json` — the extracted
  training features
- `static/alphabet_images/<LETTER>.jpg` — 26 representative hand-sign
  thumbnails, for Text-to-Sign and the recognition UI
- `static/alphabet_expressions/<LETTER>.jpg` — 26 face crops (HUD
  removed via MediaPipe Face Detection), one per letter, showing the
  captured expression for that letter

If the dataset folder ever moves, update `DATASET_SOURCE` in
`alphabet/config.py`.

## What "facial expression is preserved and displayed" means here

Each recognized or generated letter is paired with a **stored
reference image** from `personal_captures` (the `neutral`-emotion
capture for that letter, cropped to just the face) — not a live
expression classifier run on the webcam feed. This is what the source
dataset actually supports well (a labeled photo per letter+emotion),
and it's what gets shown next to the sign, in both directions:

- **Sign → Text** (`predict_alphabet_sign.py`): as letters are
  recognized into the current word, `alphabet_prediction.json` includes
  an `expressions` list pairing each letter with its reference image.
- **Text → Sign** (Alphabet-wise mode on the Text-to-Sign page): each
  spelled-out letter is shown with its hand-sign image directly above
  its expression thumbnail.

## Pipeline

```bash
source .venv/bin/activate

# 1. Generate the 52 small display thumbnails from the source dataset
python alphabet/prepare_assets.py

# 2. Extract MediaPipe Hands landmarks from a sample of images/
#    (300/letter by default - see config.MAX_TRAIN_IMAGES_PER_LETTER)
python alphabet/extract_features.py

# 3. Train the RandomForest letter classifier
python alphabet/train_alphabet_model.py
```

## Running recognition live

```bash
python alphabet/predict_alphabet_sign.py
```

Hold a letter sign steady (~0.8s) to commit it into the current word.
Pull your hand out of frame for ~1.2s to commit the word into the
sentence (space bar also forces a word break; `C` clears the sentence;
`ESC` quits) — same interaction pattern as the project's other two
recognizers.

Headless sanity check without a camera:

```bash
python alphabet/predict_alphabet_sign.py --dry-run path/to/img1.jpg path/to/img2.jpg
```

## From the web app

`/recognition` now opens with an **Alphabet-wise** / **Word-wise**
tab switcher. Alphabet-wise is the new fingerspelling UI described
above. Word-wise is exactly the two recognizers that already existed
(legacy static Sign Recognition + Word-Level Recognition Beta),
unchanged, just grouped under one tab.

`/text-to-sign` has a mode radio: **Word-wise** is the original
whole-word-image behavior, untouched. **Alphabet-wise** always spells
the input out letter-by-letter using `static/alphabet_images/`, each
letter paired with its `static/alphabet_expressions/` thumbnail.

## Read this before you trust the accuracy number

Same caveat the source dataset's own README calls out: these images
come from continuous video, so consecutive frames are near-duplicates.
`train_alphabet_model.py` does a random train/test split (matching the
style of the project's existing `train_model.py`), which the source
dataset measured at **98% accuracy random-split vs. 8-17% when the
test set is a signer the model never saw.** Treat the printed number as
an optimistic upper bound, not a real-world accuracy figure. `J` and
`Z` are motion letters and are expected to be the weakest classes in
any static single-frame model — this is the same reason `word_level/`
is a real "signs move" upgrade over single-frame classification.

## Licence and privacy

The `personal_captures` subset shows an identifiable person (the
dataset author). It's already part of this local project because the
author is the one integrating it — be mindful of that if this project
is ever shared, demoed publicly, or its repository made public.
