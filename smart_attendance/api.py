# smart_attendance/smart_attendance/api.py
import frappe
import base64, io, json
from datetime import datetime, date, timedelta

@frappe.whitelist(allow_guest=True)
def fetch_next_15_days_holidays(employee=None):
    """
    Returns holidays for the next 15 days.
    """
    try:
        if employee:
            holiday_list = frappe.db.get_value("Employee", employee, "holiday_list")
        else:
            holiday_list = frappe.db.get_single_value("Attendance Manager Settings", "default_holiday_list")

        if not holiday_list:
            # Fallback to any holiday list
            holiday_list = frappe.db.get_value("Holiday List", {"is_default": 1}, "name")

        if not holiday_list:
             return {"holidays": []}

        start_date = date.today()
        end_date = start_date + timedelta(days=15)

        holidays = frappe.get_all("Holiday",
            filters={
                "parent": holiday_list,
                "holiday_date": ["between", [start_date, end_date]]
            },
            fields=["holiday_date", "description"],
            order_by="holiday_date asc"
        )
        
        # Format for frontend
        formatted = []
        for h in holidays:
            formatted.append({
                "date": frappe.utils.formatdate(h.holiday_date),
                "name": h.description
            })

        return {"holidays": formatted}
    except Exception as e:
        frappe.log_error(f"Error checking holidays: {str(e)}")
        return {"holidays": []}



@frappe.whitelist()
def enroll_face(employee, image_base64):
    """Enroll a face for an employee. Only allowed for logged-in Attendance Manager."""
    if 'Attendance Manager' not in frappe.get_roles():
        frappe.throw("Permission denied")
    # decode image
    header, b64 = image_base64.split(',',1) if ',' in image_base64 else (None, image_base64)
    imgdata = base64.b64decode(b64)
    # compute encoding using face_recognition (deferred to helper)
    encoding = _compute_encoding(imgdata)
    if not encoding:
        frappe.throw("No face detected")
    doc = frappe.get_doc({
        "doctype":"Employee Face",
        "employee": employee,
        "face_encoding": json.dumps(encoding),
        "enrolled_by": frappe.session.user,
        "enrolled_on": frappe.utils.now_datetime()
    }).insert(ignore_permissions=True)
    # attach image
    frappe.get_doc({
        "doctype":"File",
        "file_name": f"{employee}_enroll.jpg",
        "attached_to_doctype": doc.doctype,
        "attached_to_name": doc.name,
        "content": base64.b64encode(imgdata).decode('utf-8')
    }).insert(ignore_permissions=True)
    frappe.db.commit()
    return {"status":"ok", "doc": doc.name}

@frappe.whitelist(allow_guest=True)
def verify_face(device_id=None, device_secret=None, image_base64=None, confidence_threshold=0.6):
    """Kiosk calls this endpoint (POST)."""
    # authenticate device
    if not device_id or not device_secret:
        frappe.throw("Device credentials required")
    try:
        dev = frappe.get_doc("Attendance Device", device_id)
    except frappe.DoesNotExistError:
        frappe.throw("Invalid device id")
    if not dev.is_active or dev.secret_key != device_secret:
        frappe.throw("Invalid device credentials")
    # decode image
    header, b64 = image_base64.split(',',1) if ',' in image_base64 else (None, image_base64)
    imgdata = base64.b64decode(b64)
    unknown_encoding = _compute_encoding(imgdata)
    if not unknown_encoding:
        # no face detected — save unmatched record
        att = frappe.get_doc({
            "doctype":"Face Attendance",
            "employee": None,
            "device": device_id,
            "attendance_time": frappe.utils.now_datetime(),
            "confidence": 0,
            "status": "Unmatched"
        }).insert(ignore_permissions=True)
        _attach_file(att, imgdata)
        frappe.db.commit()
        return {"status":"unmatched", "reason":"no_face_detected"}

    # load all encodings (cache recommended)
    faces = frappe.get_all("Employee Face", fields=["name","employee","face_encoding"])
    import face_recognition
    best = None
    best_dist = 1.0
    for f in faces:
        known = json.loads(f.face_encoding)
        dist = face_recognition.face_distance([known], unknown_encoding)[0]
        if dist < best_dist:
            best_dist = dist
            best = f
    confidence = float(1.0 - best_dist) if best else 0.0
    if best and confidence >= float(confidence_threshold):
        att = frappe.get_doc({
            "doctype":"Face Attendance",
            "employee": best.employee,
            "device": device_id,
            "attendance_time": frappe.utils.now_datetime(),
            "confidence": confidence,
            "status": "Present",
            "match_type": "Auto"
        }).insert(ignore_permissions=True)
        _attach_file(att, imgdata)
        frappe.db.commit()
        # update device last_seen
        frappe.db.set_value("Attendance Device", device_id, "last_seen", frappe.utils.now_datetime())

        # --- STANDARD HR CHECKIN ---
        try:
            frappe.get_doc({
                "doctype": "Employee Checkin",
                "employee": best.employee,
                "log_type": "IN", # Default to IN, or logic could be improved to toggle
                "time": frappe.utils.now_datetime(),
                "device_id": device_id
            }).insert(ignore_permissions=True)
        except Exception as e:
            frappe.log_error(f"Failed to create Employee Checkin: {str(e)}")
        # ---------------------------

        return {"status":"success", "employee": best.employee, "confidence": confidence}
    else:
        # unmatched / low-confidence
        status = "Low Confidence" if best else "Unmatched"
        att = frappe.get_doc({
            "doctype":"Face Attendance",
            "employee": best.employee if best else None,
            "device": device_id,
            "attendance_time": frappe.utils.now_datetime(),
            "confidence": confidence,
            "status": status,
            "match_type": "Auto"
        }).insert(ignore_permissions=True)
        _attach_file(att, imgdata)
        frappe.db.commit()
        return {"status":"unmatched", "confidence": confidence}
 
# Helpers:
def _compute_encoding(imgbytes):
    """Return face encoding list or None. Requires face_recognition installed."""
    try:
        import face_recognition
        from PIL import Image
        import numpy as np
        img = Image.open(io.BytesIO(imgbytes)).convert('RGB')
        arr = np.array(img)
        encs = face_recognition.face_encodings(arr)
        return encs[0].tolist() if encs else None
    except Exception as e:
        frappe.log_error(message=str(e), title="Face encoding error")
        return None

def _attach_file(doc, imgbytes):
    import base64
    frappe.get_doc({
        "doctype":"File",
        "file_name": f"{doc.name}.jpg",
        "attached_to_doctype": doc.doctype,
        "attached_to_name": doc.name,
        "content": base64.b64encode(imgbytes).decode('utf-8')
    }).insert(ignore_permissions=True)
