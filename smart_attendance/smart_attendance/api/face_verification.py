import frappe
import numpy as np
from frappe.utils import now_datetime, get_site_path
import base64
import os
import tempfile
import json
import io
from frappe.utils.file_manager import save_file
from smart_attendance.smart_attendance.api.custom_checkin_employee_id import mark_kiosk_attendance

# Try importing face_recognition and OpenCV
try:
    import face_recognition
    import face_recognition
    import cv2
    from PIL import Image, ImageOps 
except ImportError:
    face_recognition = None
    cv2 = None
    Image = None
    ImageOps = None


# ------------ Helper: Get Employee Image Paths ------------

def _get_all_employee_images():
    """
    Returns a list of tuples: (employee, absolute_file_path)
    Only considers employees who have a 'face_image' attached.
    """
    rows = frappe.get_all(
        "Employee Face",
        filters={"face_image": ["is", "set"]},
        fields=["employee", "face_image"]
    )
    
    data = []
    for r in rows:
        # face_image is like "/files/abc.jpg" or "/private/files/abc.jpg"
        relative_path = r.face_image
        
        full_path = None
        
        if relative_path.startswith("/private/files/"):
             filename = relative_path.replace("/private/files/", "")
             full_path = get_site_path("private", "files", filename)
             
        elif relative_path.startswith("/files/"):
             filename = relative_path.replace("/files/", "")
             full_path = get_site_path("public", "files", filename)
             
        if full_path and os.path.exists(full_path):
             data.append((r.employee, full_path))
    
    return data

# ------------ Helper: Save Base64 to Temp File ------------

def _save_base64_to_temp(image_base64: str):
    if not image_base64:
        return None
        
    if "," in image_base64:
        image_base64 = image_base64.split(",")[1]
        
    try:
        image_bytes = base64.b64decode(image_base64)
        
        # FIX: Handle EXIF Rotation (Mobile)
        if Image and ImageOps:
             img = Image.open(io.BytesIO(image_bytes))
             img = ImageOps.exif_transpose(img)
             
             # Overwrite image_bytes with corrected image
             buf = io.BytesIO()
             img.save(buf, format='JPEG')
             image_bytes = buf.getvalue()
             
    except Exception as e:
        frappe.log_error(f"Image Decode Error: {e}", "Kiosk Debug")
        return None
    
    # Create a temp file
    tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
    tfile.write(image_bytes)
    tfile.flush()
    tfile.close()
    return tfile.name

# ------------ ✅ LIVENESS CHECK HELPER ------------

def check_liveness(image_path, face_location=None):
    """
    Unified Liveness Check:
    1. Texture Analysis (Laplacian Variance)
    2. Frequency Analysis (FFT for Moiré patterns)
    """
    if cv2 is None:
        return True, "OpenCV not installed."

    try:
        # Load image
        image = cv2.imread(image_path)
        if image is None:
             return False, "Could not load image."
             
        # 🟢 ISOLATE FACE AREA
        if face_location:
            top, right, bottom, left = face_location
            h, w = image.shape[:2]
            # Use tight crop for frequency analysis
            image_face = image[top:bottom, left:right]
        else:
            image_face = image

        gray_face = cv2.cvtColor(image_face, cv2.COLOR_BGR2GRAY)
        
        # 1️⃣ TEXTURE ANALYSIS (Laplacian)
        texture_score = cv2.Laplacian(gray_face, cv2.CV_64F).var()
        
        # 2️⃣ FREQUENCY ANALYSIS (FFT for Screen Patterns)
        # Digital screens create "grid" or "interference" patterns in high frequencies.
        rows, cols = gray_face.shape
        crow, ccol = rows//2 , cols//2
        f = np.fft.fft2(gray_face)
        fshift = np.fft.fftshift(f)
        magnitude_spectrum = 20*np.log(np.abs(fshift) + 1e-9)
        
        # High-frequency content (away from center)
        # We check the corners of the spectrum for periodic peaks
        h_freq = (np.mean(magnitude_spectrum[0:10, 0:10]) + 
                  np.mean(magnitude_spectrum[-10:, -10:])) / 2
        
        l_freq = np.mean(magnitude_spectrum[crow-10:crow+10, ccol-10:ccol+10])
        
        # 🔍 Liveness Logic
        # Real Skin: High texture variation, organic noise (random), non-uniform detail.
        # Photo/Screen: Fixed pixel grid (sharp peaks), flat/uniform detail.

        # 3️⃣ ADAPTIVE SCALING
        # If the image is sharp (Real person usually > 50), we can be slightly relaxed.
        # If the image is blurry (Photo/Screen usually < 35), we must be extremely strict.
        is_low_detail = texture_score < 45
        
        # 4️⃣ ORGANIC REGIONAL VARIANCE
        h, w = gray_face.shape
        # Use more regions for better variance capturing
        r_h, r_w = h//3, w//3
        quads = [gray_face[i*r_h:(i+1)*r_h, j*r_w:(j+1)*r_w] for i in range(3) for j in range(3)]
        quad_textures = [cv2.Laplacian(q, cv2.CV_64F).var() for q in quads if q.size > 0]
        org_v = np.std(quad_textures) / (np.mean(quad_textures) + 1e-6) if quad_textures else 0
        
        # 5️⃣ SIGNAL SHARPNESS (Spectral Peakiness)
        # Real noise is spread out. Screens have precise peaks.
        h_ring = magnitude_spectrum[0:15, 0:15]
        h_std = np.std(h_ring)
        sharpness = h_std / (np.mean(h_ring) + 1e-6)
        
        rel_freq = (h_freq / l_freq) * 100 if l_freq > 0 else 0
        
        frappe.log_error(f"Liveness - T:{texture_score:.1f}, Org:{org_v:.2f}, Ratio:{rel_freq:.1f}, Sharp:{sharpness:.2f}", "Kiosk Debug")
        
        # REJECTION CRITERIA (ADAPTIVE BIOMETRIC)
        # 1. Base Texture Floor
        if texture_score < 11:
            return False, f"Anti-Spoofing: Natural texture too low ({texture_score:.1f})"
            
        # 2. Regional Variance (The "Flat" Check)
        # Real faces > 0.4. Photos/Screens < 0.3.
        # Strict if low detail.
        v_limit = 0.38 if is_low_detail else 0.32
        if org_v < v_limit:
             return False, f"Anti-Spoofing: Surface too uniform ({org_v:.2f})"

        # 3. Frequency Ratio Check 
        # Real phone hits ~42. Photos hit 39-45.
        # If low detail, the ratio MUST be lower (blocked if high ratio + low detail)
        r_limit = 35 if is_low_detail else 46
        if rel_freq > r_limit:
            return False, f"Anti-Spoofing: Secondary scan failed ({rel_freq:.1f})"
            
        # 4. Signal Sharpness (Digital Grid)
        if sharpness > 0.18:
             return False, f"Anti-Spoofing: Digital grid detected ({sharpness:.2f})"

        return True, f"Liveness Check Passed (T:{texture_score:.0f}, O:{org_v:.1f})"
        
    except Exception as e:
        frappe.log_error(f"Liveness Multi-Check Error: {e}")
        return True, "Check skipped due to error"


