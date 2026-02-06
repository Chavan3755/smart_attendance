# smart_attendance/smart_attendance/api.py
import frappe
import base64, io, json
from datetime import datetime, date, timedelta

@frappe.whitelist(allow_guest=True)
def fetch_next_15_days_holidays(employee=None):
    """
    Returns holidays for the next 15 days.
    """
    # uyfyfsdyufsdyusdafuysdafdyusaf
    try:
        if employee:
            holiday_list = frappe.db.get_value("Employee", employee, "holiday_list")
        else:
            # Safely check for settings
            if frappe.db.exists("DocType", "Attendance Manager Settings"):
                holiday_list = frappe.db.get_single_value("Attendance Manager Settings", "default_holiday_list")
            else:
                holiday_list = None

            # 1. Fallback to Shift Assignment
            if employee:
                # Find active shift assignment for today
                shift_assignment = frappe.db.get_value("Shift Assignment", {
                    "employee": employee,
                    "status": "Active",
                    "start_date": ["<=", start_date],
                    # end_date can be None (ongoing) or >= today
                    # Complex queries might need get_all, but let's try a simpler approach first or use SQL if needed for OR
                    # For simplicity in get_value, we might miss the OR condition for end_date.
                    # Let's use get_all to be safe about the end_date logic (None OR >= today).
                }, "shift_type")
                
                # If get_value didn't work directly due to complex end_date, let's try a better query if needed. 
                # Actually, let's use a robust query for shift assignment.
                if not shift_assignment:
                     # Check if there is any assignment valid for today
                     sas = frappe.get_all("Shift Assignment",
                        filters=[
                            ["employee", "=", employee],
                            ["status", "=", "Active"],
                            ["start_date", "<=", start_date],
                            ["end_date", "in", [None, ""]], # Open ended
                        ],
                        fields=["shift_type"],
                        limit=1
                     )
                     if not sas:
                         sas = frappe.get_all("Shift Assignment",
                            filters=[
                                ["employee", "=", employee],
                                ["status", "=", "Active"],
                                ["start_date", "<=", start_date],
                                ["end_date", ">=", start_date],
                            ],
                            fields=["shift_type"],
                            limit=1
                         )
                     
                     if sas:
                         shift_assignment = sas[0].shift_type

                if shift_assignment:
                    holiday_list = frappe.db.get_value("Shift Type", shift_assignment, "holiday_list")

            # 2. Fallback to Company default
            if not holiday_list:
                company = None
                if employee:
                    company = frappe.db.get_value("Employee", employee, "company")
                if not company:
                    company = frappe.defaults.get_user_default("Company")
                
                if company:
                    holiday_list = frappe.db.get_value("Company", company, "default_holiday_list")

            # 3. Gloabl Settings
            if not holiday_list:
                 if frappe.db.exists("DocType", "Attendance Manager Settings"):
                     holiday_list = frappe.db.get_single_value("Attendance Manager Settings", "default_holiday_list")
            
            # 4. Last resort: ANY holiday list (optional, but maybe better to show nothing than wrong info)
            # if not holiday_list:
            #    pass

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
        "encoding": json.dumps(encoding),
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
def verify_face(device_id=None, device_secret=None, image_base64=None, confidence_threshold=0.6, employee=None, log_type="AUTO"):
    """Kiosk calls this endpoint (POST)."""
    
    frappe.log_error(f"Verify Face Called: Device={device_id}, Emp={employee}, HasImage={bool(image_base64)}", "Kiosk Debug")
    
    # SCREAM TEST (Temporary Debug)
    # frappe.throw(f"DEBUG: dev={device_id} img={bool(image_base64)}")

    # 0. WEB KIOSK DELEGATION
    if (not device_id or device_id == "null"):
         if not image_base64:
             return {"ok": False, "message": "No image provided for Kiosk verification"}

         try:
             # Debug Step 1
             frappe.log_error("Delegation Step 1: Importing face_verification", "Kiosk Debug")
             frappe.db.commit() # FORCE COMMIT
             
             # Lazy import for safety
             from smart_attendance.smart_attendance.api.face_verification import mark_attendance_by_face
             
             # Debug Step 2
             frappe.log_error("Delegation Step 2: Import success. Calling function.", "Kiosk Debug")
             frappe.db.commit() # FORCE COMMIT
             
             return mark_attendance_by_face(employee, image_base64, log_type, confidence_threshold)
         except ImportError as e:
             frappe.log_error(f"Import Error in Delegation: {str(e)}", "Kiosk Debug")
             frappe.db.commit()
             return {"ok": False, "message": f"Server Import Error: {str(e)}"}
         except Exception as e:
             frappe.log_error(f"Delegation Error: {str(e)}", "Kiosk Debug")
             frappe.db.commit()
             return {"ok": False, "message": f"Server Error: {str(e)}"}

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
    faces = frappe.get_all("Employee Face", fields=["name","employee","encoding"])
    import face_recognition
    best = None
    best_dist = 1.0
    for f in faces:
        if not f.encoding:
            continue
            
        try:
            known = json.loads(f.encoding)
            dist = face_recognition.face_distance([known], unknown_encoding)[0]
            if dist < best_dist:
                best_dist = dist
                best = f
        except Exception as e:
            frappe.log_error(f"Error processing face encoding for {f.name}: {str(e)}")
            continue
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
            
            return {"status":"success", "ok": True, "employee": best.employee, "employee_name": best.employee, "confidence": confidence, "log_type": "IN"}
        except Exception as e:
            frappe.log_error(f"Failed to create Employee Checkin: {str(e)}")
            return {"status":"success", "ok": False, "message": f"Face matched but Check-in failed: {str(e)}", "employee": best.employee, "confidence": confidence}
        # ---------------------------
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
