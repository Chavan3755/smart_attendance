import frappe
import numpy as np
from frappe.utils import now_datetime
from PIL import Image
import face_recognition
import base64
import io
from frappe.utils.file_manager import save_file


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


# ------------ Helper: Camera se aayi base64 image se encoding ------------

def _encoding_from_base64(image_base64: str):
    if not image_base64:
        return None

    image_bytes = base64.b64decode(image_base64)
    pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    img_np = np.asarray(pil_image, dtype=np.uint8)
    img_np = np.ascontiguousarray(img_np)

    encodings = face_recognition.face_encodings(img_np)
    return encodings[0] if encodings else None


# ------------ ✅ IMAGE ATTACH HELPER ------------

def attach_image_to_fal(fal_name, image_base64):
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
def mark_attendance_by_face(employee: str, image_base64: str, log_type: str = "AUTO", tolerance: float = 0.6):

    # 1️⃣ Employee encoding
    saved_vector = _get_employee_encoding(employee)

    # 2️⃣ Current image encoding
    current_vector = _encoding_from_base64(image_base64)

    if current_vector is None:
        return {
            "ok": False,
            "reason": "no_face",
            "message": "Image me face detect nahi hua.",
        }

    # 3️⃣ Face compare
    distance = float(face_recognition.face_distance([saved_vector], current_vector)[0])
    is_match = distance <= float(tolerance)

    if not is_match:
        return {
            "ok": False,
            "reason": "face_not_matched",
            "distance": distance,
            "tolerance": float(tolerance),
        }

    # 4️⃣ AUTO IN/OUT toggle
    if log_type == "AUTO":
        last = frappe.get_all(
            "Face Attendance Log",
            filters={"employee": employee},
            fields=["log_type", "time"],
            order_by="time desc",
            limit=1,
        )

        log_type_final = "OUT" if last and last[0].get("log_type") == "IN" else "IN"
    else:
        log_type_final = log_type

    # 5️⃣ Create Face Attendance Log
    log = frappe.new_doc("Face Attendance Log")
    log.employee = employee
    log.time = now_datetime()
    log.log_type = log_type_final
    log.distance = distance
    log.insert(ignore_permissions=True)

    # ✅✅✅ 6️⃣ IMAGE ATTACH ✅✅✅
    attach_image_to_fal(log.name, image_base64)

    frappe.db.commit()

    return {
        "ok": True,
        "log_name": log.name,
        "employee": employee,
        "log_type": log_type_final,
        "distance": distance,
        "tolerance": float(tolerance),
    }
