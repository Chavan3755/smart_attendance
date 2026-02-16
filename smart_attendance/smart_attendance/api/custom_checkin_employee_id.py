
import frappe
from frappe.utils import nowdate, now_datetime, get_datetime

# Remove time_diff_in_hours import to avoid potential import issues, define locally or use simple math
def simple_time_diff_hours(dt1, dt2):
    if not dt1 or not dt2: return 0
    diff = dt1 - dt2
    return diff.total_seconds() / 3600.0

@frappe.whitelist(allow_guest=True)
def check_employee_exists(employee_id):
    return bool(frappe.db.exists("Employee", employee_id))

@frappe.whitelist(allow_guest=True)
def mark_kiosk_attendance(employee, log_type=None):
    """
    Safely mark attendance with AGGRESSIVE TRACING.
    """
    try:
        employee_id = employee
        # TRACE 1
        frappe.log_error(f"TRACE 1: Start {employee_id}", "Kiosk Trace")
        frappe.db.commit()

        if not employee_id:
            return {"ok": False, "message": "Employee ID required"}

        if not frappe.db.exists("Employee", employee_id):
            return {"ok": False, "message": "Employee not found"}

        # TRACE 2
        frappe.log_error("TRACE 2: Pre-Cooldown", "Kiosk Trace")
        frappe.db.commit()

        # 30-Second Cooldown Check
        last_log_time = frappe.db.get_value("Employee Checkin", 
            {"employee": employee_id}, 
            "time", 
            order_by="creation desc"
        )
        
        if last_log_time:
            # Safe datetime conversion
            last_dt = get_datetime(last_log_time)
            now_dt = now_datetime()
            diff = (now_dt - last_dt).total_seconds()
            
            if diff < 60:
                return {"ok": False, "message": f"Please wait {int(60 - diff)}s before next check-in."}

        # TRACE 3
        frappe.log_error("TRACE 3: Pre-LogType", "Kiosk Trace")
        
        # Determine log type if not provided or AUTO
        if not log_type or log_type == "AUTO":
            last_checkin = frappe.db.get_value("Employee Checkin", 
                {"employee": employee_id}, 
                ["log_type", "time"], 
                order_by="time desc"
            )

            if last_checkin:
                l_type, l_time = last_checkin
                # Flip logic: If last was IN, next is OUT
                new_type = "OUT" if l_type == "IN" else "IN"
                
                # Smart Reset: If last IN was > 16 hours ago, force new IN (forgot punch out)
                if l_type == "IN":
                    l_dt = get_datetime(l_time)
                    if (now_datetime() - l_dt).total_seconds() > 16 * 3600:
                         new_type = "IN"
                
                log_type = new_type
            else:
                log_type = "IN" # First ever punch

        # TRACE 4
        frappe.log_error(f"TRACE 4: Inserting {log_type}", "Kiosk Trace")

        # Create Checkin
        checkin = frappe.get_doc({
            "doctype": "Employee Checkin",
            "employee": employee_id,
            "log_type": log_type,
            "device_id": "FACE_KIOSK",
            "time": now_datetime()
        })
        checkin.insert(ignore_permissions=True)

        # TRACE 5
        frappe.log_error("TRACE 5: Post-Insert", "Kiosk Trace")
        frappe.db.commit()

        # Auto-create Attendance Record for 'IN'
        if log_type == "IN":
            _create_attendance_if_missing(employee_id)
        
        # TRACE 6
        frappe.log_error("TRACE 6: Success", "Kiosk Trace")
        frappe.db.commit()

        return {
            "ok": True,
            "log_type": log_type,
            "employee": employee_id,
            "time": checkin.time
        }

    except Exception as e:
        frappe.db.rollback()
        err_msg = f"Kiosk Logic Crash: {str(e)}"
        frappe.log_error(frappe.get_traceback(), "Kiosk Logic Crash")
        frappe.db.commit() # Ensure error is logged
        return {"ok": False, "message": err_msg}

def _create_attendance_if_missing(employee_id):
    try:
        today = nowdate()
        if not frappe.db.exists("Attendance", {"employee": employee_id, "attendance_date": today}):
            doc = frappe.get_doc({
                "doctype": "Attendance",
                "employee": employee_id,
                "attendance_date": today,
                "status": "Present"
            })
            doc.insert(ignore_permissions=True)
    except Exception as e:
        frappe.log_error(f"Auto Attendance Error: {e}", "Kiosk Trace")
