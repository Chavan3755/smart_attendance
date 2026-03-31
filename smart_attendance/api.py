import frappe
from frappe.utils import nowdate, now_datetime, get_datetime, formatdate
import base64, io, json
from datetime import datetime, date, timedelta

@frappe.whitelist(allow_guest=True)
def get_csrf_token():
    return {"csrf_token": frappe.local.session.data.csrf_token}

@frappe.whitelist(allow_guest=True)
def get_today_logs(employee):
  
    if not employee:
        return []

    # Safe strip
    emp_id = employee.strip() if employee else ""

    try:
        # Fetch last 50 logs regardless of date to ensure we catch recent punches
        # even if there's a timezone skew or date mismatch.
        logs = frappe.db.sql("""
            SELECT
                name,
                log_type,
                time,
                employee_name
            FROM `tabEmployee Checkin`
            WHERE TRIM(employee) = %s
            ORDER BY time DESC
            LIMIT 50
        """, (emp_id,), as_dict=True)

        today_str = frappe.utils.nowdate()

        # Mark logs as today dynamically
        for l in logs:
            if l.time:
                # Convert to string date YYYY-MM-DD
                log_date = str(l.time).split(" ")[0]
                l["is_today"] = (log_date == today_str)
            else:
                l["is_today"] = False

        return logs

    except Exception as e:
        pass
        return []


@frappe.whitelist(allow_guest=True)
def get_last_log_type(employee):
    """Returns the last log type (IN/OUT) for an employee."""
    if not employee: return "OUT"
    emp_id = employee.strip()
    
    try:
        last_type = frappe.db.get_value("Employee Checkin", 
            {"employee": emp_id}, "log_type", 
            order_by="time desc", ignore_permissions=True)
            
        if not last_type:
            emp_name = frappe.db.get_value("Employee", emp_id, "employee_name", ignore_permissions=True)
            last_type = frappe.db.get_value("Employee Checkin", 
                {"employee_name": emp_name}, "log_type", 
                order_by="time desc", ignore_permissions=True)
                
        return last_type or "OUT"
    except Exception:
        return "OUT"

@frappe.whitelist(allow_guest=True)
def fetch_next_15_days_holidays(employee=None):
    """
    Returns holidays for the next 15 days.
    """
    # uyfyfsdyufsdyusdafuysdafdyusaf
    try:
        if employee:
            holiday_list = frappe.db.get_value("Employee", employee, "holiday_list", ignore_permissions=True)
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
            order_by="holiday_date asc",
            ignore_permissions=True
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
        pass
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
def verify_face(**kwargs):
    """Kiosk calls this endpoint (POST). Uses kwargs to avoid 400 Bad Request on arg mismatch."""
    try:

        
        # Extract args safely
        device_id = kwargs.get("device_id")
        device_secret = kwargs.get("device_secret")
        image_base64 = kwargs.get("image_base64")
        confidence_threshold = kwargs.get("confidence_threshold", 0.6)
        employee = kwargs.get("employee")
        log_type = kwargs.get("log_type", "IN")
        verify_only = kwargs.get("verify_only")
        if isinstance(verify_only, str):
            verify_only = (verify_only.lower() == "true")

        # Sanitize log_type - Default to IN, treat AUTO as IN explicit mode
        if not log_type or str(log_type).lower() in ["null", "undefined", "none", "", "auto"]:
            log_type = "IN"
        
        # Sanitize confidence
        try:
             confidence_threshold = float(confidence_threshold)
        except:
             confidence_threshold = 0.6
        
        # 0. WEB KIOSK DELEGATION
        # Handle various "null" string representations from frontend
        if (not device_id or str(device_id).lower() in ["null", "undefined", "none", ""]):
             if not image_base64:
                 return {"ok": False, "message": "No image provided for Kiosk verification"}

             try:
                 # Lazy import for safety
                 from smart_attendance.smart_attendance.api.face_verification import mark_attendance_by_face
                 
                 return mark_attendance_by_face(employee, image_base64, log_type, confidence_threshold, verify_only=verify_only)
             except Exception as e:
                 pass
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
                pass
                continue
        confidence = float(1.0 - best_dist) if best else 0.0
        
        # Use 0.5 threshold for better user experience
        if best and confidence >= 0.5:
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
                # Determine Log Type: If AUTO, infer from last log, else use explicit type (IN/OUT)
                final_log_type = log_type
                if log_type == "AUTO":
                    last_type = get_last_log_type(best.employee)
                    final_log_type = "OUT" if last_type == "IN" else "IN"

                if not verify_only:
                    frappe.get_doc({
                        "doctype": "Employee Checkin",
                        "employee": best.employee,
                        "log_type": final_log_type, 
                        "time": frappe.utils.now_datetime(),
                        "device_id": device_id
                    }).insert(ignore_permissions=True)
                
                # Fetch name for display
                emp_name = frappe.db.get_value("Employee", best.employee, "employee_name") or best.employee
                
                return {
                    "status": "success", 
                    "ok": True, 
                    "employee": best.employee, 
                    "employee_name": emp_name, 
                    "confidence": confidence, 
                    "log_type": final_log_type
                }
            except Exception as e:
                pass
                return {"status":"success", "ok": False, "message": f"Face matched but Check-in failed: {str(e)}", "employee": best.employee, "confidence": confidence}
            # ---------------------------
        else:
            # unmatched / low-confidence
            status = "Low Confidence" if best else "Unmatched"
            
            # LOGGING FOR DEBUGGING
            dist_msg = f"Best: {1.0-confidence:.2f} (Conf: {confidence:.2f})" if best else "No match"
            pass
            
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

    except Exception as e:
        pass
        return {"ok": False, "message": f"System Error: {str(e)}"}
 
