
import frappe

def execute():
    # Fix Attendance fields in_time and out_time visibility by removing depends_on
    for fieldname in ['in_time', 'out_time']:
        if not frappe.db.exists('Property Setter', {'doc_type': 'Attendance', 'field_name': fieldname, 'property': 'depends_on'}):
            frappe.make_property_setter({
                'doctype': 'Attendance',
                'doctype_or_field': 'DocField',
                'fieldname': fieldname,
                'property': 'depends_on',
                'value': '',
                'is_system_generated': 0
            })
        else:
            ps = frappe.get_doc('Property Setter', {'doc_type': 'Attendance', 'field_name': fieldname, 'property': 'depends_on'})
            ps.value = ''
            ps.save()
            
    # Also ensure they are not read_only if that is an issue, but usually system handles it.
    # The JSON showed read_only: 1. This might be standard. 
    # If user wants to edit them manually in backend, we should perhaps remove read_only too?
    # "fix this this in_time and in_time this field"
    # Usually in_time/out_time are set by system but managers might need to edit.
    # Let's remove read_only constraint too just in case.
    
    for fieldname in ['in_time', 'out_time']:
        if not frappe.db.exists('Property Setter', {'doc_type': 'Attendance', 'field_name': fieldname, 'property': 'read_only'}):
             frappe.make_property_setter({
                'doctype': 'Attendance',
                'doctype_or_field': 'DocField',
                'fieldname': fieldname,
                'property': 'read_only',
                'value': '0',
                'is_system_generated': 0
            })
        else:
            ps = frappe.get_doc('Property Setter', {'doc_type': 'Attendance', 'field_name': fieldname, 'property': 'read_only'})
            ps.value = '0'
            ps.save()

    frappe.db.commit()
    print("Attendance fields updated.")

if __name__ == "__main__":
    execute()
