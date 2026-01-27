import frappe
import numpy as np
from frappe.utils import now_datetime
from PIL import Image
import face_recognition
import base64
import io
from frappe.utils.file_manager import save_file
from smart_attendance.smart_attendance.api.custom_checkin_employee_id import mark_kiosk_attendance

# ------------ Helper: Employee ka saved encoding ------------

def _get_employee_encoding(employee: str):
    row = frappe.get_all(
        "Employee Face",
        filters={"employee": employee, "encoding": ["is", "set"]},
        fields=["encoding"],
        order_by="creation desc",
        limit=1,
    )

    if not row:
        frappe.throw("Employee ka enrolled face (encoding) nahi mila.")

    encoding_str = row[0]["encoding"]
    if not encoding_str:
        frappe.throw("Employee ke liye encoding empty hai.")

    try:
        vec = np.fromstring(encoding_str, sep=",", dtype=float)
    except Exception:
        frappe.throw("Saved encoding corrupt hai.")

    return vec

def _get_all_encodings():
    """Returns a list of tuples: (employee, encoding_vector)"""
    rows = frappe.get_all(
        "Employee Face",
        filters={"encoding": ["is", "set"]},
        fields=["employee", "encoding"]
    )
    
    data = []
    for r in rows:
        try:
            vec = np.fromstring(r.encoding, sep=",", dtype=float)
            data.append((r.employee, vec))
        except Exception:
            continue
    return data


# ------------ Helper: Camera se aayi base64 image se encoding ------------

def _encoding_from_base64(image_base64: str):
    if not image_base64:
        return None

    try:
        # Fix: Helper to handle potentially comma-separated base64 prefix
        if "," in image_base64:
            image_base64 = image_base64.split(",")[1]
            
        image_bytes = base64.b64decode(image_base64)
        pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    
        img_np = np.asarray(pil_image, dtype=np.uint8)
        img_np = np.ascontiguousarray(img_np)
    
        encodings = face_recognition.face_encodings(img_np)
        return encodings[0] if encodings else None
    except Exception as e:
        frappe.log_error(f"Face encoding error: {str(e)}")
        return None


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
def mark_attendance_by_face(employee: str = None, image_base64: str = None, log_type: str = "AUTO", tolerance: float = 0.5):
    """
    Inputs:
        employee: Optional. If provided, verifies against this employee. If None, searches all faces.
        image_base64: Required.
        log_type: "IN", "OUT", or "AUTO".
        tolerance: Matching threshold (lower is stricter).
    """

    # 1️⃣ Current image encoding
    current_vector = _encoding_from_base64(image_base64)

    if current_vector is None:
        return {
            "ok": False,
            "reason": "no_face",
            "message": "Image me face detect nahi hua.",
        }

    detected_employee = employee
    match_distance = 0.0

    # 2️⃣ Identify Employee
    if not detected_employee:
        # --- 1:N Search Mode ---
        candidates = _get_all_encodings()
        if not candidates:
             return {"ok": False, "message": "System me koi registered faces nahi hain."}
             
        known_encodings = [c[1] for c in candidates]
        known_ids = [c[0] for c in candidates]
        
        # vector calculation
        distances = face_recognition.face_distance(known_encodings, current_vector)
        
        # Find best match
        min_idx = np.argmin(distances)
        min_dist = distances[min_idx]
        
        if min_dist <= float(tolerance):
            detected_employee = known_ids[min_idx]
            match_distance = min_dist
        else:
            return {
                "ok": False,
                "reason": "face_not_matched",
                "distance": min_dist,
                "tolerance": float(tolerance),
                "message": "Face match nahi hua (User not found).",
            }
            
    else:
        # --- 1:1 Verification Mode (Legacy) ---
        saved_vector = _get_employee_encoding(detected_employee)
        match_distance = float(face_recognition.face_distance([saved_vector], current_vector)[0])
        
        if match_distance > float(tolerance):
            return {
                "ok": False,
                "reason": "face_not_matched",
                "distance": match_distance,
                "tolerance": float(tolerance),
                "message": "Face match nahi hua.",
            }

    # 3️⃣ Create Employee Checkin (Real Attendance)
    # Using the imported helper to handle IN/OUT logic and Checkin creation
    kiosk_result = mark_kiosk_attendance(detected_employee, log_type if log_type != "AUTO" else None)
    
    if not kiosk_result.get("ok"):
        return kiosk_result

    final_log_type = kiosk_result.get("log_type")

    # 4️⃣ Create Face Attendance Log (Audit Trail)
    log = frappe.new_doc("Face Attendance Log")
    log.employee = detected_employee
    log.time = now_datetime()
    log.log_type = final_log_type
    log.distance = match_distance
    log.insert(ignore_permissions=True)

    # ✅✅✅ 5️⃣ IMAGE ATTACH ✅✅✅
    if image_base64:
        attach_image_to_fal(log.name, image_base64)

    frappe.db.commit()

    return {
        "ok": True,
        "log_name": log.name,
        "employee": detected_employee,
        "employee_name": frappe.db.get_value("Employee", detected_employee, "employee_name"),
        "log_type": final_log_type,
        "distance": match_distance,
        "tolerance": float(tolerance),
        "message": f"Welcome {detected_employee}, marked {final_log_type}"
    }
