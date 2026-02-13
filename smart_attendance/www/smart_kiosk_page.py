import frappe

no_cache = 1

def get_context(context):
    context.no_cache = 1
    context.allow_guest = True
    context.title = "Face Kiosk"
    try:
        context.csrf_token = frappe.sessions.get_csrf_token()
    except Exception:
        context.csrf_token = "Guest"
    context.site_url = frappe.utils.get_url()
