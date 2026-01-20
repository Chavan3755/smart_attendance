import frappe
from frappe.utils import nowdate

@frappe.whitelist(allow_guest=True)
def safe_employee_checkin(employee_id):
    # 1️⃣ Validate input
    if not employee_id:
        return {
            "ok": False,
            "message": "Employee ID is required"
        }

    # 2️⃣ Check Employee exists (KEY REQUIREMENT)
    if not frappe.db.exists("Employee", employee_id):
        return {
            "ok": False,
            "message": "Employee ID does not exist"
        }

    # 3️⃣ Get last check-in log_type
    last_log = frappe.db.get_value(
        "Employee Checkin",
        {"employee": employee_id},
        "log_type",
        order_by="creation desc"
    )

    # 4️⃣ Decide next log_type
    log_type = "OUT" if last_log == "IN" else "IN"

    # 5️⃣ Create Employee Checkin
    checkin = frappe.get_doc({
        "doctype": "Employee Checkin",
        "employee": employee_id,
        "log_type": log_type,
        "device_id": "FACE_KIOSK"
    })
    checkin.insert(ignore_permissions=True)

    # 6️⃣ Auto-create Attendance (only on IN)
    if log_type == "IN":
        if not frappe.db.exists(
            "Attendance",
            {
                "employee": employee_id,
                "attendance_date": nowdate()
            }
        ):
            attendance = frappe.get_doc({
                "doctype": "Attendance",
                "employee": employee_id,
                "attendance_date": nowdate(),
                "status": "Present"
            })
            attendance.insert(ignore_permissions=True)

    return {
        "ok": True,
        "log_type": log_type
    }
