import os

import word_video_lookup

SIGN_IMAGES_DIR = os.path.join("static", "sign_images")
ALPHABET_IMAGES_DIR = os.path.join("static", "alphabet_images")
ALPHABET_EXPRESSIONS_DIR = os.path.join("static", "alphabet_expressions")


def _build_lookup(directory, ext=".jpg"):
    """Maps UPPERCASE name -> actual filename on disk, so matching
    works regardless of whether the filesystem is case-insensitive
    (e.g. macOS default) or case-sensitive (e.g. Linux deployments)."""
    lookup = {}
    if os.path.isdir(directory):
        for fname in os.listdir(directory):
            name, fext = os.path.splitext(fname)
            if fext.lower() == ext:
                lookup[name.upper()] = fname
    return lookup


def convert_text(text, mode="word"):
    """
    mode="word" (default): looks up one whole-word sign per word in the
    input. First checks the hand-picked static/sign_images/ (unchanged
    behaviour, same images as before). If a word isn't there but IS one
    of the 220 words the word-level WLASL model knows
    (word_level/data/labels.json), falls back to a real sign *video*
    for it instead, served from word_level/wlasl_raw/ via the
    /word-clip/<word> route -- this is what connects the 220-word
    dataset to Text-to-Sign. Returns a list of
    {"type": "image"|"video", "word": ..., "src": ...} dicts.

    mode="alphabet": ignores whole-word images entirely and always
    spells every word out letter-by-letter using static/alphabet_images/,
    pairing each letter with its facial-expression reference image from
    static/alphabet_expressions/ where available. Returns a flat list of
    tokens: {"type": "letter", ...} for each letter, and
    {"type": "space"} between words, so the template can render word
    boundaries.
    """

    if mode == "alphabet":
        return _convert_text_alphabet(text)

    lookup = _build_lookup(SIGN_IMAGES_DIR)
    wlasl_words = set(word_video_lookup.list_words())

    results = []

    for raw_word in text.split():
        word_upper = raw_word.upper()
        word_lower = raw_word.lower()

        image_name = lookup.get(word_upper)
        if image_name:
            results.append({"type": "image", "word": raw_word, "src": image_name})
            continue

        if word_lower in wlasl_words:
            clip = word_video_lookup.first_clip_filename(word_lower)
            if clip:
                results.append({"type": "video", "word": word_lower, "src": word_lower})

    return results


def _convert_text_alphabet(text):
    hand_lookup = _build_lookup(ALPHABET_IMAGES_DIR)
    expr_lookup = _build_lookup(ALPHABET_EXPRESSIONS_DIR)

    words = text.upper().split()

    tokens = []

    for w_idx, word in enumerate(words):
        if w_idx > 0:
            tokens.append({"type": "space"})

        for ch in word:
            if not ch.isalpha():
                continue

            tokens.append({
                "type": "letter",
                "letter": ch,
                "hand_image": hand_lookup.get(ch),
                "expression_image": expr_lookup.get(ch),
            })

    return tokens