import frappe

no_cache = 1

def get_context(context):
    context.no_cache = 1
    context.allow_guest = True
    context.title = "Face Kiosk"
    # Ensure a valid CSRF token is available even for Guests
    # Always force a fresh CSRF token to prevent stale session issues
    frappe.local.session.data.csrf_token = frappe.generate_hash()
    frappe.db.commit() 

    context.csrf_token = frappe.local.session.data.csrf_token

    context.site_url = frappe.utils.get_url()