# ------------ ✅ IMAGE ATTACH HELPER ------------

def attach_image_to_fal(fal_name, image_base64):
    if "," in image_base64:
        image_base64 = image_base64.split(",")[1]

    image_bytes = base64.b64decode(image_base64)

    file_doc = save_file(
        "checkin.jpg",
        image_bytes,
        "Face Attendance Log",
        fal_name,
        is_private=0
    )

    frappe.db.set_value(
        "Face Attendance Log",
        fal_name,
        "image",
        file_doc.file_url
    )


# ------------ ✅ MAIN API ------------

@frappe.whitelist(allow_guest=True)
def mark_attendance_by_face(employee: str = None, image_base64: str = None, log_type: str = "AUTO", tolerance: float = 0.6):
    """
    Inputs:
        employee: Optional.
        image_base64: Required.
        log_type: "IN", "OUT", or "AUTO".
        tolerance: Matching threshold for dlib (default 0.55).
                   Lower is stricter. 0.6 is typical, 0.55 offers higher precision.
    """
    
    frappe.log_error("Mark Attendance By Face - START", "Kiosk Debug")
    
    if not face_recognition:
        frappe.log_error("Face Rec Lib Missing", "Kiosk Debug")
        return {"ok": False, "message": "Server Error: face_recognition library not installed."}

    if not image_base64:
        return {"ok": False, "message": "No image provided."}

    # 1️⃣ Save Input Image to Temp
    temp_img_path = _save_base64_to_temp(image_base64)
    if not temp_img_path:
        return {"ok": False, "message": "Invalid image data."}

    try:
        frappe.log_error("Starting Face Detection...", "Kiosk Debug")
        # 2️⃣ Face Detection & Encoding
        try:
            image = face_recognition.load_image_file(temp_img_path)
            # Find faces
            face_locations = face_recognition.face_locations(image)
            
            if not face_locations:
                 frappe.log_error("No face detected in submitted image", "Kiosk Debug")
                 return {"ok": False, "message": "No face detected in image."}
            
            # 🟢 1.5 ADVANCED LIVENESS CHECK
            is_live, live_msg = check_liveness(temp_img_path, face_locations[0])
            if not is_live:
                 # Cleanup
                 if os.path.exists(temp_img_path):
                     os.remove(temp_img_path)
                 return {
                     "ok": False, 
                     "message": live_msg,
                     "reason": "spoofing_detected"
                 }

            # Compute encodings
            # We take the first face found
            face_encodings = face_recognition.face_encodings(image, face_locations)
            
            if not face_encodings:
                return {"ok": False, "message": "Face features could not be extracted."}
                
            input_vector = face_encodings[0]
            
        except Exception as e:
            frappe.log_error(f"Face Recognition Extract Error: {e}")
            return {"ok": False, "message": "Face analysis failed. (Internal Error)"}
            

        detected_employee = employee
        match_distance = 1.0 
        
        # 3️⃣ Fetch Stored Encodings
        # We fetch (employee, encoding_json) from DB
        candidates = frappe.db.sql("""
            SELECT employee, encoding 
            FROM `tabEmployee Face` 
            WHERE encoding IS NOT NULL AND encoding != ''
        """, as_dict=True)
        
        if not candidates:
             return {"ok": False, "message": "No registered face data found."}

        best_match_emp = None
        best_match_dist = 100.0
        
        # 4️⃣ Compare against Candidates
        for cand in candidates:
            # If explicit employee requested, filter
            if employee and cand.employee != employee:
                continue
                
            try:
                db_vector = []
                # 1. Try JSON load
                try:
                    db_vector = json.loads(cand.encoding)
                except:
                    # 2. Try CSV split (backup)
                    if isinstance(cand.encoding, str):
                        db_vector = [float(x) for x in cand.encoding.split(',')]
                
                # Ensure it's a list/array
                if not db_vector:
                    continue

                # Compare using Euclidean Distance (face_distance)
                # face_distance returns a list, we compare one to one
                dist_arr = face_recognition.face_distance([np.array(db_vector)], input_vector)
                dist = dist_arr[0]
                
                if dist < best_match_dist:
                    best_match_dist = dist
                    best_match_emp = cand.employee
                    
                # Optimization: Break if very close match
                if dist < 0.35:
                    break
                    
            except Exception as e:
                # frappe.log_error("Face Match Error", str(e))
                continue

        # 5️⃣ Validate Match
        if best_match_dist <= float(tolerance):
            detected_employee = best_match_emp
            match_distance = float(best_match_dist)
        else:
             return {
                 "ok": False,
                 "reason": "face_not_matched",
                 "distance": best_match_dist,
                 "tolerance": float(tolerance),
                 "message": "Face not recognized."
             }

        # 6️⃣ MARK ATTENDANCE
        try:
            frappe.log_error(f"Face Matched: {detected_employee}, calling mark_kiosk_attendance", "Kiosk Debug")
            kiosk_result = mark_kiosk_attendance(detected_employee, log_type if log_type != "AUTO" else None)
        except Exception:
            err = frappe.get_traceback()
            frappe.log_error(err, "Kiosk Crash Trace")
            return {"ok": False, "message": "Server crashed during check-in creation. See Error Log 'Kiosk Crash Trace'."}
        
        if not kiosk_result.get("ok"):
            return kiosk_result
    
        final_log_type = kiosk_result.get("log_type")
    
    
        # 7️⃣ AUDIT LOG SAFE BLOCK
        log_name = ""
        try:
            frappe.log_error("Creating Audit Log...", "Kiosk Debug")
            
            # 60-Second Cooldown for Audit Log
            last_audit_time = frappe.db.get_value("Face Attendance Log", 
                {"employee": detected_employee}, 
                "time", 
                order_by="time desc"
            )
            if last_audit_time:
                from frappe.utils import get_datetime
                diff = (now_datetime() - get_datetime(last_audit_time)).total_seconds()
                if diff < 60:
                    frappe.log_error(f"Audit log skipped for {detected_employee} (Cooldown: {int(diff)}s)", "Kiosk Debug")
                    return {
                        "ok": True,
                        "log_name": "COOLDOWN_SKIPPED",
                        "employee": detected_employee,
                        "employee_name": frappe.db.get_value("Employee", detected_employee, "employee_name"),
                        "log_type": final_log_type,
                        "distance": match_distance,
                        "message": f"Welcome back {detected_employee}"
                    }

            log = frappe.new_doc("Face Attendance Log")
            log.employee = detected_employee
            log.time = now_datetime()
            log.log_type = final_log_type
            log.distance = match_distance
            log.details = f"Liveness: Pass, Dist: {match_distance:.4f}"
            log.insert(ignore_permissions=True)
            log_name = log.name
            
            # Attach Image
            try:
                attach_image_to_fal(log.name, image_base64)
            except Exception as e:
                frappe.log_error(f"Image Attach Failed: {str(e)}", "Kiosk Image Error")

            frappe.db.commit()
        except Exception as e:
            frappe.log_error(f"Audit Log Failed: {str(e)}", "Kiosk Logic Error")
            # Do NOT return error, attendance was marked successfully
    
        return {
            "ok": True,
            "log_name": log_name,
            "employee": detected_employee,
            "employee_name": frappe.db.get_value("Employee", detected_employee, "employee_name"),
            "log_type": final_log_type,
            "distance": match_distance,
            "message": f"Welcome {detected_employee} ({final_log_type})"
        }

    except Exception as e:
        frappe.log_error(f"Verification Error: {str(e)}")
        return {"ok": False, "message": f"System Error during verification."}
        
    finally:
        # Cleanup
        if os.path.exists(temp_img_path):
            try:
                os.remove(temp_img_path)
            except:
                pass
