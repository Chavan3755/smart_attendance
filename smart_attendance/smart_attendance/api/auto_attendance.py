import frappe
from frappe.utils import nowdate

def create_realtime_attendance(doc, method=None):
    try:
        
        if doc.log_type != "IN":
            return

        employee = doc.employee
        today = nowdate()

        
        existing = frappe.db.exists("Attendance", {
            "employee": employee,
            "attendance_date": today
        })

        if existing:
            att = frappe.get_doc("Attendance", existing)
            att.status = "Present"
            att.flags.ignore_permissions = True
            att.save()
            frappe.db.commit()
            return

       
        att = frappe.get_doc({
            "doctype": "Attendance",
            "employee": employee,
            "attendance_date": today,
            "status": "Present"
        })

        att.flags.ignore_permissions = True
        att.insert()
        frappe.db.commit()

    except Exception as e:
        frappe.log_error(str(e), "Auto Attendance Error")
