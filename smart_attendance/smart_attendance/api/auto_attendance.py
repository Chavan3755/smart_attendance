import frappe
from frappe.utils import nowdate

def create_realtime_attendance(doc, method=None):
    try:
        
        if doc.log_type != "IN":
            return

        employee = doc.employee
        from frappe.utils import get_datetime
        checkin_dt = get_datetime(doc.time)
        attendance_date = checkin_dt.date()
        
        existing = frappe.db.exists("Attendance", {
            "employee": employee,
            "attendance_date": attendance_date
        })

        if existing:
            att = frappe.get_doc("Attendance", existing)
            att.status = "Present"
            if not att.in_time:
                att.in_time = doc.time
            att.flags.ignore_permissions = True
            att.save()
            frappe.db.commit()
            return

       
        att = frappe.get_doc({
            "doctype": "Attendance",
            "employee": employee,
            "attendance_date": attendance_date,
            "status": "Present",
            "in_time": doc.time
        })

        att.flags.ignore_permissions = True
        att.insert()
        frappe.db.commit()

    except Exception as e:
        pass
