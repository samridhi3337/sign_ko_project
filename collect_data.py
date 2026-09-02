import cv2
import os

label = "Hello"   # change later

path = f"dataset/{label}"

if not os.path.exists(path):
    os.makedirs(path)

cap = cv2.VideoCapture(0)
count = 0

while True:
    ret, frame = cap.read()
    cv2.imshow("Capture", frame)

    key = cv2.waitKey(1)

    if key == ord('s'):  # press S to save
        cv2.imwrite(f"{path}/{count}.jpg", frame)
        count += 1
        print("Saved:", count)

    elif key == 27:
        break

cap.release()
cv2.destroyAllWindows()