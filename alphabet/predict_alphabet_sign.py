"""
Real-time ALPHABET (fingerspelling) recognition + Facial Expression Detection:
classifies each webcam frame's hand landmarks as a single letter and computes
the signer's facial expression (Happy, Sad, Surprised, Focused, Neutral).

Writes alphabet_prediction.json:
    {
      "letter": "<current stable letter>",
      "confidence": "94%",
      "expression": "Happy 😊",
      "word": "<word being spelled>",
      "sentence": "<committed sentence>",
      "expressions": [{"letter": "H", "image": "H.jpg"}, ...]
    }

Usage:
    python alphabet/predict_alphabet_sign.py             # live webcam
    python alphabet/predict_alphabet_sign.py --dry-run img1.jpg img2.jpg ...
"""

import argparse
import json
import os
import pickle
import time
from collections import deque

import cv2
import mediapipe as mp
import numpy as np

import config

mp_hands = mp.solutions.hands
mp_face_mesh = mp.solutions.face_mesh
mp_draw = mp.solutions.drawing_utils

CONFIDENCE_THRESHOLD = 0.35


def load_model():
    with open(config.MODEL_PATH, "rb") as f:
        bundle = pickle.load(f)
    return bundle["model"], bundle["labels"]


def extract_features(hand_landmarks):
    features = []
    base_x = hand_landmarks.landmark[0].x
    base_y = hand_landmarks.landmark[0].y

    for lm in hand_landmarks.landmark:
        features.append(lm.x - base_x)
        features.append(lm.y - base_y)

    max_value = max(max(abs(v) for v in features), 1e-6)
    return [v / max_value for v in features]


def detect_expression(rgb_image, face_mesh_processor):
    results = face_mesh_processor.process(rgb_image)
    if not results.multi_face_landmarks:
        return "Neutral 😐"

    landmarks = results.multi_face_landmarks[0].landmark
    h, w, _ = rgb_image.shape
    pts = np.array([[lm.x * w, lm.y * h] for lm in landmarks])

    mouth_width = np.linalg.norm(pts[61] - pts[291])
    mouth_height = np.linalg.norm(pts[13] - pts[14])
    mar = mouth_height / max(mouth_width, 1e-6)

    left_brow_height = np.linalg.norm(pts[70] - pts[159])
    right_brow_height = np.linalg.norm(pts[300] - pts[386])
    avg_brow_height = (left_brow_height + right_brow_height) / 2.0

    mouth_center_y = (pts[13][1] + pts[14][1]) / 2.0
    corner_y = (pts[61][1] + pts[291][1]) / 2.0
    smile_delta = mouth_center_y - corner_y

    if mar > 0.35 and avg_brow_height > 18:
        return "Surprised 😲"
    elif smile_delta > 2.5 or (mar > 0.15 and smile_delta > 0.8):
        return "Happy 😊"
    elif smile_delta < -2.5:
        return "Sad 😔"
    elif mar < 0.08 and avg_brow_height < 12:
        return "Focused 🧐"
    return "Neutral 😐"


def expressions_for_word(word):
    result = []
    for letter in word:
        image_name = f"{letter}.jpg"
        image_path = os.path.join(config.ALPHABET_EXPRESSIONS_DIR, image_name)
        result.append({
            "letter": letter,
            "image": image_name if os.path.exists(image_path) else None,
        })
    return result


def write_prediction(letter, word, sentence, confidence_str="", expression="Neutral 😐"):
    with open(config.ALPHABET_PREDICTION_JSON, "w") as f:
        json.dump({
            "letter": letter,
            "confidence": confidence_str,
            "expression": expression,
            "word": word,
            "sentence": sentence,
            "expressions": expressions_for_word(word),
        }, f)


class FingerspellRecognizer:
    def __init__(self, model, labels, hold_seconds=0.7, no_hand_word_break=1.0):
        self.model = model
        self.labels = labels
        self.hold_seconds = hold_seconds
        self.no_hand_word_break = no_hand_word_break

        self.history = deque(maxlen=7)
        self.expression_history = deque(maxlen=5)
        self.stable_letter = ""
        self.last_letter = ""
        self.hold_start = None
        self.letter_added = False
        self.current_confidence = 0.0
        self.current_expression = "Neutral 😐"

        self.word = ""
        self.sentence_words = []
        self.no_hand_since = None

    def _predict_with_conf(self, feats):
        if hasattr(self.model, "predict_proba"):
            probs = self.model.predict_proba([feats])[0]
            max_idx = int(probs.argmax())
            conf = float(probs[max_idx])
            if conf >= CONFIDENCE_THRESHOLD:
                return self.labels[max_idx], conf
            else:
                return "", conf
        else:
            idx = self.model.predict([feats])[0]
            return self.labels[idx], 1.0

    def update_expression(self, raw_expr):
        self.expression_history.append(raw_expr)
        if self.expression_history:
            self.current_expression = max(set(self.expression_history), key=self.expression_history.count)

    def on_hand_frame(self, feats):
        self.no_hand_since = None

        raw, conf = self._predict_with_conf(feats)
        self.current_confidence = conf

        if raw:
            self.history.append(raw)

        if len(self.history) >= 3:
            counts = {item: self.history.count(item) for item in set(self.history)}
            best_item, best_count = max(counts.items(), key=lambda x: x[1])
            if best_count >= 2:
                self.stable_letter = best_item
        elif self.history:
            self.stable_letter = self.history[-1]

        if self.stable_letter and self.stable_letter == self.last_letter:
            if self.hold_start is None:
                self.hold_start = time.time()
            elif time.time() - self.hold_start >= self.hold_seconds and not self.letter_added:
                self.word += self.stable_letter
                self.letter_added = True
        else:
            self.hold_start = time.time()
            self.letter_added = False

        self.last_letter = self.stable_letter
        return self.stable_letter, self.current_confidence

    def on_no_hand_frame(self):
        self.history.clear()
        self.stable_letter = ""
        self.last_letter = ""
        self.hold_start = None
        self.letter_added = False
        self.current_confidence = 0.0

        if self.word:
            if self.no_hand_since is None:
                self.no_hand_since = time.time()
            elif time.time() - self.no_hand_since >= self.no_hand_word_break:
                self.sentence_words.append(self.word)
                self.word = ""
                self.no_hand_since = None

    @property
    def sentence(self):
        return " ".join(self.sentence_words)


