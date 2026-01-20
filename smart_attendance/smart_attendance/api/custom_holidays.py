import frappe
from frappe.utils import getdate, add_days, nowdate

@frappe.whitelist(allow_guest=True)
def fetch_next_15_days_holidays(date=None):

    # 📅 Start date = today
    start_date = getdate(date) if date else getdate(nowdate())
    end_date = add_days(start_date, 15)

    # ✅ Get LATEST created Holiday List (confirmed: 2026)
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
        "holidays": [
            {
                "date": h["holiday_date"].strftime("%d-%m-%Y"),
                "name": h["description"]
            }
            for h in holidays
        ]
    }
 