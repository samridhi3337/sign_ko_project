import json
import os
import sys
from flask import Flask, render_template, request, jsonify, send_from_directory, abort
import subprocess
import json
from text_to_sign_web import convert_text
import word_video_lookup

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "sign_animation"))
import gloss as sign_gloss  # noqa: E402
import config as sign_animation_config  # noqa: E402
import kozha as sign_kozha  # noqa: E402

app = Flask(__name__)
@app.route("/get_prediction")
def get_prediction():

    with open("prediction.json", "r") as f:
        data = json.load(f)

    return jsonify(data)

@app.route("/")
def home():
    return render_template("index.html")


# ---------------- Recognition ----------------

@app.route("/recognition")
def recognition():
    return render_template("recognition.html")



@app.route("/start-recognition")
def start_recognition():
    subprocess.Popen([sys.executable, "predict_sign_terminal.py"])
    return "Started"


# ---------------- Word-Level Recognition (WLASL-based) ----------------
# Additive, motion-aware upgrade: recognizes whole signed words/phrases
# from a landmark *sequence* instead of a single static hand pose. Does
# not touch or replace the static recognizer above.

WORD_PREDICTION_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "word_prediction.json"
)


@app.route("/start-word-recognition")
def start_word_recognition():
    word_level_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "word_level")
    subprocess.Popen([sys.executable, "predict_word_sign.py"], cwd=word_level_dir)
    return "Started"


@app.route("/get_word_prediction")
def get_word_prediction():
    if not os.path.exists(WORD_PREDICTION_FILE):
        return jsonify({"prediction": "Waiting...", "sentence": ""})

    with open(WORD_PREDICTION_FILE, "r") as f:
        data = json.load(f)

    return jsonify(data)


# ---------------- Alphabet (Fingerspelling) Recognition ----------------
# Letter-by-letter recognition that assembles words/sentences, paired
# with the user's own captured facial-expression reference image per
# letter. Additive: does not touch the two recognizers above.

ALPHABET_PREDICTION_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "alphabet_prediction.json"
)


@app.route("/start-alphabet-recognition")
def start_alphabet_recognition():
    alphabet_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "alphabet")
    subprocess.Popen([sys.executable, "predict_alphabet_sign.py"], cwd=alphabet_dir)
    return "Started"


@app.route("/get_alphabet_prediction")
def get_alphabet_prediction():
    if not os.path.exists(ALPHABET_PREDICTION_FILE):
        return jsonify({"letter": "", "word": "", "sentence": "", "expressions": []})

    with open(ALPHABET_PREDICTION_FILE, "r") as f:
        data = json.load(f)

    return jsonify(data)


# ---------------- Word Dictionary (220-word WLASL dataset) ----------------
# Connects the downloaded WLASL clips (word_level/wlasl_raw/) to the
# browser: a searchable list of every word the word-level model knows,
# each with its own real sign video, served without duplicating the
# ~956MB of video into static/.

@app.route("/word-dictionary")
def word_dictionary():
    return render_template("word_dictionary.html", words=word_video_lookup.list_words())


@app.route("/api/word-list")
def api_word_list():
    return jsonify({"words": word_video_lookup.list_words()})


@app.route("/word-clip/<word>")
def word_clip(word):
    # Validate against the known vocabulary before touching the
    # filesystem -- prevents path traversal via the URL segment.
    if not word_video_lookup.is_known_word(word):
        abort(404)

    filename = word_video_lookup.first_clip_filename(word)
    if not filename:
        abort(404)

    clip_dir = word_video_lookup.clip_dir_for_word(word)
    return send_from_directory(clip_dir, filename)


# ---------------- Text to Sign Animation (3D Avatar) ----------------
# Converts input text/sentences into a simplified sign-gloss sequence
# (sign_animation/gloss.py -- not a word-by-word translation) and
# serves the real captured-motion animation data for each token so the
# frontend (static/js/sign_animation.js) can play it on a 3D avatar.

@app.route("/sign-animation")
def sign_animation_page():
    return render_template("sign_animation.html")


