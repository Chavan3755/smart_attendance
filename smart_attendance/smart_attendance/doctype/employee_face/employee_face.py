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
        # 0) Debug: log that hook actually ran
        frappe.log_error(
            title="EmployeeFace.after_insert",
            message=f"Running after_insert for {self.name}, image={self.face_image}",
        )

        if not DeepFace:
             frappe.throw("DeepFace library not installed. Cannot generate face encoding.")

        # 1) Validate Image
        if not self.face_image:
            frappe.throw("Please upload Face Image before saving.")

        # 2) Full file path
        # handle /private/files and /files
        file_url = self.face_image
        if file_url.startswith("/private/files/"):
            file_path = get_site_path("private", "files", file_url.replace("/private/files/", ""))
        elif file_url.startswith("/files/"):
            file_path = get_site_path("public", "files", file_url.replace("/files/", ""))
        else:
            file_path = os.path.join(get_site_path(), file_url.lstrip("/"))

        if not os.path.exists(file_path):
            frappe.throw(f"Face image file not found: {file_path}")

        try:
            # 3) Generate Encoding using DeepFace (VGG-Face)
            # This matches face_verification.py methodology
            embedding_objs = DeepFace.represent(
                img_path=file_path,
                model_name="VGG-Face",
                enforce_detection=True,
                detector_backend="opencv"
            )

            if not embedding_objs:
                frappe.throw("No face detected in the uploaded image.")

            # Get first face
            vector = embedding_objs[0]["embedding"]
            
            # 4) Store as JSON String
            encoding_str = json.dumps(vector)

            # 5) Save to DB
            self.db_set("encoding", encoding_str, update_modified=False)

            # 6) FIX: Ensure File is attached to this Document (not new-employee-face-...)
            if self.face_image:
                 files = frappe.get_all(
                    "File", 
                    filters={"file_url": self.face_image}, 
                    fields=["name", "attached_to_name"]
                 )
                 for f in files:
                     if f.attached_to_name != self.name:
                         frappe.db.set_value("File", f.name, {
                             "attached_to_doctype": "Employee Face",
                             "attached_to_name": self.name,
                             "is_private": 0
                         })

            frappe.log_error(
                title="EmployeeFace Encoding Encoded",
                message=f"{self.name}: Vector generated (len={len(vector)})",
            )

        except ValueError as e:
             # DeepFace raises ValueError if no face detected (if enforce_detection=True)
             frappe.throw("No face detected in the image (DeepFace Analysis).")

        except Exception as e:
            # koi bhi unexpected error
            frappe.log_error(
                title="EmployeeFace.after_insert ERROR",
                message=frappe.get_traceback(),
            )
            frappe.throw(f"Error processing face image: {str(e)}")
