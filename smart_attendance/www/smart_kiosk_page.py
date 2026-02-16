
import frappe
import re
import json

no_cache = 1

SCRIPT_TAG_PATTERN = re.compile(r"\<script[^<]*\</script\>")
CLOSING_SCRIPT_TAG_PATTERN = re.compile(r"</script\>")

def get_context(context):
    if frappe.session.user == "Guest":
        boot = frappe.website.utils.get_boot_data()
    else:
        try:
            boot = frappe.sessions.get()
        except Exception as e:
            # If session boot fails, try standard boot
            boot = frappe.website.utils.get_boot_data()
    
    # Ensure CSRF token is in context for the template
    csrf_token = boot.get("csrf_token")
    if not csrf_token and frappe.local.session.data.csrf_token:
        csrf_token = frappe.local.session.data.csrf_token
        
    context.csrf_token = csrf_token

    # Standardize boot for frontend (optional, based on user snippet)
    # The user wanted a specific boot JSON format
    boot_json = frappe.as_json(boot, indent=None, separators=(",", ":"))
    
    # Strip scripts if needed (from User snippet)
    boot_json = SCRIPT_TAG_PATTERN.sub("", boot_json) # Standard in some frappe versions
    boot_json = CLOSING_SCRIPT_TAG_PATTERN.sub("", boot_json)

    context.update({
        "build_version": frappe.utils.get_build_version(),
        "boot": boot_json 
    })
    
    context.title = "Face Kiosk"
    return context
