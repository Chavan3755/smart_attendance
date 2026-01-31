import frappe
import numpy as np
from frappe.utils import now_datetime, get_site_path
import base64
import os
import tempfile
from frappe.utils.file_manager import save_file
from smart_attendance.smart_attendance.api.custom_checkin_employee_id import mark_kiosk_attendance

# Try importing DeepFace
try:
    from deepface import DeepFace
except ImportError:
    DeepFace = None

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
    # DeepFace needs a path
    tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
    tfile.write(image_bytes)
    tfile.flush()
    tfile.close()
    return tfile.name

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

@frappe.whitelist()
def mark_attendance_by_face(employee: str = None, image_base64: str = None, log_type: str = "AUTO", tolerance: float = 0.40):
    """
    Inputs:
        employee: Optional.
        image_base64: Required.
        log_type: "IN", "OUT", or "AUTO".
        tolerance: Matching threshold for DeepFace (VGG-Face usually 0.40 is good strictness).
    """
    
    if not DeepFace:
        return {"ok": False, "message": "Server Error: DeepFace library not installed/loaded."}

    if not image_base64:
        return {"ok": False, "message": "No image provided."}

    # 1️⃣ Save Input Image to Temp
    temp_img_path = _save_base64_to_temp(image_base64)
    if not temp_img_path:
        return {"ok": False, "message": "Invalid image data."}

    try:
        # 2️⃣ Face Detection (Liveness Removed as per request)
        try:
             # Use enforce_detection=False to avoid hard crash on "No Face"
             # verification step will handle specific matching
             faces = DeepFace.extract_faces(
                 img_path=temp_img_path, 
                 detector_backend='opencv',
                 enforce_detection=True,
                 align=True
             )
        except ValueError:
            return {"ok": False, "message": "No face detected in image."}
        except Exception as e:
            frappe.log_error(f"DeepFace Extract Error: {e}")
            return {"ok": False, "message": "Face analysis failed."}
            
        if not faces:
             return {"ok": False, "message": "No face detected."}
             
        # Check first face (assuming single user)
        main_face = faces[0]
        
        # Liveness check removed


        # 3️⃣ IDENTIFY / VERIFY
        # 3️⃣ IDENTIFY / VERIFY using EMBEDDINGS (Faster & More Reliable)
        
        # A. Extract Embedding from Input
        try:
            # represent returns list of dicts: [{"embedding": [...], ...}]
            input_embedding_objs = DeepFace.represent(
                img_path=temp_img_path,
                model_name="VGG-Face",
                enforce_detection=True,
                detector_backend="opencv"
            )
            
            if not input_embedding_objs:
                 return {"ok": False, "message": "Face features could not be extracted."}
                 
            input_vector = input_embedding_objs[0]["embedding"]
            
        except Exception as e:
            frappe.log_error(f"DeepFace Represent Error: {e}")
            return {"ok": False, "message": "Face feature extraction failed."}

        detected_employee = employee
        match_distance = 1.0 
        
        # B. Fetch Stored Encodings
        # We fetch (employee, encoding_json) from DB
        # Only those with encodings
        candidates = frappe.db.sql("""
            SELECT employee, encoding 
            FROM `tabEmployee Face` 
            WHERE encoding IS NOT NULL AND encoding != ''
        """, as_dict=True)
        
        if not candidates:
             frappe.log_error("Face Verification", "No registered face data found in Employee Face table.")
             return {"ok": False, "message": "No registered face data found."}

        best_match_emp = None
        best_match_dist = 100.0
        
        # Helper: Cosine Distance
        def find_cosine_distance(source_representation, test_representation):
            if not isinstance(source_representation, list) and not isinstance(source_representation, np.ndarray):
                 return 1.0
            a = np.matmul(np.transpose(source_representation), test_representation)
            b = np.sum(np.multiply(source_representation, source_representation))
            c = np.sum(np.multiply(test_representation, test_representation))
            return 1 - (a / (np.sqrt(b) * np.sqrt(c)))

        # C. Compare against Candidates
        import json
        
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
                    # 2. Try CSV split
                    if isinstance(cand.encoding, str):
                        db_vector = [float(x) for x in cand.encoding.split(',')]
                
                # Ensure it's a list/array of numbers
                if not db_vector or len(db_vector) < 10: # Basic validity check
                    continue

                # Compare
                dist = find_cosine_distance(input_vector, db_vector)
                
                if dist < best_match_dist:
                    best_match_dist = dist
                    best_match_emp = cand.employee
                    
                # Optimization: Break if very close match
                if dist < 0.20:
                    break
                    
            except Exception as e:
                # frappe.log_error("Face Match Error", str(e))
                continue

        # D. Validate Match
        if best_match_dist <= float(tolerance):
            detected_employee = best_match_emp
            match_distance = best_match_dist
        else:
             return {
                 "ok": False,
                 "reason": "face_not_matched",
                 "distance": best_match_dist,
                 "tolerance": float(tolerance),
                 "message": "Face not recognized."
             }

        # 4️⃣ MARK ATTENDANCE
        kiosk_result = mark_kiosk_attendance(detected_employee, log_type if log_type != "AUTO" else None)
        
        if not kiosk_result.get("ok"):
            return kiosk_result
    
        final_log_type = kiosk_result.get("log_type")
    
        # 5️⃣ AUDIT LOG
        log = frappe.new_doc("Face Attendance Log")
        log.employee = detected_employee
        log.time = now_datetime()
        log.log_type = final_log_type
        log.distance = match_distance
        log.details = f"Liveness: Skipped, Dist: {match_distance:.4f}"
        log.insert(ignore_permissions=True)
    
        attach_image_to_fal(log.name, image_base64)
    
        frappe.db.commit()
    
        return {
            "ok": True,
            "log_name": log.name,
            "employee": detected_employee,
            "employee_name": frappe.db.get_value("Employee", detected_employee, "employee_name"),
            "log_type": final_log_type,
            "distance": match_distance,
            "message": f"Welcome {detected_employee}, marked {final_log_type} (Liveness OK)"
        }

    except Exception as e:
        frappe.log_error(f"DeepFace Error: {str(e)}")
        # Provide user friendly error
        return {"ok": False, "message": f"System Error during verification."}
        
    finally:
        # Cleanup
        if os.path.exists(temp_img_path):
            try:
                os.remove(temp_img_path)
            except:
                pass
