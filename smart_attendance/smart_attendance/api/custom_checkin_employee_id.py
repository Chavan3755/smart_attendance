
import frappe
from frappe.utils import nowdate, now_datetime, get_datetime

# Remove time_diff_in_hours import to avoid potential import issues, define locally or use simple math
def simple_time_diff_hours(dt1, dt2):
    if not dt1 or not dt2: return 0
    diff = dt1 - dt2
    return diff.total_seconds() / 3600.0

@frappe.whitelist(allow_guest=True)
def check_employee_exists(employee_id):
    return bool(frappe.db.exists("Employee", employee_id))

@frappe.whitelist(allow_guest=True)
def mark_kiosk_attendance(employee, log_type=None, timestamp=None):
    """
    Safely mark attendance with AGGRESSIVE TRACING.
    """
    try:
        employee_id = employee
        # TRACE 1
        pass
        frappe.db.commit()

        if not employee_id:
            return {"ok": False, "message": "Employee ID required"}

        if not frappe.db.exists("Employee", employee_id):
            return {"ok": False, "message": "Employee not found"}

        # TRACE 2
        pass
        frappe.db.commit()

        # 1. ESTABLISH CURRENT TIME
        # Priority: Employee's User Timezone > Session User Timezone > System Timezone
        target_tz_str = None
        
        try:
            # A) Try Session User first (Highest Priority as per request)
            if frappe.session.user and frappe.session.user != "Guest":
                target_tz_str = frappe.db.get_value("User", frappe.session.user, "time_zone")

            # B) If not found, try Employee -> User
            if not target_tz_str and employee_id:
                user_id = frappe.db.get_value("Employee", employee_id, "user_id")
                if user_id:
                     target_tz_str = frappe.db.get_value("User", user_id, "time_zone")
            
            # C) Fallback to System Timezone
            if not target_tz_str:
                from frappe.utils import get_system_timezone
                target_tz_str = get_system_timezone() or "Asia/Kolkata"
                
            # Log Timezone Decision
            # frappe.log_error(f"Timezone Selected: {target_tz_str} for {employee_id} (Session: {frappe.session.user})", "Kiosk TZ Debug")

            import pytz
            from datetime import datetime
            
            tz = pytz.timezone(target_tz_str)
            
            # Get UTC time first, then convert to Target Timezone
            utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
            checkin_time = utc_now.astimezone(tz).replace(tzinfo=None)
            
        except Exception as e:
            pass
            checkin_time = now_datetime()

        # 2. COOLDOWN CHECK (Using established checkin_time)
        last_log_time = frappe.db.get_value("Employee Checkin", 
            {"employee": employee_id}, 
            "time", 
            order_by="creation desc"
        )
        
        if last_log_time:
            # Safe datetime conversion
            last_dt = get_datetime(last_log_time)
            
            # Diff = Current Attempt Time - Last Attempt Time
            # Logic: If I check in at 5:00, last was 4:59:30 -> Diff = 30s. Wait.
            diff = (checkin_time - last_dt).total_seconds()
            
            # Handle negative diff (Clock skew where new time < old time) or short diff
            # Allow check-in if diff is huge negative (e.g. days) just in case, but block imminent repeats
            # Standard cooldown: 45 seconds (User requested ~49s ok)
            if 0 <= diff < 45: 
                return {"ok": False, "message": f"Please wait {int(45 - diff)}s before next check-in."}
            elif -3600 < diff < 0:
                 # If time moved backwards slightly (up to 1 hour), block to be safe against glitches
                 return {"ok": False, "message": "Clock skew detected. Please wait a moment."}

        # 3. DETERMINE LOG TYPE (IN/OUT)
        final_log_type = "IN"
        clean_type = str(log_type).upper().strip() if log_type else "AUTO"
        
        if clean_type in ["IN", "OUT"]:
            final_log_type = clean_type
        else:
            # AUTO LOGIC: Flip based on last check-in
            # Re-fetch last checkin including log_type (since we only fetched time above)
            last_checkin_data = frappe.db.get_value("Employee Checkin", 
                {"employee": employee_id}, 
                ["log_type", "time"], 
                order_by="time desc"
            )

            if last_checkin_data:
                l_type, l_time = last_checkin_data
                # Flip logic
                final_log_type = "OUT" if l_type == "IN" else "IN"
                
                # Smart Reset: If last punch was IN but > 16 hours ago, assume new day -> IN
                if l_type == "IN":
                    try:
                        # Use our established checkin_time for robust comparison
                        l_dt = get_datetime(l_time)
                        # diff in seconds
                        if (checkin_time - l_dt).total_seconds() > 16 * 3600:
                             final_log_type = "IN"
                    except: pass
            else:
                final_log_type = "IN"  # First ever punch

        # Create Checkin
        checkin = frappe.get_doc({
            "doctype": "Employee Checkin",
            "employee": employee_id,
            "log_type": final_log_type, 
            "device_id": "FACE_KIOSK",
            "time": checkin_time
        })
        checkin.insert(ignore_permissions=True)
        # Force immediate commit to persist punch
        frappe.db.commit()

        # TRACE 5
        pass


        
        # TRACE 6
        pass

        emp_name = frappe.db.get_value("Employee", employee_id, "employee_name")

        return {
            "ok": True,
            "log_type": final_log_type,
            "employee": employee_id,
            "employee_name": emp_name,
            "time": checkin.time,
            "name": checkin.name
        }

    except Exception as e:
        frappe.db.rollback()
        err_msg = f"Kiosk Logic Crash: {str(e)}"
        pass
        frappe.db.commit() # Ensure error is logged
        return {"ok": False, "message": err_msg}


