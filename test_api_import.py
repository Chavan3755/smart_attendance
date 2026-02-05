
import sys
import os

current_dir = os.getcwd() # apps/smart_attendance
sys.path.append(current_dir)
sys.path.append(os.path.abspath(os.path.join(current_dir, '..', 'frappe')))

try:
    import frappe
except:
    pass

print("Testing import of smart_attendance.smart_attendance.api ...")
try:
    import smart_attendance.smart_attendance.api
    print("SUCCESS: api.py imported.")
except ImportError as e:
    print(f"FAIL: ImportError: {e}")
except SyntaxError as e:
    print(f"FAIL: SyntaxError: {e}")
except Exception as e:
    print(f"FAIL: Exception: {e}")
    import traceback
    traceback.print_exc()
