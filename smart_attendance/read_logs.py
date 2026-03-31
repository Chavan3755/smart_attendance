import frappe

def get_logs():
    logs = frappe.db.get_list("Error Log", 
        fields=["method", "error", "creation"], 
        limit=5, 
        order_by="creation desc"
    )
    for l in logs:
        print(f"--- {l.creation} | {l.method} ---")
        print(l.error[:500])  # Print first 500 chars

get_logs()
