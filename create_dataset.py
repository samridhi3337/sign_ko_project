import os
import csv
import cv2
import mediapipe as mp

mp_hands = mp.solutions.hands

hands = mp_hands.Hands(
    static_image_mode=True,
    max_num_hands=1,
    min_detection_confidence=0.5
)

DATASET_PATH = "dataset"
CSV_FILE = "data.csv"

data = []

for label in os.listdir(DATASET_PATH):

    label_path = os.path.join(DATASET_PATH, label)

    if not os.path.isdir(label_path):
        continue

    print("Processing:", label)

    for image_name in os.listdir(label_path):

        image_path = os.path.join(label_path, image_name)

        image = cv2.imread(image_path)

        if image is None:
            continue

        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        result = hands.process(rgb)

        if result.multi_hand_landmarks:

            hand = result.multi_hand_landmarks[0]

            # -----------------------------
            # Normalize Landmarks
            # -----------------------------
            features = []

            base_x = hand.landmark[0].x
            base_y = hand.landmark[0].y

            for lm in hand.landmark:
                features.append(lm.x - base_x)
                features.append(lm.y - base_y)

            max_value = max(max(abs(x) for x in features), 1e-6)
            features = [x / max_value for x in features]

            features.append(label)

            data.append(features)

with open(CSV_FILE, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerows(data)

print("Dataset Created Successfully!")
print("Total Samples:", len(data))