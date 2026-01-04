import frappe
from frappe.model.document import Document
from frappe.utils import get_site_path

import face_recognition
from PIL import Image
import numpy as np
import io
import os


class EmployeeFace(Document):
    def after_insert(self):
        # 0) Debug: log that hook actually ran
        frappe.log_error(
            title="EmployeeFace.after_insert",
            message=f"Running after_insert for {self.name}, image={self.face_image}",
        )

        # 1) Agar image hi nahi di, kuch mat karo
        if not self.face_image:
            frappe.throw("Please upload Face Image before saving.")

        # 2) Full file path banao: /home/.../sites/site1.com/private/files/...
        file_path = os.path.join(get_site_path(), self.face_image.lstrip("/"))

        if not os.path.exists(file_path):
            frappe.throw(f"Face image file not found: {file_path}")

        try:
            # 3) PIL se image open karo (PNG / JPG / WebP sab chalega)
            pil_image = Image.open(file_path)

            # 4) Har format ko force RGB 8bit me convert
            pil_image = pil_image.convert("RGB")

            # 5) Optional: In-memory JPEG (face_recognition ko 100% pasand)
            buffer = io.BytesIO()
            pil_image.save(buffer, format="JPEG")
            buffer.seek(0)

            # 6) face_recognition se load
            image = face_recognition.load_image_file(buffer)

            # 7) Safety: numpy array ko uint8 + contiguous bana do
            image = np.asarray(image, dtype=np.uint8)
            image = np.ascontiguousarray(image)

            # 8) Encoding nikaalo
            encodings = face_recognition.face_encodings(image)

            if not encodings:
                frappe.throw("No face detected in the uploaded image.")

            vector = encodings[0]  # first face
            encoding_str = ",".join(map(str, vector))

            # 9) Encoding field me store karo (Long Text / Text field: 'encoding')
            self.db_set("encoding", encoding_str, update_modified=False)

            frappe.log_error(
                title="EmployeeFace.after_insert SUCCESS",
                message=f"{self.name}: encoding length={len(vector)}",
            )

        except RuntimeError as e:
            # dlib / face_recognition specific runtime errors
            frappe.log_error(
                title="EmployeeFace.after_insert RuntimeError",
                message=frappe.get_traceback(),
            )
            frappe.throw(f"Error processing image: {e}")

        except Exception as e:
            # koi bhi unexpected error
            frappe.log_error(
                title="EmployeeFace.after_insert ERROR",
                message=frappe.get_traceback(),
            )
            frappe.throw(f"Unexpected error while processing image: {e}")
