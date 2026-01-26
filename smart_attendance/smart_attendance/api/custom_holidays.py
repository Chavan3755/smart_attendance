import frappe
from frappe.utils import getdate, add_days, nowdate

@frappe.whitelist(allow_guest=True)
def fetch_next_15_days_holidays(date=None, employee=None):

    # 📅 Start date = today
    start_date = getdate(date) if date else getdate(nowdate())
    end_date = add_days(start_date, 15)
    
    holiday_list = None
    
    if employee:
        # Check active Shift Assignment
        # Logic: Active assignment where start_date <= today and (end_date >= today or end_date is null)
        assignments = frappe.get_all("Shift Assignment", filters={
            "employee": employee,
            "start_date": ["<=", start_date],
            "status": "Active"
        }, fields=["shift_type", "end_date"])
        
        # Find the first valid assignment for today
        valid_shift = None
        for a in assignments:
            if not a.end_date or getdate(a.end_date) >= start_date:
                valid_shift = a.shift_type
                break
        
        if valid_shift:
            # Check if Shift Type has a holiday list
            holiday_list = frappe.db.get_value("Shift Type", valid_shift, "holiday_list")
        
        if not holiday_list:
            # Fallback to Employee's default
            holiday_list = frappe.db.get_value("Employee", employee, "holiday_list")

    # ✅ If still no list, Get LATEST created Holiday List (fallback)
    if not holiday_list:
        holiday_list = frappe.db.get_value(
            "Holiday List",
            {},
            "name",
            order_by="creation desc"
        )

    if not holiday_list:
        return {"holidays": []}

    # 🔥 SQL QUERY
    holidays = frappe.db.sql(
        """
        SELECT
            holiday_date,
            description
        FROM
            `tabHoliday`
        WHERE
            parent = %s
            AND holiday_date BETWEEN %s AND %s
        ORDER BY
            holiday_date ASC
        """,
        (holiday_list, start_date, end_date),
        as_dict=True
    )

    return {
        "holiday_list": holiday_list,
        "holidays": [
            {
                "date": h["holiday_date"].strftime("%d-%m-%Y"),
                "name": h["description"]
            }
            for h in holidays
        ]
    }
 