
import sys
import os
import numpy as np

print("1. Importing modules...")
try:
    import face_recognition
    import cv2
    print("Modules imported.")
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

print("2. Creating dummy image...")
# Create a black image
img = np.zeros((100, 100, 3), dtype=np.uint8)
# Save to temp
import tempfile
tfile = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
import cv2
cv2.imwrite(tfile.name, img)
print(f"Image saved to {tfile.name}")

print("3. Testing cv2 load...")
try:
    loaded = cv2.imread(tfile.name)
    print("cv2 load success.")
except Exception as e:
    print(f"cv2 crash: {e}")

print("4. Testing face_recognition load...")
try:
    fr_img = face_recognition.load_image_file(tfile.name)
    print("fr load success.")
except Exception as e:
    print(f"fr load crash: {e}")

print("5. Testing face detection (HOG)...")
try:
    locs = face_recognition.face_locations(fr_img)
    print(f"Face locations: {locs}")
except Exception as e:
    print(f"HOG crash: {e}")

print("SUCCESS: No SegFault.")
os.remove(tfile.name)
