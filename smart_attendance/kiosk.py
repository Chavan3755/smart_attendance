
import frappe
from frappe.utils import nowdate, now_datetime, get_datetime, formatdate
import base64, io, json
from datetime import datetime, date, timedelta

@frappe.whitelist(allow_guest=True)
def ping():
    return {"message": "pong"}

@frappe.whitelist(allow_guest=True)
def verify_face(image_base64=None, log_type=None, device_id=None, device_secret=None, confidence_threshold=0.45, employee=None, timestamp=None, verify_only=False):
    """
    Kiosk calls this endpoint (POST). 
    Explicit arguments used to ensure FormData parsing works correctly.
    """
    try:
        # Debug: Log keys to verify reception
        frappe.log_error(f"Kiosk Verify Called (Explict Args). Device: {device_id}, Log: {log_type}, Time: {timestamp}, Verify Only: {verify_only}", "Kiosk Debug")
        
        # Args are now local variables
        if not confidence_threshold:
             confidence_threshold = 0.45

        # Sanitize log_type
        if not log_type or str(log_type).lower() in ["null", "undefined", "none", ""]:
             log_type = "AUTO"
        
        # Sanitize confidence
        try:
             if confidence_threshold:
                confidence_threshold = float(confidence_threshold)
             else:
                confidence_threshold = 0.45
        except:
             confidence_threshold = 0.45

        # Sanitize verify_only (handle JS "true" string)
        if isinstance(verify_only, str):
            verify_only = (verify_only.lower() == "true")
        
        # 0. WEB KIOSK DELEGATION
        # Treat "null" string as None
        if device_id and str(device_id).lower() in ["null", "undefined"]:
            device_id = None

        if not device_id:
             if not image_base64:
                 return {"ok": False, "message": "No image provided for Kiosk verification"}

             try:
                 # Explicit import to avoid path issues
                 from smart_attendance.smart_attendance.api.face_verification import mark_attendance_by_face
                 verification_method = mark_attendance_by_face
                 
                 if not verification_method:
                     return {"ok": False, "message": "Server Error: Verification module not found"}
                 
                 return verification_method(employee, image_base64, log_type, confidence_threshold, timestamp=timestamp, verify_only=verify_only)
             except ImportError:
                 return {"ok": False, "message": "Server Error: face_verification module import failed (path error)"}
             except Exception as e:
                 frappe.log_error(f"Delegation Error: {str(e)}", "Kiosk Debug")
                 return {"ok": False, "message": f"Server Error: {str(e)}"}

        # Authenticate device (Legacy flow)
        if not device_id or not device_secret:
            frappe.throw("Device credentials required")
        try:
            dev = frappe.get_doc("Attendance Device", device_id)
        except frappe.DoesNotExistError:
            frappe.throw("Invalid device id")
        if not dev.is_active or dev.secret_key != device_secret:
            frappe.throw("Invalid device credentials")
        
        return {"ok": False, "message": "Legacy Device flow not fully implemented in this patch."}

    except Exception as e:
        frappe.log_error(f"Kiosk Verify Error (Top Level): {str(e)}", "Kiosk Crash")
        return {"ok": False, "message": f"System Error: {str(e)}"}
