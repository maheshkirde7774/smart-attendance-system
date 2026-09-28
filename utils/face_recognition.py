import os
import re
import io
import base64
import pickle
import numpy as np
from PIL import Image, ImageOps

FACE_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'face_data')
MODEL_PATH = os.path.join(FACE_DATA_DIR, 'face_model.pkl')
os.makedirs(FACE_DATA_DIR, exist_ok=True)

# Lazy cascade loader
_face_cascade = None

def get_face_cascade():
    global _face_cascade
    if _face_cascade is None:
        try:
            import cv2
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            _face_cascade = cv2.CascadeClassifier(cascade_path)
        except Exception as e:
            _face_cascade = None
    return _face_cascade

def decode_image_from_base64(b64_string):
    """Decodes a base64 string into a RGB/BGR numpy array image."""
    try:
        if ',' in b64_string:
            b64_string = b64_string.split(',')[1]
        img_bytes = base64.b64decode(b64_string)

        try:
            import cv2
            nparr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is not None:
                return img
        except Exception:
            pass

        # Fallback to Pillow
        pil_img = Image.open(io.BytesIO(img_bytes)).convert('RGB')
        return np.array(pil_img)
    except Exception as e:
        print(f"Failed to decode base64 image: {e}")
        return None

def extract_face_crop(img, target_size=(112, 112)):
    """
    Detects the primary face in the image and returns a normalized grayscale face crop.
    Uses OpenCV Haar Cascade if available, with intelligent central ROI detection fallback.
    Returns: (crop, (x, y, w, h)) or (None, None)
    """
    if img is None:
        return None, None

    try:
        # Check OpenCV Cascade first
        cascade = get_face_cascade()
        if cascade is not None:
            import cv2
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img

            faces = cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=4,
                minSize=(50, 50),
                flags=cv2.CASCADE_SCALE_IMAGE
            )

            if len(faces) > 0:
                faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
                (x, y, w, h) = faces[0]

                pad = int(0.1 * w)
                h_img, w_img = gray.shape
                x1 = max(0, x - pad)
                y1 = max(0, y - pad)
                x2 = min(w_img, x + w + pad)
                y2 = min(h_img, y + h + pad)

                face_roi = gray[y1:y2, x1:x2]
                face_resized = cv2.resize(face_roi, target_size, interpolation=cv2.INTER_AREA)
                face_eq = cv2.equalizeHist(face_resized)
                return face_eq, (int(x), int(y), int(w), int(h))

        # Pillow Fallback
        pil_img = Image.fromarray(img).convert('L')
        w_img, h_img = pil_img.size

        # Central 50% region as the face focus zone
        w = int(w_img * 0.5)
        h = int(h_img * 0.5)
        x = int(w_img * 0.25)
        y = int(h_img * 0.25)

        crop = pil_img.crop((x, y, x + w, y + h))
        crop = crop.resize(target_size, Image.Resampling.LANCZOS)
        crop_eq = ImageOps.equalize(crop)

        return np.array(crop_eq), (int(x), int(y), int(w), int(h))
    except Exception as e:
        print(f"Error in extract_face_crop: {e}")
        return None, None

def save_face_samples(student_id, b64_images):
    """
    Saves face samples for a student and triggers model retraining.
    b64_images: list of base64 image strings.
    """
    student_dir = os.path.join(FACE_DATA_DIR, student_id)
    os.makedirs(student_dir, exist_ok=True)

    saved_count = 0
    for idx, b64_data in enumerate(b64_images):
        img = decode_image_from_base64(b64_data)
        if img is None:
            continue
        face_crop, _ = extract_face_crop(img)
        if face_crop is not None:
            filepath = os.path.join(student_dir, f"sample_{idx}.jpg")
            pil_crop = Image.fromarray(face_crop)
            pil_crop.save(filepath, 'JPEG')
            saved_count += 1

    if saved_count > 0:
        train_model()
        return True, f"Successfully registered {saved_count} face sample(s) for {student_id}"
    return False, "No valid faces were detected in the captured images. Please look directly at the camera."

