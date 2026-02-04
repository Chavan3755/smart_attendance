import frappe 
@frappe.whitelist(allow_guest=True)
def get_kiosk_settings():
    s = frappe.get_single("Smart Attendance Settings")

    return {
        "settings": {
            "theme": {
                "aurora_a": s.aurora_a_color,
                "aurora_b": s.aurora_b_color,
                "button_a": s.button_color_a,
                "button_b": s.button_color_b,
            },
            "features": {
                "sound": int(s.enable_sound or 0),
                "vibration": int(s.enable_vibration or 0),
                # "show_face_percentage": int(s.show_face_percentage or 0),
            },
            "advanced": {
                # "face_detection_model": s.face_detection_model,
                "cdn_url": s.cdn_url,
                "colour_mode": int(s.colour_mode or 0),
            }
        }
    }
