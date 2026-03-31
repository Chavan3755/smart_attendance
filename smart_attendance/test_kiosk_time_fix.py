
import frappe
from smart_attendance.smart_attendance.api.custom_checkin_employee_id import mark_kiosk_attendance
from frappe.utils import now_datetime, get_datetime

def test_fix():
    print("--- Testing Timestamp Logic ---")
    
    # Simulate Client sending Future Time (Yakutsk time ~ 21:00)
    # Current Server Time is approx 17:45
    fake_client_time = "2026-02-18 21:30:00"
    employee = "HR-EMP-00003" # Siddharth Jain
    
    print(f"Simulating Check-in with Client Time: {fake_client_time}")
    
    try:
        # Call API
        res = mark_kiosk_attendance(employee, log_type="IN", timestamp=fake_client_time)
        
        if res.get('ok'):
            checkin_name = res.get('name')
            checkin_time = res.get('time')
            
            print(f"Check-in Created: {checkin_name}")
            print(f"Result Time: {checkin_time}")
            
            # Verify
            c_time_str = str(checkin_time)
            if "21:30" in c_time_str:
                print("FAIL: System used the incorrect Client Timestamp!")
            else:
                print("PASS: System ignored Client Timestamp and used Server/System time.")
                
            # Check DB
            db_time = frappe.db.get_value("Employee Checkin", checkin_name, "time")
            print(f"DB Stored Time: {db_time}")
            
        else:
            print(f"Failed: {res.get('message')}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    frappe.connect()
    test_fix()
