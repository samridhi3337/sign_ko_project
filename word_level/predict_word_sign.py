"""
Real-time WORD-LEVEL sign recognition + Facial Expression Tracking:
buffers a rolling window of webcam frames, extracts MediaPipe Holistic
landmarks, classifies sign motions with word_model.h5, and tracks the
signer's facial expression.

Writes word_prediction.json:
    {
      "prediction": "<current candidate word>",
      "confidence": "85%",
      "expression": "Happy 😊",
      "sentence": "<assembled sentence>"
    }

Usage:
    python word_level/predict_word_sign.py            # live webcam
    python word_level/predict_word_sign.py --dry-run path/to/clip.mp4
"""

import argparse
import json
import sys
import time
from collections import deque

import cv2
import numpy as np

import config
from landmarks import extract_frame_features, make_holistic, resample_sequence


def load_model_and_labels():
    import os, pickle
    root_model = None
    root_model_path = os.path.join(config.BASE_DIR, "..", "model.pkl")
    if os.path.exists(root_model_path):
        try:
            with open(root_model_path, "rb") as f:
                root_model = pickle.load(f)
        except Exception as e:
            print("Root model load note:", e)

    pkl_path = os.path.join(config.MODEL_DIR, "word_model.pkl")
    if os.path.exists(pkl_path):
        with open(pkl_path, "rb") as f:
            bundle = pickle.load(f)
        return bundle["model"], bundle["labels"], True, root_model
    
    from tensorflow import keras
    model = keras.models.load_model(config.MODEL_PATH)
    with open(config.LABELS_PATH) as f:
        labels = json.load(f)
    return model, labels, False, root_model


def detect_expression_from_holistic(results, image_shape=(480, 640)):
    if not results or not results.face_landmarks:
        return "Neutral 😐"
    landmarks = results.face_landmarks.landmark
    h, w = image_shape[:2]
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


def write_prediction(prediction, sentence, confidence_str="", expression="Neutral 😐"):
    with open(config.WORD_PREDICTION_JSON, "w") as f:
        json.dump({
            "prediction": prediction,
            "confidence": confidence_str,
            "expression": expression,
            "sentence": " ".join(sentence) if isinstance(sentence, list) else sentence
        }, f)


class SlidingWindowRecognizer:
    def __init__(self, model, labels, is_pkl=True, root_model=None, confidence_threshold=0.15):
        self.model = model
        self.labels = labels
        self.is_pkl = is_pkl
        self.root_model = root_model
        self.confidence_threshold = confidence_threshold
        self.buffer = deque(maxlen=config.SEQUENCE_LENGTH)
        self.history = deque(maxlen=7)
        self.expression_history = deque(maxlen=5)
        self.sentence = []
        self.last_confirmed = ""
        self.hold_start = None
        self.word_added = False
        self.current_confidence = 0.0
        self.current_expression = "Neutral 😐"
        self.last_results = None
        self.no_hand_count = 0

    def push_frame(self, results):
        self.last_results = results
        has_hand = False
        if results and (results.left_hand_landmarks is not None or results.right_hand_landmarks is not None):
            has_hand = True

        if has_hand:
            self.no_hand_count = 0
            self.buffer.append(extract_frame_features(results))
        else:
            self.no_hand_count += 1
            if self.no_hand_count >= 4:
                self.buffer.clear()
                self.history.clear()

    def update_expression(self, raw_expr):
        self.expression_history.append(raw_expr)
        if self.expression_history:
            self.current_expression = max(set(self.expression_history), key=self.expression_history.count)

    def predict(self):
        # 1. Check exact geometric hand signature (e.g., water, hello, help, i, need, danger, you)
        from landmarks import detect_anchor_sign
        anchor_word, anchor_conf = detect_anchor_sign(self.last_results)
        if anchor_word and anchor_conf >= 0.85:
            return anchor_word, anchor_conf

        if len(self.buffer) < 10 or self.no_hand_count >= 2:
            return None, 0.0

        seq = resample_sequence(list(self.buffer), config.SEQUENCE_LENGTH)
        if self.is_pkl:
            from landmarks import extract_sequence_features
            feats = extract_sequence_features(seq)
            probs = self.model.predict_proba([feats])[0]
        else:
            seq_input = np.expand_dims(seq, axis=0)
            probs = self.model.predict(seq_input, verbose=0)[0]

        idx = int(np.argmax(probs))
        return self.labels[idx], float(probs[idx])

    def step(self):
        label, conf = self.predict()
        self.current_confidence = conf

        if label is None or conf < self.confidence_threshold:
            self.history.append("")
        else:
            self.history.append(label)

        if self.history:
            counts = {item: self.history.count(item) for item in set(self.history) if item}
            if counts:
                stable, count = max(counts.items(), key=lambda x: x[1])
                if count < 3:
                    stable = ""
            else:
                stable = ""
        else:
            stable = ""

        confirmed = None
        if stable and stable == self.last_confirmed:
            if self.hold_start is None:
                self.hold_start = time.time()
            elif time.time() - self.hold_start >= 0.6 and not self.word_added:
                if not self.sentence or self.sentence[-1] != stable:
                    self.sentence.append(stable)
                    self.word_added = True
                    confirmed = stable
        else:
            self.hold_start = time.time()
            self.word_added = False

        self.last_confirmed = stable
        return stable, confirmed, self.current_confidence


