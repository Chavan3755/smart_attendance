
import frappe
from smart_attendance.smart_attendance.api.custom_checkin_employee_id import mark_kiosk_attendance
import pytz
from datetime import datetime

def test_user_tz():
    print("--- Testing User-Specific Timezone Logic ---")
    
    employee = "HR-EMP-00003" # Siddharth Jain (Default TZ: Asia/Kolkata)
    
    # Let's temporarily change this user's timezone to "America/New_York" to test conversion
    # America/New_York is typically -5 hours relative to UTC (or -4 in DST), while IST is +5.30
    user_id = frappe.db.get_value("Employee", employee, "user_id")
    original_tz = frappe.db.get_value("User", user_id, "time_zone")
    
    print(f"User: {user_id}, Original TZ: {original_tz}")
    
    try:
        # 1. Update to New York
        print("Setting User TZ to America/New_York...")
        frappe.db.set_value("User", user_id, "time_zone", "America/New_York")
        frappe.db.commit()
        
        # 2. Mark Attendance
        # Server is in IST (supposedly). If logic works, check-in time should be ~9.5-10.5 hours BEHIND IST time.
        # e.g. 18:00 IST -> 07:30 EST
        print("Marking Attendance...")
        res = mark_kiosk_attendance(employee, log_type="IN")
        
        if res.get('ok'):
            c_time = res.get('time')
            print(f"Check-in Time (New York): {c_time}")
            
            # Simple validation: Is it significantly behind server time?
            from frappe.utils import now_datetime
            server_now = now_datetime()
            print(f"Server Time (IST/System): {server_now}")
            
            diff = (server_now - c_time).total_seconds()
            print(f"Difference (Server - Checkin): {diff} seconds (~{diff/3600:.2f} hours)")
            
            if diff > 18000: # greater than 5 hours positive diff
                print("PASS: Check-in time is correctly converted to User's TZ (behind server time).")
            else:
                print("FAIL: Check-in time seems too close to server time (conversion might have failed or server is UTC).")
        else:
            print(f"Error: {res.get('message')}")
            
    except Exception as e:
        print(f"Exception: {e}")
        
    finally:
        # Restore
        print(f"Restoring TZ to {original_tz}...")
        frappe.db.set_value("User", user_id, "time_zone", original_tz)
        frappe.db.commit()

if __name__ == "__main__":
    frappe.connect()
    test_user_tz()