@app.route("/api/sign-animation/gloss", methods=["POST"])
def api_sign_animation_gloss():
    text = request.get_json(silent=True) or {}
    text = text.get("text", "")

    sentences = sign_gloss.text_to_gloss(text)

    # Real Kozha/CWASA ASL data (see sign_animation/kozha.py and
    # README.md "Pass 7") is a SEPARATE, much smaller (14-sign) real
    # ASL source. It's only used for a request when EVERY word in the
    # WHOLE input resolves to something real in it (a genuine sign or
    # real fingerspelling) -- never mixed mid-playback with this
    # project's own much larger 250-word avatar, which stays the
    # default for anything Kozha can't fully cover.
    kozha_words = []
    for body, punct in sign_gloss._split_sentences(text):
        is_question = punct.startswith("?")
        kozha_words.extend(sign_gloss.sentence_to_gloss_words(body, is_question))
    kozha_sigml = sign_kozha.try_build_sigml(kozha_words) if kozha_words else None

    return jsonify({
        "sentences": sentences,
        "kozha": {"eligible": kozha_sigml is not None, "sigml": kozha_sigml},
    })

DICTIONARY_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "dictionary",
    "DictionaryGeneration-deploy-260828"
)

ASL_TO_DGS = {
    "hello": "HALLO",
    "water": "WASSER",
    "apple": "APFEL",
    "please": "BITTE",
    "danger": "GEFAHR",
    "cold": "KALT",
    "city": "STADT",
    "country": "LAND",
    "cousin": "COUSIN",
    "brother": "BRUDER",
    "child": "KIND",
    "future": "ZUKUNFT",
    "you": "INDEX",
    "i": "INDEX",
    "he": "INDEX",
    "she": "INDEX",
    "it": "INDEX",
    "we": "INDEX",
    "they": "INDEX",
    "me": "INDEX",
    "not": "NICHT",
    "nothing": "NICHT",
    "have": "HABEN",
    "need": "BRAUCHEN",
    "want": "WOLLEN",
    "go": "GEHEN",
    "come": "KOMMEN",
    "see": "ANSEHEN",
    "look": "AUSSEHEN",
    "know": "WISSEN",
    "say": "SAGEN",
    "think": "DENKEN",
    "make": "MACHEN",
    "work": "ARBEITEN",
    "time": "ZEIT",
    "day": "TAG",
    "year": "JAHR",
    "yes": "JA",
    "no": "NEIN",
    "good": "GUT",
    "bad": "SCHLECHT",
    "thank": "DANKE",
    "thanks": "DANKE",
    "but": "ABER",
    "all": "ALLE",
    "other": "ANDERE",
    "start": "ANFANGEN",
    "arrive": "ANKOMMEN",
    "also": "AUCH",
    "out": "AUS",
    "example": "BEISPIEL",
    "get": "BEKOMMEN",
    "picture": "BILD",
    "stay": "BLEIBEN",
    "inside": "DRINNEN",
}

def make_mms_csv(tokens):
    rows = ["maingloss,framestart,frameend,duration,transition,domgloss,ndomgloss"]
    rows.append("gest:PAUSENPOSITION,0,0,100%,0.2,,")
    for token in tokens:
        if token.get("type") == "word":
            word_lower = token["text"].lower()
            dgs_word = ASL_TO_DGS.get(word_lower)
            if dgs_word and os.path.exists(os.path.join(DICTIONARY_DIR, "signs", "trimmed", f"{dgs_word}.blend")):
                rows.append(f"signs:{dgs_word},0,0,100%,0.5,,")
            else:
                for char in word_lower:
                    if char.isalpha():
                        letter = char.upper()
                        if os.path.exists(os.path.join(DICTIONARY_DIR, "fa", "trimmed", f"{letter}.blend")):
                            rows.append(f"fa:{letter},0,0,100%,0.3,,")
        elif token.get("type") == "fingerspell":
            for char in token["text"].lower():
                if char.isalpha():
                    letter = char.upper()
                    if os.path.exists(os.path.join(DICTIONARY_DIR, "fa", "trimmed", f"{letter}.blend")):
                        rows.append(f"fa:{letter},0,0,100%,0.3,,")
        elif token.get("type") == "pause":
            rows.append("<HOLD>,0,0,0.5,0.1,,")
    rows.append("gest:PAUSENPOSITION,0,0,100%,0.4,,")
    return "\n".join(rows) + "\n"

