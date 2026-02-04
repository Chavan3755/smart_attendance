import frappe

def get_context(context):
    # Force redirect to the static asset
    frappe.local.response["type"] = "redirect"
    frappe.local.response["location"] = "/assets/smart_attendance/kiosk.html"
