"""
Simplifies input English text into a sign-appropriate token sequence
("gloss") instead of translating word-by-word. This is a documented,
simplified heuristic -- not a full ASL syntax parser (that's a real
linguistics/NLP research problem) -- but it does real, meaningful
transformations:

  - drops English function words ASL conventionally omits (articles,
    copula "be" forms, empty "do/does/did")
  - keeps negation intact ("not"/"n't") -- dropping it would invert
    the sentence's meaning, so it's explicitly protected
  - reorders WH-questions to put the question word at the end,
    matching real ASL gloss convention, instead of English word order
  - maps each remaining content word to either a known sign (if it's
    one of the words the word-level model/animation data covers) or
    fingerspelling (letter-by-letter) as a fallback
  - classifies each sentence as a statement / yes-no question / WH
    question, so the avatar can hold the correct ASL non-manual marker
    (a real, documented grammatical feature, not invented) for the
    sentence's whole duration -- see SENTENCE_TYPE below

See sign_animation/README.md for the full rationale and limitations.
"""

import re
import string

import config

CONTRACTIONS = {
    "don't": "do not", "doesn't": "does not", "didn't": "did not",
    "can't": "can not", "won't": "will not", "wouldn't": "would not",
    "shouldn't": "should not", "couldn't": "could not",
    "isn't": "is not", "aren't": "are not", "wasn't": "was not",
    "weren't": "were not", "haven't": "have not", "hasn't": "has not",
    "hadn't": "had not",
    "i'm": "i am", "you're": "you are", "he's": "he is", "she's": "she is",
    "it's": "it is", "we're": "we are", "they're": "they are",
    "i've": "i have", "you've": "you have", "we've": "we have",
    "they've": "they have",
    "i'll": "i will", "you'll": "you will", "he'll": "he will",
    "she'll": "she will", "we'll": "we will", "they'll": "they will",
    "i'd": "i would", "you'd": "you would", "he'd": "he would",
    "she'd": "she would", "we'd": "we would", "they'd": "they would",
    "let's": "let us", "that's": "that is", "what's": "what is",
    "who's": "who is", "where's": "where is",
}

# Function words ASL conventionally drops. NOTE: "not" is deliberately
# NOT in this list -- negation changes meaning and must be preserved.
DROP_WORDS = {
    "a", "an", "the",
    "is", "am", "are", "was", "were", "be", "being", "been",
    "do", "does", "did",
    "of", "to",
}

WH_WORDS = {"what", "where", "when", "why", "who", "how", "which"}

# Real ASL non-manual grammar (documented in ASL linguistics -- e.g.
# Baker-Shenk & Cokely, Neidle et al. -- not invented here): yes/no
# questions are marked by RAISED eyebrows + a forward head tilt held
# through the whole question; WH-questions are marked by LOWERED/
# furrowed eyebrows + forward head tilt. These are genuinely different
# markers, not the same "question face" -- see SENTENCE_TYPE.
SENTENCE_TYPE = {
    "statement": {"eyebrow": 0.0, "head_tilt_deg": 0.0},
    "yn_question": {"eyebrow": 1.0, "head_tilt_deg": 8.0},
    "wh_question": {"eyebrow": -1.0, "head_tilt_deg": 8.0},
}

# ASL prosody research (e.g. Wilbur's work on stress/prosodic structure
# in ASL) documents "final lengthening" -- the last sign in a phrase or
# sentence is held measurably longer than the same sign mid-sentence,
# the same phenomenon spoken languages show at phrase boundaries. This
# is a timing-only inflection applied to the sign's own real captured
# motion (see sign_animation/README.md "Pass 5") -- never a different
# or invented handshape, just how long the real motion is held/played.
PHRASE_FINAL_HOLD_MULTIPLIER = 1.4

PUNCT_TABLE = str.maketrans("", "", string.punctuation.replace("'", ""))


def _expand_contractions(sentence_lower):
    words = sentence_lower.split()
    return " ".join(CONTRACTIONS.get(w, w) for w in words)


