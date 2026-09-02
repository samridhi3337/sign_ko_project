import cv2
import os

# Take text input
text = input("Enter text: ")

# Split into words
words = text.split()

for word in words:
    image_path = os.path.join("sign_images", word + ".jpg")

    if os.path.exists(image_path):
        img = cv2.imread(image_path)

        # Show sign image
        cv2.imshow("Text to Sign", img)

        # Wait for 2 seconds before next image
        cv2.waitKey(2000)

    else:
        print(word, "sign image not found")

cv2.destroyAllWindows()