def train_model():
    """
    Scans FACE_DATA_DIR, extracts features for all registered students,
    trains a nearest-centroid / cosine distance face embedding model,
    and saves to MODEL_PATH.
    """
    try:
        student_ids = []
        features_list = []

        for item in os.listdir(FACE_DATA_DIR):
            student_dir = os.path.join(FACE_DATA_DIR, item)
            if os.path.isdir(student_dir):
                s_id = item
                for fname in os.listdir(student_dir):
                    if fname.lower().endswith(('.jpg', '.jpeg', '.png')):
                        fpath = os.path.join(student_dir, fname)
                        try:
                            pil_im = Image.open(fpath).convert('L').resize((112, 112))
                            arr = np.array(pil_im, dtype=np.float32)
                            feat = arr.flatten()
                            norm = np.linalg.norm(feat)
                            if norm > 0:
                                feat = feat / norm
                            features_list.append(feat)
                            student_ids.append(s_id)
                        except Exception as err:
                            print(f"Error reading {fpath}: {err}")

        if len(features_list) == 0:
            if os.path.exists(MODEL_PATH):
                os.remove(MODEL_PATH)
            return False, "No training data available."

        X = np.array(features_list)
        y = np.array(student_ids)

        model_data = {
            "X": X,
            "y": y,
            "students": list(set(student_ids))
        }

        with open(MODEL_PATH, 'wb') as f:
            pickle.dump(model_data, f)

        print(f"Face model trained successfully with {len(X)} samples across {len(set(student_ids))} students.")
        return True, "Model trained successfully"
    except Exception as e:
        print(f"Model training failed: {e}")
        return False, str(e)

def recognize_face(img_or_b64, similarity_threshold=0.62):
    """
    Recognizes a student face from an image.
    Strictly rejects unrecognized faces as Unknown.
    """
    try:
        if isinstance(img_or_b64, str):
            img = decode_image_from_base64(img_or_b64)
        else:
            img = img_or_b64

        if img is None:
            return {"status": "no_face", "match": False, "student_id": None, "confidence": 0, "box": None, "message": "Invalid image frame"}

        face_crop, box = extract_face_crop(img)
        if face_crop is None:
            return {"status": "no_face", "match": False, "student_id": None, "confidence": 0, "box": None, "message": "No face detected in camera"}

        if not os.path.exists(MODEL_PATH):
            return {"status": "no_model", "match": False, "student_id": None, "confidence": 0, "box": list(box), "message": "No registered face database found"}

        with open(MODEL_PATH, 'rb') as f:
            model_data = pickle.load(f)

        X_train = model_data["X"]
        y_train = model_data["y"]

        feat = face_crop.flatten().astype(np.float32)
        norm = np.linalg.norm(feat)
        if norm > 0:
            feat = feat / norm

        # Compute cosine similarities
        similarities = np.dot(X_train, feat)
        best_idx = np.argmax(similarities)
        best_sim = float(similarities[best_idx])
        predicted_id = y_train[best_idx]

        confidence_pct = round(best_sim * 100, 1)

        # STRICT UNKNOWN CHECK:
        # If best similarity is below threshold, reject as unknown!
        if best_sim < similarity_threshold:
            return {
                "status": "unknown",
                "match": False,
                "student_id": None,
                "confidence": confidence_pct,
                "box": list(box),
                "message": f"Face detected but unrecognized (Confidence: {confidence_pct}%)"
            }

        return {
            "status": "success",
            "match": True,
            "student_id": predicted_id,
            "confidence": confidence_pct,
            "box": list(box),
            "message": f"Recognized {predicted_id} ({confidence_pct}% match)"
        }
    except Exception as e:
        print(f"Error during face recognition: {e}")
        return {
            "status": "error",
            "match": False,
            "student_id": None,
            "confidence": 0,
            "box": None,
            "message": str(e)
        }
