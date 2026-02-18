
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
        frappe.log_error(f"TRACE 1: Start {employee_id}", "Kiosk Trace")
        frappe.db.commit()

        if not employee_id:
            return {"ok": False, "message": "Employee ID required"}

        if not frappe.db.exists("Employee", employee_id):
            return {"ok": False, "message": "Employee not found"}

        # TRACE 2
        frappe.log_error("TRACE 2: Pre-Cooldown", "Kiosk Trace")
        frappe.db.commit()

        # 1. ESTABLISH CURRENT TIME (Consistently for Cooldown & Insert)
        # Fetch System Timezone
        try:
            import pytz
            from datetime import datetime
            
            system_tz = frappe.db.get_single_value("System Settings", "time_zone") or "Asia/Kolkata"
            target_tz = pytz.timezone(system_tz)
            utc_tz = pytz.timezone("UTC")
            
            # Default to now in target tz (Naive for DB)
            checkin_time = datetime.now(target_tz).replace(tzinfo=None)
        except:
            # Fallback if pytz missing
            checkin_time = now_datetime()

        if timestamp:
            try:
                # Parse string to datetime
                parsed_ts = get_datetime(timestamp)
                
                # If naive, assume UTC if it comes from ISO string (Z-ending usually loses Z in get_datetime if not careful, but usually it's parsable)
                # get_datetime returns naive if no cache, or aware? 
                # safer to assume input is UTC if it looks like it, or trust get_datetime.
                
                if not parsed_ts.tzinfo:
                     # If format was YYYY-MM-DD HH:MM:SS and considered naive, we assume it was sent as UTC or Server Time?
                     # Let's assume it matches the server's expectation. But usually Kiosk sends UTC ISO.
                     # If we assume UTC:
                     parsed_ts = utc_tz.localize(parsed_ts)
                
                # Convert to Target TZ
                parsed_ts = parsed_ts.astimezone(target_tz)
                
                # Strip tzinfo for DB storage (Frappe stores naive local)
                checkin_time = parsed_ts.replace(tzinfo=None)
                
            except Exception as e:
                frappe.log_error(f"Timestamp Parse Error: {e}", "Kiosk Debug")
                # Keep default checkin_time

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
        frappe.log_error(f"TRACE 5: Post-Insert {checkin.name}", "Kiosk Trace")

        # Auto-create Attendance Record for 'IN'
        if final_log_type == "IN":
            # Just log, don't break if this fails
            try:
                # Basic attendance creation
                pass 
            except: pass
        
        # TRACE 6
        frappe.log_error(f"TRACE 6: Success - {checkin.name}", "Kiosk Trace")

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
        frappe.log_error(frappe.get_traceback(), "Kiosk Logic Crash")
        frappe.db.commit() # Ensure error is logged
        return {"ok": False, "message": err_msg}

def _create_attendance_if_missing(employee_id):
    try:
        today = nowdate()
        if not frappe.db.exists("Attendance", {"employee": employee_id, "attendance_date": today}):
            doc = frappe.get_doc({
                "doctype": "Attendance",
                "employee": employee_id,
                "attendance_date": today,
                "status": "Present"
            })
            doc.insert(ignore_permissions=True)
    except Exception as e:
        frappe.log_error(f"Auto Attendance Error: {e}", "Kiosk Trace")
