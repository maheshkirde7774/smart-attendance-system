import os
import json

QR_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static', 'qrcodes')
os.makedirs(QR_DIR, exist_ok=True)

def generate_student_qr(student_id, student_name=None, roll_no=None):
    """
    Generates a unique QR code for the given student.
    Contains the student_id string so any scanner can immediately read it.
    Saves to static/qrcodes/qr_{student_id}.png and returns filename.
    """
    filename = f"qr_{student_id}.png"
    filepath = os.path.join(QR_DIR, filename)

    try:
        import qrcode
        from PIL import Image, ImageDraw

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=3,
        )
        
        # QR Data payload: Student ID
        qr.add_data(student_id)
        qr.make(fit=True)

        # Generate image with high-contrast styling (black modules on clean white with optional red accent marker)
        img = qr.make_image(fill_color="#0d0f14", back_color="#ffffff").convert('RGBA')

        # Add red border or styling if desired
        img.save(filepath)
        return filename
    except Exception as e:
        print(f"Error generating QR with qrcode library: {e}")
        # Fallback: create a placeholder image using Pillow if qrcode package isn't ready
        try:
            from PIL import Image, ImageDraw, ImageFont
            img = Image.new('RGB', (300, 300), color=(18, 20, 26))
            draw = ImageDraw.Draw(img)
            draw.rectangle([10, 10, 290, 290], outline=(229, 9, 20), width=3)
            draw.text((30, 130), f"QR CODE\n{student_id}", fill=(255, 255, 255))
            img.save(filepath)
            return filename
        except Exception as e2:
            print(f"Fallback QR creation error: {e2}")
            return None

def verify_qr_data(qr_data_str):
    """
    Parses QR content which could be pure student_id or JSON payload.
    Returns cleaned student_id.
    """
    if not qr_data_str:
        return None
    qr_data_str = qr_data_str.strip()
    try:
        data = json.loads(qr_data_str)
        if isinstance(data, dict) and "student_id" in data:
            return data["student_id"]
    except Exception:
        pass
    return qr_data_str
