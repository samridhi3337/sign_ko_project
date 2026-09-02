
import json
import cv2
print("1")

import mediapipe as mp
print("2")

import pickle
print("3")

import time
print("4")

import pygame
print("5")

import pywhatkit
print("6")

print("Loading model...")
model = pickle.load(open("model.pkl", "rb"))
print("Model Loaded Successfully")

print("Initializing pygame...")
pygame.mixer.init()
print("Pygame initialized")

# =========================
# MediaPipe Hands
# =========================
mp_hands = mp.solutions.hands

hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7
)

mp_draw = mp.solutions.drawing_utils

print("Opening camera...")
cap = cv2.VideoCapture(0)
print("Camera opened")
mp_hands = mp.solutions.hands

hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7
)

mp_draw = mp.solutions.drawing_utils

# =========================
# Open Camera
# =========================
cap = cv2.VideoCapture(0)

# Full Screen
cv2.namedWindow("Sign Language Emergency System", cv2.WND_PROP_FULLSCREEN)
cv2.setWindowProperty(
    "Sign Language Emergency System",
    cv2.WND_PROP_FULLSCREEN,
    cv2.WINDOW_FULLSCREEN
)

# =========================
# Sentence Variables
# =========================
sentence = []

current_word = ""
last_word = ""

start_time = None
word_added = False

# Stable Prediction Variables
prediction_history = []
stable_prediction = ""

# =========================
# Emergency Settings
# =========================
emergency_words = ["Help", "Danger", "Emergency"]

emergency_number = "+917006301254"

emergency_message = "Emergency! I need help immediately."

location_link = "https://maps.google.com/?q=12.9716,77.5946"

alarm_playing = False
message_sent = False

# =========================
# Main Loop
# =========================
while True:

    ret, frame = cap.read()

    if not ret:
        print("Camera Error")
        break

    # Mirror View
    frame = cv2.flip(frame, 1)

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    result = hands.process(rgb)

    if result.multi_hand_landmarks:

        for hand_landmarks in result.multi_hand_landmarks:

            # Normalize Landmarks
            features = []

            base_x = hand_landmarks.landmark[0].x
            base_y = hand_landmarks.landmark[0].y

            for lm in hand_landmarks.landmark:
                features.append(lm.x - base_x)
                features.append(lm.y - base_y)

            max_value = max(max(abs(x) for x in features), 1e-6)
            features = [x / max_value for x in features]

            # Draw Hand
            mp_draw.draw_landmarks(
                frame,
                hand_landmarks,
                mp_hands.HAND_CONNECTIONS
            )

            # Predict with confidence
            conf_str = ""
            if hasattr(model, "predict_proba"):
                probs = model.predict_proba([features])[0]
                best_idx = probs.argmax()
                conf = float(probs[best_idx])
                if conf >= 0.35:
                    prediction = model.classes_[best_idx]
                    conf_str = f"{int(conf * 100)}%"
                else:
                    prediction = ""
            else:
                prediction = model.predict([features])[0]

            if prediction:
                prediction_history.append(prediction)

            if len(prediction_history) > 5:
                prediction_history.pop(0)

            if prediction_history and prediction_history.count(prediction_history[-1]) >= 3:
                stable_prediction = prediction_history[-1]

            current_word = stable_prediction

            disp_pred = current_word if current_word else "Listening..."
            with open("prediction.json", "w") as f:
                json.dump({
                    "prediction": disp_pred,
                    "confidence": conf_str,
                    "sentence": " ".join(sentence)
                }, f)

            # Hold Prediction
            if current_word and current_word == last_word:

                if start_time is None:
                    start_time = time.time()

                elif time.time() - start_time >= 0.8 and not word_added:

                    sentence.append(current_word)
                    word_added = True
                    print("\n==============================")
                    print("Current Sentence:", " ".join(sentence))
                    print("==============================")
                    with open("prediction.json", "w") as f:
                        json.dump({
                          "prediction": current_word,
                          "confidence": conf_str,
                          "sentence": " ".join(sentence)
                        }, f)

                    # Emergency Detection
                    if current_word in emergency_words:

                        print("Emergency Detected!")

                        if not alarm_playing:
                            pygame.mixer.music.load("alarm.mp3")
                            pygame.mixer.music.play(-1)
                            alarm_playing = True

                        if not message_sent:

                            pywhatkit.sendwhatmsg_instantly(
                                emergency_number,
                                emergency_message,
                                wait_time=20,
                                tab_close=True,
                                close_time=5
                            )

                            time.sleep(3)

                            pywhatkit.sendwhatmsg_instantly(
                                emergency_number,
                                location_link,
                                wait_time=20,
                                tab_close=True,
                                close_time=5
                            )

                            message_sent = True

            else:
                start_time = time.time()
                word_added = False

            last_word = current_word

    else:
        prediction_history.clear()
        stable_prediction = ""
        current_word = ""
        last_word = ""
        start_time = None
        word_added = False

    # Display Sentence
    cv2.putText(
        frame,
        "Sentence: " + " ".join(sentence),
        (20, 50),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (0, 255, 0),
        2
    )

    # Show Camera
    cv2.imshow("Sign Language Emergency System", frame)

    key = cv2.waitKey(1) & 0xFF

    # ESC to Exit
    if key == 27:
        break

    # Press C to Clear Sentence
    elif key == ord('c'):
        sentence.clear()
        with open("prediction.json", "w") as f:
            json.dump({
                "prediction": "Waiting...",
                "sentence": ""
            }, f)

        if alarm_playing:
            pygame.mixer.music.stop()
            alarm_playing = False

        message_sent = False

# Cleanup
cap.release()
cv2.destroyAllWindows()
pygame.quit()