# Helpers:
# Helpers:
def _compute_encoding(imgbytes):
    """Return face encoding list or None. Requires face_recognition installed."""
    try:
        import face_recognition
        from PIL import Image, ImageOps 
        import numpy as np
        
        # Open image from bytes
        img = Image.open(io.BytesIO(imgbytes))
        
        # Handle EXIF rotation (Mobile camera fix)
        img = ImageOps.exif_transpose(img)
        
        # Convert to RGB
        img = img.convert('RGB')
        
        arr = np.array(img)
        encs = face_recognition.face_encodings(arr)
        
        # Log if no face found during enrollment/verification internal check
        if not encs:
            pass
            
        return encs[0].tolist() if encs else None
    except Exception as e:
        pass
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

@frappe.whitelist(allow_guest=True)
def get_recent_attendance(employee):
    """
    Returns the last 5 attendance records from the 'Attendance' DocType.
    """
    if not employee:
        return []
    
    try:
        attendance_list = frappe.get_all("Attendance",
            filters={"employee": employee, "docstatus": 1},
            fields=["attendance_date", "status", "working_hours", "in_time", "out_time"],
            order_by="attendance_date desc",
            limit=5,
            ignore_permissions=True
        )

        # Check if today's attendance is already in the list
        today_date = get_datetime(nowdate()).date()
        has_today = False
        for att in attendance_list:
            # att.attendance_date can be date or str
            att_date = get_datetime(att.attendance_date).date()
            if att_date == today_date:
                has_today = True
                break
        
        # If no Attendance record for today, check Employee Checkin
        if not has_today:
            today_checkins = frappe.get_all("Employee Checkin", filters={
                "employee": employee,
                "time": ["between", [f"{today_date} 00:00:00", f"{today_date} 23:59:59"]]
            }, fields=["time", "log_type"], order_by="time asc")

            if today_checkins:
                # Construct synthetic record
                first_log = today_checkins[0]
                last_log = today_checkins[-1] if len(today_checkins) > 1 else None
                
                # Calculate synthetic working hours
                wh = 0
                if last_log and last_log.time != first_log.time:
                     start = get_datetime(first_log.time)
                     end = get_datetime(last_log.time)
                     wh = (end - start).total_seconds() / 3600.0

                synthetic_att = frappe._dict({
                    "attendance_date": today_date,
                    "status": "Present",
                    "in_time": first_log.time,
                    "out_time": last_log.time if last_log and last_log.time != first_log.time else None,
                    "working_hours": wh
                })
                attendance_list.insert(0, synthetic_att)
        
        # Format for frontend
        data = []
        for att in attendance_list:
            # Fallback: Check 'Employee Checkin' if in_time/out_time missing
            # This handles cases where Attendance is marked 'Present' but times are not synced
            if not att.get("in_time") or not att.get("out_time"):
                try:
                    logs = frappe.get_all("Employee Checkin", filters={
                        "employee": employee,
                        "time": ["between", [f"{att.attendance_date} 00:00:00", f"{att.attendance_date} 23:59:59"]]
                    }, fields=["time", "log_type"], order_by="time asc")

                    if logs:
                        # First log is IN
                        if not att.get("in_time"):
                            att.in_time = logs[0].time
                        
                        # Last log is OUT (if multiple)
                        if not att.get("out_time") and len(logs) > 0:
                             att.out_time = logs[-1].time
                             
                    # Recalculate working hours if possible and missing
                    if not att.get("working_hours") and att.get("in_time") and att.get("out_time"):
                         start = get_datetime(att.in_time)
                         end = get_datetime(att.out_time)
                         diff = (end - start).total_seconds() / 3600.0
                         if diff > 0:
                             att.working_hours = diff
                except Exception as e:
                    pass

            in_time = format_time(att.get("in_time"))
            out_time = format_time(att.get("out_time"))
            
            # Format working hours
            wh = ""
            if att.get("working_hours"):
                try:
                    wh = f"{float(att.working_hours):.1f}h"
                except: pass

            data.append({
                "date": formatdate(att.attendance_date),
                "raw_date": att.attendance_date,
                "day": get_datetime(att.attendance_date).strftime("%A"),
                "status": att.status,
                "in_time": in_time,
                "out_time": out_time,
                "working_hours": wh
            })
            
        return data
    except Exception as e:
        pass
        return []

def format_time(time_val):
    if not time_val: return "--:--"
    return get_datetime(time_val).strftime("%I:%M %p")

@frappe.whitelist(allow_guest=True)
def get_employee_holidays(employee):
    """
    Uses the standard ERPNext method to fetch holidays.
    """
    if not employee:
        return []
        
    try:
        from erpnext.setup.doctype.employee.employee import get_holiday_list_for_employee
        
        # This returns the name of the holiday list
        holiday_list_name = get_holiday_list_for_employee(employee)
        
        if not holiday_list_name:
            return []
            
        # Now fetch the holidays from that list for the current year
        year_start = get_datetime(nowdate()).replace(month=1, day=1)
        year_end = get_datetime(nowdate()).replace(month=12, day=31)
        
        holidays = frappe.get_all("Holiday",
            filters={
                "parent": holiday_list_name,
                "holiday_date": ["between", [nowdate(), year_end]]
            },
            fields=["holiday_date", "description"],
            order_by="holiday_date asc",
            limit=20
        )
        
        data = []
        for h in holidays:
            data.append({
                "date": formatdate(h.holiday_date),
                "description": h.description,
                "day": get_datetime(h.holiday_date).strftime("%A")
            })
            
        return data

    except ImportError:
         # Fallback if ERPNext module not found (unlikely)
         return fetch_next_15_days_holidays(employee).get("holidays", [])
    except Exception as e:
        pass
        return []
