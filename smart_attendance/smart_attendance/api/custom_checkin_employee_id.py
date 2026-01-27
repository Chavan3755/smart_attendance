import frappe
from frappe.utils import nowdate

@frappe.whitelist(allow_guest=True)
def check_employee_exists(employee_id):
    """Simple check if employee exists. Returns boolean."""
    if not employee_id: 
        return False
    return bool(frappe.db.exists("Employee", employee_id))

@frappe.whitelist(allow_guest=True)
def get_last_log(employee_id):
    """Get the last log type for an employee (IN or OUT). Defaults to OUT (so next is IN)."""
    if not employee_id:
        return "OUT"
        
    # RAW SQL to bypass all permission/ORM layers
    last_log = frappe.db.sql("""
        SELECT log_type FROM `tabEmployee Checkin`
        WHERE employee = %s
        ORDER BY creation DESC
        LIMIT 1
    """, (employee_id,))
    
    if last_log and last_log[0][0]:
        return last_log[0][0]
        
    return "OUT"

@frappe.whitelist(allow_guest=True)
def mark_kiosk_attendance(employee_id, log_type=None):
    """
    Safely mark attendance.
    If log_type is provided, uses it. 
    Otherwise compares with last log to toggle IN/OUT.
    """
    if not employee_id:
        return {"ok": False, "message": "Employee ID required"}

    if not frappe.db.exists("Employee", employee_id):
        return {"ok": False, "message": "Employee not found"}

    # Determine log type if not provided
    if not log_type:
        last = get_last_log(employee_id)
        log_type = "OUT" if last == "IN" else "IN"

    # Create Checkin
    checkin = frappe.get_doc({
        "doctype": "Employee Checkin",
        "employee": employee_id,
        "log_type": log_type,
        "device_id": "FACE_KIOSK",
        "time": frappe.utils.now_datetime()
    })
    checkin.insert(ignore_permissions=True)

    # Auto-create Attendance Record for 'IN'
    if log_type == "IN":
        _create_attendance_if_missing(employee_id)
    
    # 🔴 CRITICAL: Commit immediately so subsequent reads see it
    frappe.db.commit()

    return {
        "ok": True,
        "log_type": log_type,
        "employee": employee_id,
        "time": checkin.time
    }

def _create_attendance_if_missing(employee_id):
    """Creates a 'Present' attendance record for today if one doesn't exist."""
    today = nowdate()
    if not frappe.db.exists("Attendance", {"employee": employee_id, "attendance_date": today}):
        try:
            doc = frappe.get_doc({
                "doctype": "Attendance",
                "employee": employee_id,
                "attendance_date": today,
                "status": "Present"
            })
            doc.insert(ignore_permissions=True)
        except Exception:
            pass # Ignore if duplicate error or other issues