def run_live():
    print("Loading alphabet model...")
    model, labels = load_model()
    print(f"Loaded. Letters ({len(labels)}): {labels}")

    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        min_detection_confidence=0.6,
        min_tracking_confidence=0.6,
    )
    face_mesh = mp_face_mesh.FaceMesh(static_image_mode=False, max_num_faces=1)

    recognizer = FingerspellRecognizer(model, labels)

    cap = cv2.VideoCapture(0)
    cv2.namedWindow("Alphabet Recognition", cv2.WND_PROP_FULLSCREEN)
    cv2.setWindowProperty("Alphabet Recognition", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    write_prediction("Waiting...", "", "", "", "Neutral 😐")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Camera Error")
            break

        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Detect Facial Expression
        expr = detect_expression(rgb, face_mesh)
        recognizer.update_expression(expr)

        result = hands.process(rgb)

        if result.multi_hand_landmarks:
            hand_landmarks = result.multi_hand_landmarks[0]
            mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
            feats = extract_features(hand_landmarks)
            stable, conf = recognizer.on_hand_frame(feats)
            conf_str = f"{int(conf * 100)}%" if stable else ""
        else:
            recognizer.on_no_hand_frame()
            stable = ""
            conf_str = ""

        disp_letter = stable if stable else ("Listening..." if result.multi_hand_landmarks else "Waiting for hand...")
        write_prediction(disp_letter, recognizer.word, recognizer.sentence, conf_str, recognizer.current_expression)

        cv2.putText(frame, f"Letter: {disp_letter} {conf_str}", (20, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(frame, f"Expression: {recognizer.current_expression}", (20, 90),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 100, 250), 2)
        cv2.putText(frame, f"Word: {recognizer.word}", (20, 130),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 200, 0), 2)
        cv2.putText(frame, f"Sentence: {recognizer.sentence}", (20, 170),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 200, 255), 2)

        cv2.imshow("Alphabet Recognition", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == 27:
            break
        elif key == ord(' '):
            if recognizer.word:
                recognizer.sentence_words.append(recognizer.word)
                recognizer.word = ""
        elif key == ord('c'):
            recognizer.sentence_words.clear()
            recognizer.word = ""
            write_prediction("Waiting...", "", "", "", "Neutral 😐")

    cap.release()
    cv2.destroyAllWindows()
    hands.close()
    face_mesh.close()


def run_dry_run(image_paths):
    print("Loading alphabet model...")
    model, labels = load_model()
    print(f"Loaded. Letters ({len(labels)}): {labels}")

    hands = mp_hands.Hands(static_image_mode=True, max_num_hands=1, min_detection_confidence=0.5)
    face_mesh = mp_face_mesh.FaceMesh(static_image_mode=True, max_num_faces=1)
    recognizer = FingerspellRecognizer(model, labels, hold_seconds=0.0, no_hand_word_break=0.0)

    for path in image_paths:
        image = cv2.imread(path)
        if image is None:
            print(f"  {path}: could not read")
            continue

        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        expr = detect_expression(rgb, face_mesh)
        result = hands.process(rgb)

        if result.multi_hand_landmarks:
            feats = extract_features(result.multi_hand_landmarks[0])
            stable, conf = recognizer.on_hand_frame(feats)
            print(f"  {path}: letter '{stable}' ({int(conf*100)}%), expression: {expr}")
        else:
            recognizer.on_no_hand_frame()
            print(f"  {path}: no hand detected, expression: {expr}")

    hands.close()
    face_mesh.close()
    print(f"\nWord so far: '{recognizer.word}'")
    print(f"Sentence: '{recognizer.sentence}'")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run", nargs="+", metavar="IMAGE_PATH", default=None,
        help="Run headlessly over a sequence of saved images instead of the live webcam.",
    )
    args = parser.parse_args()

    if args.dry_run:
        run_dry_run(args.dry_run)
    else:
        run_live()