@app.route("/api/sign-animation/mms", methods=["POST"])
def api_sign_animation_mms():
    text = request.get_json(silent=True) or {}
    text = text.get("text", "").strip()
    if not text:
        return jsonify({"error": "Empty text"}), 400

    sentences = sign_gloss.text_to_gloss(text)
    tokens = []
    for s in sentences:
        tokens.extend(s.get("tokens", []))
        if len(sentences) > 1 and s != sentences[-1]:
            tokens.append({"type": "pause", "text": "hold"})

    csv_content = make_mms_csv(tokens)

    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False) as f_csv:
        f_csv.write(csv_content)
        csv_path = f_csv.name

    json_path = csv_path.replace(".csv", ".json")

    python_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv_mms", "bin", "python")
    main_py_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mms_player_temp", "main.py")

    cmd = [
        python_path,
        main_py_path,
        "--source-mms-file", csv_path,
        "--dictionary-dir", DICTIONARY_DIR,
        "--use-relative-time",
        "--export-anim-json", json_path
    ]

    import subprocess
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = p.communicate()

    try:
        os.remove(csv_path)
    except:
        pass

    if not os.path.exists(json_path):
        return jsonify({"error": "MMS Player failed to generate animation", "stderr": stderr.decode("utf-8")}), 500

    with open(json_path, "r") as f_json:
        result_json = json.load(f_json)

    try:
        os.remove(json_path)
    except:
        pass

    return jsonify(result_json)


@app.route("/api/sign-animation/word/<word>")
def api_sign_animation_word(word):
    if not word_video_lookup.is_known_word(word):
        abort(404)

    path = os.path.join(sign_animation_config.WORDS_DIR, f"{word.lower()}.json")
    if not os.path.exists(path):
        abort(404)

    with open(path) as f:
        return jsonify(json.load(f))


@app.route("/api/sign-animation/letter/<letter>")
def api_sign_animation_letter(letter):
    letter = letter.upper()
    if len(letter) != 1 or letter not in sign_animation_config.LETTERS:
        abort(404)

    path = os.path.join(sign_animation_config.LETTERS_DIR, f"{letter}.json")
    if not os.path.exists(path):
        abort(404)

    with open(path) as f:
        return jsonify(json.load(f))


@app.route("/api/sign-animation/mocap/<word>")
def api_sign_animation_mocap(word):
    """Serves a real professional motion-capture FBX clip for `word`,
    if this project has one (see sign_animation/fetch_mocap_words.py
    and README.md "Pass 6") -- source: Studio Galt Sign Language
    Mocap Archive, CC0-1.0."""
    manifest_entry = sign_animation_config.mocap_manifest().get(word.lower())
    if not manifest_entry:
        abort(404)

    path = os.path.join(sign_animation_config.MOCAP_DIR, manifest_entry["file"])
    if not os.path.exists(path):
        abort(404)

    return send_from_directory(sign_animation_config.MOCAP_DIR, manifest_entry["file"])


# ---------------- Text to Sign ----------------

@app.route("/text-to-sign", methods=["GET", "POST"])
def text_to_sign():

    images = []
    tokens = []
    mode = request.form.get("mode", "word")

    if request.method == "POST":

        text = request.form["text"]

        result = convert_text(text, mode=mode)

        if mode == "alphabet":
            tokens = result
        else:
            images = result

    return render_template(
        "text_to_sign.html", images=images, tokens=tokens, mode=mode
    )


@app.route("/start-text-to-sign")
def start_text_to_sign():

    subprocess.Popen([sys.executable, "text_to_sign_terminal.py"])

    return render_template("text_to_sign.html", images=[])


# ---------------- About ----------------

@app.route("/about")
def about():
    return render_template("about.html")

if __name__ == "__main__":
    print("🚀 SignBridge Server running on http://127.0.0.1:5001 / http://localhost:5001")
    app.run(host="0.0.0.0", port=5001, debug=True)
    