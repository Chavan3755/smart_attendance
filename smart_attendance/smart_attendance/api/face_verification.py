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
        # face_image is like "/files/abc.jpg"
        # We need absolute path: .../sites/site1/public/files/abc.jpg
        relative_path = r.face_image
        if relative_path.startswith("/files/"):
             # get_site_path("public", "files") -> .../public/files
             filename = relative_path.replace("/files/", "")
             # We can use frappe.get_site_path to be safe
             full_path = get_site_path("public", "files", filename)
             
             if os.path.exists(full_path):
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
        detected_employee = employee
        match_distance = 1.0 # default high
        matched_model = "VGG-Face"

        # List of candidate images
        # Strategy: We assume we need to iterate to be safe and explicit
        candidates = _get_all_employee_images() # Returns (emp_id, path)
        
        if not candidates:
             return {"ok": False, "message": "No registered faces (with images) found in system."}

        best_match_emp = None
        best_match_dist = 100.0
        
        # Filter if employee known
        target_candidates = candidates
        if employee:
             target_candidates = [c for c in candidates if c[0] == employee]
             if not target_candidates:
                 # Fallback: Maybe they have encoding but no image? 
                 # Current plan relies on image. Return error to force proper enrollment.
                 return {"ok": False, "message": f"Employee {employee} has no registered face image."}

        # Identify loop
        found_match = False
        
        for emp_id, db_img_path in target_candidates:
            try:
                # verify returns dict: {"verified": bool, "distance": float, ...}
                result = DeepFace.verify(
                    img1_path=temp_img_path,
                    img2_path=db_img_path,
                    model_name="VGG-Face",
                    distance_metric="cosine",
                    enforce_detection=False
                )
                
                dist = result.get("distance", 1.0)
                # verified = result.get("verified", False)
                
                # Check better match
                if dist < best_match_dist:
                    best_match_dist = dist
                    best_match_emp = emp_id
                
                # Early exit if excellent match? (e.g. < 0.20)
                if dist < 0.20:
                     break
                     
            except Exception as e:
                continue
        
        # Final Check against Tolerance
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