def _split_sentences(text):
    # Keep the trailing punctuation so we can detect questions, then
    # strip it off per-sentence afterwards.
    parts = re.split(r'([.!?]+)', text.strip())
    sentences = []
    for i in range(0, len(parts) - 1, 2):
        body = parts[i].strip()
        punct = parts[i + 1].strip()
        if body:
            sentences.append((body, punct))
    if len(parts) % 2 == 1 and parts[-1].strip():
        sentences.append((parts[-1].strip(), ""))
    return sentences


def _tokenize(sentence_body):
    lowered = sentence_body.lower()
    lowered = _expand_contractions(lowered)
    lowered = lowered.translate(PUNCT_TABLE)
    return [w for w in lowered.split() if w]


def sentence_to_gloss_words(sentence_body, is_question):
    words = _tokenize(sentence_body)

    is_wh_question = is_question and words and words[0] in WH_WORDS
    wh_word = None
    if is_wh_question:
        wh_word = words[0]
        words = words[1:]

    words = [w for w in words if w not in DROP_WORDS]

    if is_wh_question:
        words.append(wh_word)

    return words


def word_to_token(word, known_words, mocap_words=None):
    word = word.strip("'")
    if not word:
        return None

    if word in known_words:
        token = {"type": "word", "text": word}
        # Real professional motion-capture data (Xsens suit + finger-
        # tracking gloves), not video-estimated -- see README "Pass 6"
        # -- preferred over this project's own WLASL-derived data for
        # any word the archive covers. The frontend fetches a
        # different endpoint/pipeline for these -- see
        # static/js/sign_animation.js `playMocapWord`.
        if mocap_words and word in mocap_words:
            token["mocap"] = True
        return token

    letters = [c for c in word if c.isalpha()]
    if not letters:
        # e.g. pure numbers/symbols. ASL numbers use dedicated
        # handshapes, not letter-by-letter fingerspelling, and this
        # project has no captured motion for them (the alphabet dataset
        # only covers A-Z) -- so rather than fabricate a handshape or
        # silently drop the word, the caller surfaces it as "unsigned"
        # (see text_to_gloss) so the gap is visible, not hidden.
        return None

    return {"type": "fingerspell", "text": "".join(letters)}


def text_to_gloss(text, known_words=None):
    """
    Returns a list of sentences:
        {
          "type": "statement" | "yn_question" | "wh_question",
          "tokens": [{"type": "word", "text": "hello", ...}, ...],
          "unsigned": ["5", ...],
        }
    `type` drives which real ASL non-manual marker (see SENTENCE_TYPE)
    the avatar holds for that sentence's whole duration. The last token
    in `tokens` (if any) carries `"phrase_final": True`, driving the
    real-motion hold-lengthening described above SENTENCE_TYPE.
    `unsigned` lists input words this project has no real sign or
    fingerspelling data for (currently: numbers/symbols) so the caller
    can disclose the gap instead of silently dropping the word. A
    "word" token additionally carries `"mocap": True` when a real
    professional motion-capture clip is available for it (see
    README.md "Pass 6") -- the frontend fetches and plays that instead
    of this project's own WLASL-derived data for those words.
    """
    if known_words is None:
        known_words = set(config.known_words())
    else:
        known_words = set(known_words)
    mocap_words = config.mocap_words()

    sentences_out = []

    for body, punct in _split_sentences(text):
        is_question = punct.startswith("?")
        raw_words = _tokenize(body)
        # Checks for a WH-word anywhere in the sentence, not just the
        # first position -- "Hello, how are you?" is still a WH
        # question grammatically even though "hello" comes first.
        is_wh_question = is_question and any(w in WH_WORDS for w in raw_words)

        if is_wh_question:
            sentence_type = "wh_question"
        elif is_question:
            sentence_type = "yn_question"
        else:
            sentence_type = "statement"

        words = sentence_to_gloss_words(body, is_question)

        tokens = []
        unsigned = []
        for w in words:
            tok = word_to_token(w, known_words, mocap_words)
            if tok:
                tokens.append(tok)
            else:
                unsigned.append(w)

        if tokens:
            tokens[-1]["phrase_final"] = True

        if tokens or unsigned:
            sentences_out.append({
                "type": sentence_type,
                "tokens": tokens,
                "unsigned": unsigned,
            })

    return sentences_out
