from schemas.document.document_checker import SDocumentChecker
from PyPDF2 import PdfReader
from pdf2image import convert_from_bytes
from PIL import Image, ImageChops, ImageEnhance
import base64
import io
from helpers.logging import logging
from typing import Optional

class DocumentController:

    @classmethod
    async def document_checker(cls, params: SDocumentChecker) -> tuple[bool, list[dict], str]:
        try:
            result_ela = await cls.detect_manipulation_ela(params)
            # result_pdf = await cls.detect_manipulation_pdf(params)
            output = [
                {
                    "ela": result_ela
                }
            ]
            return True, output, "Success"
        except Exception as e:
            logging.log_error({
                "module": __name__,
                "function": "document_checker", 
                "error": "Error fetching document", 
                "detail": str(e)
            })
            return False, [], f"Error fetching document: {str(e)}"
    @staticmethod
    async def detect_manipulation_ela(params: SDocumentChecker) -> Optional[dict]:
        try:
            # Baca file
            image_bytes = await params.file.read()
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

            # Normalisasi ukuran supaya analisa konsisten
            image = image.resize((800, 800), Image.Resampling.LANCZOS)

            # Simpan ulang dengan kompresi rendah
            temp = io.BytesIO()
            image.save(temp, "JPEG", quality=75)  # lebih sensitif
            temp_image = Image.open(temp)

            # Hitung difference (ELA raw image)
            diff = ImageChops.difference(image, temp_image)

            # Perkuat difference agar terlihat
            diff_enhanced = ImageEnhance.Brightness(diff).enhance(30)

            # Hitung skor manipulasi dari tiap pixel
            diff_gray = diff_enhanced.convert("L")
            pixels = list(diff_gray.getdata())

            avg_diff = sum(pixels) / len(pixels)   # rata-rata intensitas noise
            score = round(avg_diff, 2)

            # Convert heatmap ke base64
            buffer = io.BytesIO()
            diff_enhanced.save(buffer, format="JPEG")
            heatmap_base64 = base64.b64encode(buffer.getvalue()).decode()

            # Tentukan status
            status_text = (
                "likely original" if score < 10 else
                "possibly fake" if score < 25 else
                "likely fake"
            )

            result = {
                "file_name": params.file.filename,
                "manipulation_score": score,
                "status": status_text,
                # "ela_heatmap": heatmap_base64
            }
            return result
        except Exception as e:
            logging.log_error({
                "module": __name__,
                "function": "document_checker", 
                "error": "Error during document checker", 
                "detail": str(e)
            })
            return None
        

