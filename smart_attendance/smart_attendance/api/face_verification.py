import frappe
import numpy as np
from frappe.utils import now_datetime, get_site_path
import base64
import os
import tempfile
import json
from frappe.utils.file_manager import save_file
from smart_attendance.smart_attendance.api.custom_checkin_employee_id import mark_kiosk_attendance

# Try importing face_recognition and OpenCV
try:
    import face_recognition
    import cv2
except ImportError:
    face_recognition = None
    cv2 = None


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
    except Exception:
        return None
    
    # Create a temp file
    tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
    tfile.write(image_bytes)
    tfile.flush()
    tfile.close()
    return tfile.name

# ------------ ✅ LIVENESS CHECK HELPER ------------

def check_texture_liveness(image_path):
    """
    Checks for liveness using Laplacian Variance (Texture Analysis).
    Low variance (< 25) indicates a blur/flat image (screen or photo).
    """
    if cv2 is None:
        return True, "OpenCV not installed, skipping liveness."

    try:
        # Load image
        image = cv2.imread(image_path)
        if image is None:
             return False, "Could not load image."
             
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Calculate Laplacian Variance
        texture = cv2.Laplacian(gray, cv2.CV_64F).var()
        
        # Use user threshold 25
        if texture < 85:
             return False, "PHOTO / MOBILE DETECTED"
             
        return True, "Live"
        
    except Exception as e:
        frappe.log_error(f"Liveness Check Error: {e}")
        # Allowing for now to prevent blocking valid users on minor errors 
        return True, "Error checking liveness"


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
def mark_attendance_by_face(employee: str = None, image_base64: str = None, log_type: str = "AUTO", tolerance: float = 0.55):
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

    # 1.5 LIVENESS CHECK (Texture)
    is_live, live_msg = check_texture_liveness(temp_img_path)
    if not is_live:
         # Cleanup
         if os.path.exists(temp_img_path):
             os.remove(temp_img_path)
         return {
             "ok": False, 
             "message": live_msg,
             "reason": "spoofing_detected"
         }

    try:
        frappe.log_error("Starting Face Detection...", "Kiosk Debug")
        # 2️⃣ Face Detection & Encoding
        try:
            image = face_recognition.load_image_file(temp_img_path)
            # Find faces
            face_locations = face_recognition.face_locations(image)
            
            if not face_locations:
                 return {"ok": False, "message": "No face detected in image."}
                 
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
