import inspect
import sys
import frappe

# Setup path
sys.path.append("/home/erpnext/nexovate-live/apps/smart_attendance")

# Init frappe (minimal)
frappe.init(site="nexovate.co.in", sites_path="/home/erpnext/nexovate-live/sites")
frappe.connect()

import smart_attendance
import smart_attendance.smart_attendance.api as api

print("Package Path:", smart_attendance.__file__)
print("API Module Path:", api.__file__)

print("\n--- Source of verify_face ---")
try:
    src = inspect.getsource(api.verify_face)
    print(src[:500]) # First 500 chars
    
    if "Kiosk Debug" in src:
        print("\n✅ 'Kiosk Debug' FOUND in loaded source.")
    else:
        print("\n❌ 'Kiosk Debug' NOT FOUND in loaded source.")
except Exception as e:
    print("Could not get source:", e)
