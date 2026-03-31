import frappe

def before_request():
    # Bypass CSRF for Face Kiosk endpoints
    path = frappe.request.path
    if path and ("/api/method/smart_attendance.smart_attendance.api.verify_face" in path 
              or "/api/method/smart_attendance.smart_attendance.api.enroll_face" in path
              or "/api/method/smart_attendance.smart_attendance.api.get_csrf_token" in path
              or "verify_face" in path
              or "get_csrf_token" in path):
        
        # Log that we are bypassing
        # frappe.log_error(f"Bypassing CSRF for {path}", "Kiosk Bypass")
        
        # Force CSRF token match to avoid 417
        frappe.flags.in_test = True 
        
        # Ensure ignoring csrf
        if hasattr(frappe.local, 'conf'):
             frappe.local.conf.ignore_csrf = 1
 
