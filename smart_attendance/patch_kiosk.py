
import frappe
from frappe.utils import now_datetime

def run_patch():
    print("Starting forceful patch for Attendance fields...")
    
    fields = ['in_time', 'out_time']
    properties = {
        'depends_on': '',
        'read_only': '0'
    }
    
    for field in fields:
        for prop, val in properties.items():
            # Check if exists
            exists = frappe.db.get_value("Property Setter", 
                {"doc_type": "Attendance", "field_name": field, "property": prop}, 
                "name")
                
            if exists:
                frappe.db.sql("""
                    UPDATE `tabProperty Setter`
                    SET value = %s, modified = %s
                    WHERE name = %s
                """, (val, now_datetime(), exists))
                print(f"Updated {field} {prop} (ID: {exists})")
            else:
                # Create new
                name = frappe.generate_hash(length=10)
                frappe.db.sql("""
                    INSERT INTO `tabProperty Setter`
                    (name, doc_type, field_name, property, value, is_system_generated, creation, modified, modified_by, owner, doctype_or_field)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (name, 'Attendance', field, prop, val, 0, now_datetime(), now_datetime(), 'Administrator', 'Administrator', 'DocField'))
                print(f"Inserted {field} {prop} (ID: {name})")

    frappe.clear_cache(doctype="Attendance")
    frappe.db.commit()
    print("Patch completed successfully.")

