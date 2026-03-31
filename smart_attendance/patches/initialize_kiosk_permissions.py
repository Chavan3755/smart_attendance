import frappe

def execute():
    """
    Sets up all necessary permissions for the Smart Attendance Kiosk to work for Guest users.
    Run automatically during bench migrate.
    """
    print("Executing Patch: Initialize Kiosk Permissions...")
    
    doctypes_to_grant = [
        "Smart Attendance Settings",
        "Employee",
        "Holiday List",
        "Holiday",
        "Shift Type",
        "Shift Assignment"
    ]
    
    for dt in doctypes_to_grant:
        if not frappe.db.exists("DocType", dt):
            continue
            
        if not frappe.db.exists("Custom DocPerm", {"parent": dt, "role": "Guest"}):
            try:
                frappe.get_doc({
                    "doctype": "Custom DocPerm",
                    "parent": dt,
                    "parenttype": "DocType",
                    "parentfield": "permissions",
                    "role": "Guest",
                    "read": 1,
                    "export": 1 if dt == "Smart Attendance Settings" else 0
                }).insert(ignore_permissions=True)
                print(f"Added Guest Read permission for {dt}")
            except Exception as e:
                print(f"Failed to add custom permission for {dt}: {e}")

    # Ensure a default settings record exists
    if not frappe.db.exists("Smart Attendance Settings", "Smart Attendance Settings"):
        try:
            is_single = frappe.db.get_value("DocType", "Smart Attendance Settings", "issingle")
            if is_single:
                doc = frappe.get_doc("Smart Attendance Settings")
                doc.enable_auto_capture = 1
                doc.confidence_threshold = 0.6
                doc.save(ignore_permissions=True)
            else:
                 frappe.get_doc({
                    "doctype": "Smart Attendance Settings",
                    "name": "Smart Attendance Settings",
                    "enable_auto_capture": 1,
                    "confidence_threshold": 0.6
                }).insert(ignore_permissions=True)
            print("Created/Updated default Smart Attendance Settings")
        except Exception as e:
            print(f"Failed to create settings: {e}")

    frappe.db.commit()
