import frappe
from frappe.model.document import Document
from frappe.utils import get_site_path
import os
import json

# Try importing face_recognition
try:
    import face_recognition
except ImportError:
    face_recognition = None

class EmployeeFace(Document):
    def validate(self):
        # 1) Validate Image
        if not self.face_image:
            frappe.throw("Please upload Face Image before saving.")

        # 2) Trigger encoding if missing or image changed
        # If it's a new doc, or image changed, or encoding is empty
        should_encode = True
        if not self.is_new():
            old_doc = self.get_doc_before_save()
            if old_doc and old_doc.face_image == self.face_image and self.encoding:
                should_encode = False
        
        if should_encode:
            frappe.enqueue(
                "smart_attendance.smart_attendance.doctype.employee_face.employee_face.process_face_encoding",
                queue="long",
                timeout=1500,
                doc_name=self.name,
                file_url=self.face_image
            )
            frappe.msgprint("Face Analysis queued. Please wait...")

def process_face_encoding(doc_name, file_url):
    """
    Background job to:
    1. Resolve file path
    2. face_recognition.face_encodings()
    3. Save encoding
    4. Fix File attachment
    """
    try:
        # Re-import locally for worker context
        import frappe
        import os
        import json
        from frappe.utils import get_site_path
        
        try:
            import face_recognition
            from PIL import Image
            import numpy as np
        except ImportError:
            frappe.log_error("face_recognition not installed", "Employee Face Error")
            return

        # 1) Resolve Path
        file_path = None
        if file_url.startswith("/private/files/"):
            file_path = get_site_path("private", "files", file_url.replace("/private/files/", ""))
        elif file_url.startswith("/files/"):
            file_path = get_site_path("public", "files", file_url.replace("/files/", ""))
        else:
             # Fallback
            file_path = os.path.join(get_site_path(), file_url.lstrip("/"))

        if not file_path or not os.path.exists(file_path):
            frappe.log_error(f"File not found: {file_path}", "Employee Face Job")
            return

        # 2) Generate Encoding
        encoding_list = []
        try:
            img = Image.open(file_path).convert('RGB')
            arr = np.array(img)
            encs = face_recognition.face_encodings(arr)
            if encs:
                encoding_list = encs[0].tolist()
        except Exception as e:
             frappe.log_error(f"Encoding Error: {str(e)}", "Employee Face Job")
             return

        if not encoding_list:
             frappe.log_error(f"No face detected for {doc_name}", "Employee Face Job")
             return

        encoding_str = json.dumps(encoding_list)

        # 3) Update DB
        frappe.db.set_value("Employee Face", doc_name, "encoding", encoding_str)
        
        # 4) FIX File Attachment (Optional but good for housekeeping)
        files = frappe.get_all("File", filters={"file_url": file_url}, fields=["name", "attached_to_name"])
        for f in files:
            if f.attached_to_name != doc_name:
                frappe.db.set_value("File", f.name, {
                    "attached_to_doctype": "Employee Face",
                    "attached_to_name": doc_name,
                    "is_private": 0
                })
        
        frappe.db.commit()
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Employee Face Job Error: {doc_name}")

