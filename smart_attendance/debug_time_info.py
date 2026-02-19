
import frappe
from frappe.utils import get_system_timezone, now_datetime
from datetime import datetime
import pytz

def check_time():
    print("----- Debug Time Info -----")
    
    # 1. System Settings Timezone
    sys_tz = get_system_timezone()
    print(f"Frappe System Timezone: {sys_tz}")
    
    # 2. OS Time (now_datetime)
    now_dt = now_datetime()
    print(f"frappe.utils.now_datetime(): {now_dt}")
    
    # 3. Python datetime.now()
    py_now = datetime.now()
    print(f"datetime.now() (OS Local): {py_now}")
    
    # 4. UTC Time
    utc_now = datetime.utcnow()
    print(f"datetime.utcnow(): {utc_now}")
    
    # 5. Explicit Asia/Kolkata
    try:
        tz = pytz.timezone("Asia/Kolkata")
        kol_time = datetime.now(tz)
        print(f"Asia/Kolkata Time: {kol_time}")
    except Exception as e:
        print(f"Asia/Kolkata Error: {e}")

    # 6. Check Error Logs for Kiosk Debug
    print("\n----- Recent Error Logs (Last 5) -----")
    logs = frappe.get_all("Error Log", fields=["creation", "method", "error"], order_by="creation desc", limit=5)
    for log in logs:
        print(f"[{log.creation}] {log.method}: {log.error[:100]}...")

if __name__ == "__main__":
    frappe.connect()
    check_time()
