from deepface import DeepFace
import numpy as np
import cv2

def test():
    # Create a dummy blank image
    img = np.zeros((300, 300, 3), dtype=np.uint8)
    
    print("Test 1: Blank image, enforce_detection=True, anti_spoofing=True")
    try:
        DeepFace.extract_faces(img, detector_backend='opencv', enforce_detection=True, anti_spoofing=True)
    except ValueError as e:
        print(f"Caught expected error: {e}")
    except Exception as e:
        print(f"Caught unexpected error: {e}")

    print("\nTest 2: Blank image, enforce_detection=False, anti_spoofing=True")
    try:
        results = DeepFace.extract_faces(img, detector_backend='opencv', enforce_detection=False, anti_spoofing=True)
        print(f"Results type: {type(results)}")
        if results:
            print(f"Result 0 keys: {results[0].keys()}")
            print(f"Result 0 confidence: {results[0].get('confidence')}")
            print(f"Result 0 is_real: {results[0].get('is_real')}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test()
