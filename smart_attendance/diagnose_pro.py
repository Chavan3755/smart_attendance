
import sys
import os
import frappe

# Initialize frappe (assuming we are running with bench execute, frappe is already init, but strict/standalone check requires init)
if not frappe.db:
    frappe.init(site="demo.dexciss.tech")
    frappe.connect()

print("--- DIAGNOSTICS START ---")

# 1. Check frappe.utils
try:
    from frappe.utils import time_diff_in_hours
    print("[PASS] frappe.utils.time_diff_in_hours exists.")
except ImportError:
    print("[FAIL] frappe.utils.time_diff_in_hours MISSING. This will crash custom_checkin_employee_id.py")
except Exception as e:
    print(f"[FAIL] Error importing frappe.utils: {e}")

# 2. Check custom_checkin_employee_id
try:
    from smart_attendance.smart_attendance.api.custom_checkin_employee_id import mark_kiosk_attendance
    print("[PASS] custom_checkin_employee_id imported successfully.")
except Exception as e:
    print(f"[FAIL] custom_checkin_employee_id import failed: {e}")
    import traceback
    traceback.print_exc()

# 3. Check face_verification
try:
    from smart_attendance.smart_attendance.api.face_verification import mark_attendance_by_face
    print("[PASS] face_verification imported successfully.")
except Exception as e:
    print(f"[FAIL] face_verification import failed: {e}")
    import traceback
    traceback.print_exc()

# 4. Check API module itself
try:
    import smart_attendance.api
    print("[PASS] smart_attendance.api imported successfully.")
except Exception as e:
    print(f"[FAIL] smart_attendance.api import failed! This causes 500 on all API calls. Error: {e}")
    import traceback
    traceback.print_exc()

print("--- DIAGNOSTICS END ---")
