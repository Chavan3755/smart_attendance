import frappe
from frappe.model.document import Document
from frappe.utils import get_site_path
import os
import json

# Try importing DeepFace
try:
    from deepface import DeepFace
except ImportError:
    DeepFace = None

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
            if old_doc and old_doc.face_image == self.face_image and self.face_encoding:
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
    2. DeepFace.represent()
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
            from deepface import DeepFace
        except ImportError:
             # Try falling back to face_recognition if DeepFace is missing (as used in api.py)
            try:
                import face_recognition
                # ... implement fallback or just error
            except:
                pass
            
            frappe.log_error("DeepFace/face_recognition not installed", "Employee Face Error")
            # return

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
        # Check which library to use. `api.py` uses `face_recognition`.
        # `employee_face.py` was using `DeepFace`.
        # The user's other code suggests `face_recognition` is the standard.
        # Let's use `face_recognition` to be consistent with `api.py` and prevent mismatches.
        
        encoding_list = []
        try:
            import face_recognition
            from PIL import Image
            import numpy as np
            
            img = Image.open(file_path).convert('RGB')
            arr = np.array(img)
            encs = face_recognition.face_encodings(arr)
            if encs:
                encoding_list = encs[0].tolist()
        except ImportError:
             # Fallback to logic if DeepFace was intended, but let's stick to one.
             pass

        if not encoding_list:
             frappe.log_error(f"No face detected for {doc_name}", "Employee Face Job")
             return

        encoding_str = json.dumps(encoding_list)

        # 3) Update DB
        frappe.db.set_value("Employee Face", doc_name, "face_encoding", encoding_str)
        
        # 4) FIX File Attachment
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
