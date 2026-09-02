# Word-Level Sign Recognition (WLASL-based)

This module upgrades the project from **single-frame static hand-pose**
recognition to **motion-aware, word-level** recognition: instead of
classifying one video frame, it classifies a ~1-second **sequence** of
MediaPipe landmarks (pose + both hands), which is what real signed
words actually look like (most ASL signs involve movement, not a fixed
hand shape).

It is entirely additive — nothing in the project root (`app.py`
routes, `predict_sign_terminal.py`, `model.pkl`, `data.csv`, etc.) was
removed or changed in a breaking way. This module lives in its own
`word_level/` folder with its own model, data, and prediction file.

## Why WLASL, not RWTH-PHOENIX-Weather-2014T

| | WLASL | PHOENIX-2014T |
|---|---|---|
| Language | American Sign Language (English) | German Sign Language |
| Unit | Isolated words (2,000 gloss classes) | Continuous sentences (weather broadcasts) |
| Task | Word/gesture classification | Sequence-to-sequence translation (needs CTC/seq2seq) |
| Fit for this project | ✅ matches the existing English-word vocabulary (Hello, Help, Water, ...) | ❌ wrong language, wrong task shape |

**WLASL** is the right dataset for a word-level ASL app like this one.

## Where the data actually came from

WLASL's original raw videos (hosted across many now largely dead
YouTube/source links) aren't practically downloadable anymore. Instead
this module fetches real WLASL clips from a public, no-login-required
Hugging Face mirror: **`Voxel51/WLASL`** (11,980 clips / 2,000 gloss
classes, served as plain `.mp4` files over HTTPS with a `samples.json`
metadata file mapping each clip to its word label).

`word_level/wlasl_fetch.py` was already run for this project and
downloaded **2,142 real WLASL clips across 220 words** (~956 MB) into
`word_level/wlasl_raw/<word>/`.

### Why 220 words, not all 2,000

The full WLASL-2000 dataset was seriously considered and explicitly
analyzed before this expansion (from an original 23-word vocabulary).
Real, measured numbers from that analysis:

- Full WLASL-2000 has a **median of only 6 clips/class** (95% of
  classes have fewer than 10), and download + MediaPipe Holistic
  feature extraction over all 11,980 clips was measured/extrapolated
  at **~40 hours single-process** (~6-7h even parallelized across all
  CPU cores) on this machine.
- Published academic WLASL2000 baselines (I3D **pretrained on
  Kinetics-400** — i.e. with heavy transfer learning this project's
  from-scratch BiLSTM doesn't have) report only ~32-40% top-1 accuracy.
  With a median of 6 clips/class and no pretraining, a from-scratch
  model here would land well below that.

Instead, **220 words** were selected: every WLASL gloss with **>= 9
real clips** (9-16 each — real per-class data density), unioned with
every word the app already depended on before this expansion (so nothing
existing broke, even the handful like "hello"/"i"/"emergency" that have
fewer than 9 clips). That's a genuine ~10x vocabulary expansion with
real accuracy, instead of a diluted 2,000-way classifier trained on
5-6 examples per class.

> **License note:** WLASL is released under a Computational Use of
> Data Agreement (C-UDA) — academic / non-commercial, computational
> use only. This project uses it for exactly that (an educational
> major project).

## Vocabulary

Defined in `config.py` — 220 words (see "Why 220 words, not all 2,000"
above for the selection criteria). Covers everything the original
static-pose app recognized, everything with a sign image in
`static/sign_images`, the emergency vocabulary, plus a broad set of
everyday words (family, food, places, feelings, common verbs, ...).

To add a new word: add its (lowercase) gloss to `config.VOCAB`, then
re-run the pipeline below (`wlasl_fetch.py` is idempotent — it only
downloads clips it doesn't already have, so re-running after adding a
few words is fast). Not every English word exists as a WLASL gloss —
`word_level/wlasl_fetch.py` will print a warning for any word it can't
find clips for. For best results, check a word's clip count in
`word_level/wlasl_samples.json` first (aim for >= 9 for real accuracy,
per the analysis above).

## Pipeline

Run these **in order**, from the project root, with the project's venv
active:

```bash
source .venv/bin/activate

# 1. Download real WLASL clips for config.VOCAB (idempotent - skips
#    clips it already has)
python word_level/wlasl_fetch.py

# 2. Extract MediaPipe Holistic landmark sequences from every clip
#    (WLASL + any of your own webcam recordings) -> X.npy/y.npy
python word_level/extract_features.py

# 3. Train the Bidirectional-LSTM word classifier
python word_level/train_word_model.py
```

This produces `word_level/model/word_model.keras` and
`word_level/data/labels.json`.

### Optional: add your own recordings

WLASL only has a handful of clips per word (4-15), so accuracy is
naturally limited. `word_level/collect_webcam_words.py` lets you record
extra clips for any word with your own webcam (same interactive style
as the project's existing `collect_data.py`) into
`word_level/webcam_raw/<word>/`. Re-run steps 2 and 3 afterwards to
fold them into training.

```bash
python word_level/collect_webcam_words.py
```

### Running recognition live

```bash
python word_level/predict_word_sign.py
```

Same controls/behavior pattern as the existing
`predict_sign_terminal.py` (ESC to quit, `C` to clear the sentence,
alarm + WhatsApp alert for emergency words), but built on motion
sequences instead of single frames. Writes to `word_prediction.json`
in the project root (kept separate from the existing `prediction.json`
so the two recognition modes never clash).

To sanity-check the model without a camera:

```bash
python word_level/predict_word_sign.py --dry-run word_level/wlasl_raw/hello/27172.mp4
```

### From the web app

Visit `/recognition` — there's now a second "Word-Level Recognition
(Beta)" section below the original one, with its own Start button and
prediction/sentence display, wired to `/start-word-recognition` and
`/get_word_prediction` in `app.py`.

## Architecture

```
video frame -> MediaPipe Holistic -> pose(33) + left hand(21) + right hand(21)
            -> normalize (center on shoulder midpoint, scale by shoulder width)
            -> flatten to a 225-dim vector per frame
clip -> resample to a fixed 30-frame sequence -> (30, 225) tensor
      -> Bidirectional LSTM(128) -> Bidirectional LSTM(64) -> Dense -> softmax(num_words)
```

At inference time, `predict_word_sign.py` keeps a rolling 30-frame
buffer of live webcam features and re-predicts every frame, then
applies the same majority-vote smoothing + hold-to-commit pattern the
existing static recognizer uses before appending a word to the
sentence.

## Known limitations

- **Real measured accuracy on the 220-word model: 8.6% validation
  top-1** (stratified split, `train_word_model.py`'s printed number).
  That's ~19x better than random chance for 220 classes (~0.45%), and
  a quick spot-check of 5 held-out-style clips got the right word in
  the top-5 predictions 2/5 times (~40%, vs. ~2.3% random top-5
  baseline) — so the model is genuinely learning real signal, not
  degenerate. But treat this as a real, working, modest-accuracy
  system, not a polished 220-word product. Recording extra clips per
  word with `collect_webcam_words.py` (real per-class data is the
  actual bottleneck, per the WLASL-2000 analysis above) is the fastest
  way to improve it.
- **9-16 clips/word** (curated from WLASL, see "Why 220 words" above) —
  still modest per-class data even after this expansion. Consecutive
  frames within a clip are correlated, so treat the stratified-split
  accuracy number as an upper bound, not a signer-independent one.
- `mediapipe` is pinned to `0.10.9` in `requirements.txt` — see the
  comment there for why (newer wheels either drop the classic
  `mediapipe.solutions` API or fail to load on macOS < 14).
