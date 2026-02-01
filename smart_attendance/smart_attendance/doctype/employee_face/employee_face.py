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
    def after_insert(self):
        # 1) Validate Image
        if not self.face_image:
            frappe.throw("Please upload Face Image before saving.")

        # 2) Enqueue the heavy lifting
        frappe.enqueue(
            "smart_attendance.smart_attendance.doctype.employee_face.employee_face.process_face_encoding",
            queue="long",
            timeout=1500,
            doc_name=self.name,
            file_url=self.face_image
        )
        
        frappe.msgprint("Face Analysis queued in background. Please wait a few moments for encoding to complete.")

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
            frappe.db.set_value("Employee Face", doc_name, "status", "Failed") # If you had a status field
            frappe.log_error("DeepFace not installed", "Employee Face Error")
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
        embedding_objs = DeepFace.represent(
            img_path=file_path,
            model_name="VGG-Face",
            enforce_detection=True,
            detector_backend="opencv"
        )

        if not embedding_objs:
             frappe.log_error(f"No face detected for {doc_name}", "Employee Face Job")
             # Optionally update doc to indicate failure?
             return

        vector = embedding_objs[0]["embedding"]
        encoding_str = json.dumps(vector)

        # 3) Update DB
        frappe.db.set_value("Employee Face", doc_name, "encoding", encoding_str)
        
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
