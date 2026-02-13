import frappe

no_cache = 1

def get_context(context):
    context.no_cache = 1
    context.allow_guest = True
    context.title = "Face Kiosk"
    # Ensure no other framework wrapper interferes
    context.boot = frappe.sessions.get_boot_assets_json()
    context.csrf_token = frappe.sessions.get_csrf_token()