def check_duplicate_face(new_encoding, current_doc_name):
    """
    Check if the new encoding matches any existing active employee's face.
    Returns: (is_duplicate, matched_employee, distance)
    """
    import face_recognition
    import numpy as np
    import json
    
    # Fetch all other encodings
    # candidates = frappe.db.sql("""
    #     SELECT ef.employee, ef.encoding, ef.name as docname
    #     FROM `tabEmployee Face` ef
    #     INNER JOIN `tabEmployee` e ON ef.employee = e.name
    #     WHERE ef.encoding IS NOT NULL AND ef.encoding != ''
    #     AND e.status = 'Active'
    #     AND ef.name != %s
    # """, (current_doc_name,), as_dict=True)

    # Better query: Get all encodings (even inactive, to be safe? No, only active per requirements)
    candidates = frappe.db.sql("""
        SELECT ef.employee, ef.encoding, ef.name as docname
        FROM `tabEmployee Face` ef
        INNER JOIN `tabEmployee` e ON ef.employee = e.name
        WHERE ef.encoding IS NOT NULL AND ef.encoding != ''
        AND e.status = 'Active'
        AND ef.name != %s
    """, (current_doc_name,), as_dict=True)

    if not candidates:
        return False, None, 1.0

    min_dist = 1.0
    matched_emp = None

    for cand in candidates:
        try:
            db_vector = json.loads(cand.encoding)
            dist = face_recognition.face_distance([np.array(db_vector)], np.array(new_encoding))[0]
            
            if dist < min_dist:
                min_dist = dist
                matched_emp = cand.employee
        except:
            continue

    # STRICT DUPLICATE THRESHOLD
    # If distance is less than 0.45, it is almost certainly the same person.
    if min_dist < 0.45:
        return True, matched_emp, min_dist

    return False, None, min_dist

def process_face_encoding(doc_name, file_url):
    """
    Background job to:
    1. Resolve file path
    2. face_recognition.face_encodings()
    3. CHECK FOR DUPLICATES
    4. Save encoding
    5. Fix File attachment
    """
    try:
        # Re-import locally for worker context
        import frappe
        import os
        import json
        from frappe.utils import get_site_path
        
        try:
            import face_recognition
            from PIL import Image
            import numpy as np
        except ImportError:
            frappe.log_error("face_recognition not installed", "Employee Face Error")
            return

        # 1) Resolve Path
        file_path = None
        if file_url.startswith("/private/files/"):
            file_path = get_site_path("private", "files", file_url.replace("/private/files/", ""))
        elif file_url.startswith("/files/"):
            file_path = get_site_path("public", "files", file_url.replace("/files/", ""))
        else:
             # Fallback
            file_path = os.path.join(get_site_path(), file_url.lstrip("/"))

        if not file_path or not os.path.exists(file_path):
            frappe.log_error(f"File not found: {file_path}", "Employee Face Job")
            return

        # 2) Generate Encoding
        encoding_list = []
        try:
            img = Image.open(file_path).convert('RGB')
            arr = np.array(img)
            encs = face_recognition.face_encodings(arr)
            if encs:
                encoding_list = encs[0].tolist()
        except Exception as e:
             frappe.log_error(f"Encoding Error: {str(e)}", "Employee Face Job")
             return

        if not encoding_list:
             frappe.log_error(f"No face detected for {doc_name}", "Employee Face Job")
             # Optionally update doc to say "No Face Detected"
             frappe.db.add_comment("Employee Face", doc_name, "Error: No face detected in the uploaded image.")
             return

        # 3) CHECK DUPLICATES
        is_dup, match_emp, match_dist = check_duplicate_face(encoding_list, doc_name)
        
        if is_dup:
            msg = f"Duplicate Face Detected! Matches {match_emp} (Distance: {match_dist:.3f}). Encoding NOT saved."
            frappe.log_error(msg, "Employee Face Duplicate")
            frappe.db.add_comment("Employee Face", doc_name, f"❌ {msg}")
            # Do NOT save encoding
            return

        encoding_str = json.dumps(encoding_list)

        # 4) Update DB
        frappe.db.set_value("Employee Face", doc_name, "encoding", encoding_str)
        
        # 5) FIX File Attachment
        files = frappe.get_all("File", filters={"file_url": file_url}, fields=["name", "attached_to_name"])
        for f in files:
            if f.attached_to_name != doc_name:
                frappe.db.set_value("File", f.name, {
                    "attached_to_doctype": "Employee Face",
                    "attached_to_name": doc_name,
                    "is_private": 0
                })
        
        frappe.db.commit()
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Employee Face Job Error: {doc_name}")
