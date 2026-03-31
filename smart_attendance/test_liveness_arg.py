from deepface import DeepFace
import numpy as np

def execute():
    print("Testing DeepFace anti_spoofing arg...")
    img = np.zeros((200, 200, 3), dtype=np.uint8)
    try:
        # enforcement=False so it doesn't crash on blank image, but we want to see result structure if possible.
        # However, on blank imge it returns [] immediately. 
        # So we probably can't see keys without a real face.
        # But at least this confirms it doesn't crash on ArgumentError.
        objs = DeepFace.extract_faces(img, detector_backend='opencv', enforce_detection=False, anti_spoofing=True)
        print("Arg accepted!")
        if objs:
            print(f"Result keys: {objs[0].keys()}")
        else:
            print("No face detected (expected), but arg worked.")
    except Exception as e:
        print(f"Error: {e}")
