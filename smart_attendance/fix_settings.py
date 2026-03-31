import frappe

def fix_settings():
    try:
        doc = frappe.get_single("System Settings")
        doc.time_zone = "Asia/Kolkata"
        doc.save(ignore_permissions=True)
        print("System Settings initialized successfully.")
    except Exception as e:
        print(f"Failed to load System Settings: {e}")
        # Try creating it raw if feasible, or just initializing it
        try:
            doc = frappe.new_doc("System Settings")
            doc.time_zone = "Asia/Kolkata"
            doc.insert(ignore_permissions=True)
            print("System Settings inserted successfully.")
        except Exception as e2:
            print(f"Failed to insert System Settings: {e2}")

    frappe.db.commit()

fix_settings()
