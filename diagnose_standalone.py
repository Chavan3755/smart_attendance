
import sys
import os

# Add common paths
current_dir = os.getcwd() # apps/smart_attendance
sys.path.append(current_dir)
sys.path.append(os.path.abspath(os.path.join(current_dir, '..', 'frappe')))

try:
    import frappe
    print("Frappe module loaded.")
except ImportError:
    print("Failed to load frappe module.")

print("1. Checking frappe.utils for time_diff_in_hours...")
try:
    from frappe.utils import time_diff_in_hours
    print("SUCCESS: time_diff_in_hours exists.")
except ImportError:
    print("FAIL: time_diff_in_hours NOT found in frappe.utils")
except Exception as e:
    print(f"FAIL: Error importing frappe.utils: {e}")

print("2. Checking smart_attendance package structure...")
try:
    import smart_attendance
    print(f"smart_attendance loaded from: {smart_attendance.__file__}")
except Exception as e:
    print(f"Error loading root smart_attendance: {e}")

print("3. Checking custom_checkin_employee_id import...")
try:
    # Based on what we saw in finding files
    from smart_attendance.smart_attendance.api.custom_checkin_employee_id import mark_kiosk_attendance
    print("SUCCESS: custom_checkin_employee_id imported.")
except ImportError as e:
    print(f"FAIL: ImportError: {e}")
except Exception as e:
    print(f"FAIL: Exception: {e}")

print("4. Checking face_verification import...")
try:
    from smart_attendance.smart_attendance.api.face_verification import mark_attendance_by_face
    print("SUCCESS: face_verification imported.")
except Exception as e:
    print(f"FAIL: Exception: {e}")