def run_live():
    print("Loading word-level model...")
    model, labels, is_pkl, root_model = load_model_and_labels()
    print(f"Loaded. Vocabulary ({len(labels)}): {labels}")

    import pygame
    import pywhatkit

    try:
        pygame.mixer.init()
    except Exception as e:
        print("Pygame mixer init warning:", e)

    holistic = make_holistic(static_image_mode=False)
    recognizer = SlidingWindowRecognizer(model, labels, is_pkl=is_pkl, root_model=root_model)

    emergency_number = "+917006301254"
    location_link = "https://maps.google.com/?q=12.9716,77.5946"
    alarm_playing = False
    last_alert_time = 0.0
    COOLDOWN_SECONDS = 60.0

    cap = cv2.VideoCapture(0)

    cv2.namedWindow("Word-Level Sign Recognition", cv2.WND_PROP_FULLSCREEN)
    cv2.setWindowProperty(
        "Word-Level Sign Recognition", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN
    )

    write_prediction("Waiting...", [], "", "Neutral 😐")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Camera Error")
            break

        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        results = holistic.process(rgb)

        expr = detect_expression_from_holistic(results, frame.shape)
        recognizer.update_expression(expr)

        recognizer.push_frame(results)
        stable, confirmed, conf = recognizer.step()

        conf_str = f"{int(conf * 100)}%" if stable else ""
        disp_pred = stable if stable else "Listening..."

        write_prediction(disp_pred, recognizer.sentence, conf_str, recognizer.current_expression)

        if confirmed:
            sentence_text = " ".join(recognizer.sentence).lower()
            print("\n==============================")
            print("Current Sentence:", sentence_text.upper())
            print("==============================")

            # Emergency rule: ONLY trigger for HELP (or DANGER) with high confidence/stability
            is_help_emergency = (confirmed.lower() in config.EMERGENCY_WORDS and conf >= 0.85) or ("help" in sentence_text)

            if is_help_emergency:
                now = time.time()
                print("🚨 CONFIDENT HELP EMERGENCY DETECTED! 🚨")

                if not alarm_playing:
                    try:
                        pygame.mixer.music.load(config.ALARM_PATH)
                        pygame.mixer.music.play(-1)
                        alarm_playing = True
                    except Exception as e:
                        print("Alarm play error:", e)

                if (now - last_alert_time) > COOLDOWN_SECONDS:
                    try:
                        emergency_text = "Emergency! I need help immediately."
                        print(f"Sending WhatsApp alert to {emergency_number}...")
                        pywhatkit.sendwhatmsg_instantly(
                            emergency_number, emergency_text,
                            wait_time=15, tab_close=True, close_time=5,
                        )
                        time.sleep(2)
                        pywhatkit.sendwhatmsg_instantly(
                            emergency_number, location_link,
                            wait_time=15, tab_close=True, close_time=5,
                        )
                        last_alert_time = now
                    except Exception as e:
                        print("WhatsApp error:", e)

        cv2.putText(
            frame, "Sentence: " + " ".join(recognizer.sentence),
            (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2,
        )
        cv2.putText(
            frame, "Predicting: " + disp_pred + f" {conf_str}",
            (20, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 200, 0), 2,
        )
        cv2.putText(
            frame, "Expression: " + recognizer.current_expression,
            (20, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 100, 250), 2,
        )

        cv2.imshow("Word-Level Sign Recognition", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == 27:
            break
        elif key == ord('c'):
            recognizer.sentence.clear()
            write_prediction("Waiting...", [], "", "Neutral 😐")
            if alarm_playing:
                try:
                    pygame.mixer.music.stop()
                except:
                    pass
                alarm_playing = False
            message_sent = False

    cap.release()
    cv2.destroyAllWindows()
    holistic.close()
    try:
        pygame.quit()
    except:
        pass


def run_dry_run(video_path):
    print("Loading word-level model...")
    model, labels, is_pkl, root_model = load_model_and_labels()
    print(f"Loaded. Vocabulary ({len(labels)}): {labels}")

    holistic = make_holistic(static_image_mode=False)
    recognizer = SlidingWindowRecognizer(model, labels, is_pkl=is_pkl, root_model=root_model)

    cap = cv2.VideoCapture(video_path)
    frame_count = 0
    predictions_seen = []

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_count += 1

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        results = holistic.process(rgb)

        expr = detect_expression_from_holistic(results, frame.shape)
        recognizer.update_expression(expr)

        recognizer.push_frame(results)
        stable, confirmed, conf = recognizer.step()
        if stable:
            predictions_seen.append((stable, conf, recognizer.current_expression))

    cap.release()
    holistic.close()

    print(f"\nProcessed {frame_count} frames from {video_path}")
    print(f"Predictions seen (tail): {predictions_seen[-10:]}")
    if predictions_seen:
        preds_only = [p[0] for p in predictions_seen]
        final = max(set(preds_only), key=preds_only.count)
        print(f"Majority prediction: {final}, expression: {recognizer.current_expression}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run", metavar="VIDEO_PATH", default=None,
        help="Run headlessly against a saved video file instead of the live webcam.",
    )
    args = parser.parse_args()

    if args.dry_run:
        run_dry_run(args.dry_run)
    else:
        run_live()
