from schemas.document.document_checker import SDocumentChecker
from pypdf import PdfReader
from pdf2image import convert_from_bytes
from PIL import Image, ImageChops, ImageEnhance
import base64
import io
from helpers.logging import logging
from typing import Optional
import pytesseract
import numpy as np

class DocumentController:

    @classmethod
    async def document_checker(cls, params: SDocumentChecker) -> tuple[bool, list[dict], str]:
        try:
            if not params.file or not params.file.filename:
                return False, [], "File has no name"

            filename = params.file.filename.lower()

            if filename.endswith(".pdf"):
                result_pdf = await cls.detect_manipulation_pdf(params)
                return True, [{"pdf_analysis": result_pdf}], "success"

            else:
                result_ela = await cls.detect_manipulation_ela(params)
                return True, [{"image_analysis": result_ela}], "success"
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
        
    @classmethod
    async def detect_manipulation_pdf(cls, params: SDocumentChecker) -> Optional[dict]:
        try:
            pdf_bytes = await params.file.read()
            reader = PdfReader(io.BytesIO(pdf_bytes))

            # ---------------------------------------------------------
            # 1. Extract metadata
            # ---------------------------------------------------------
            metadata = reader.metadata or {}
            clean_meta = {k.replace("/", ""): str(v) for k, v in metadata.items()}

            producer = (metadata.get("/Producer") or "").lower()
            creator = (metadata.get("/Creator") or "").lower()

            DIGITAL_IMAGE_PRODUCERS = [
                "mpdf", "wkhtml", "wkhtmltopdf", "itext", "weasyprint",
                "aspose", "tcpdf", "libreoffice", "reportlab", "samsung", 
                "xerox", "canon", "epson", "hp", "mfp", "scanner"
            ]

            is_digital_image_pdf = any(p in producer for p in DIGITAL_IMAGE_PRODUCERS)

            # flag metadata
            metadata_flags = []

            if not metadata:
                metadata_flags.append("metadata_missing")

            if not is_digital_image_pdf:
                if producer and "adobe" not in producer.lower():
                    metadata_flags.append("unusual_producer")

            # ---------------------------------------------------------
            # 2. Determine PDF Type
            # ---------------------------------------------------------
            first_page = reader.pages[0]
            resources = first_page.get("/Resources", {})
            xobjects = resources.get("/XObject", {})

            # scan PDF has XObject images
            is_scanned_pdf = any(
                obj.get("/Subtype") == "/Image" for obj in xobjects.values()
            )

            # ---------------------------------------------------------
            # 3. DIGITAL-IMAGE PDF (Talenta, BPJS, etc)
            # ---------------------------------------------------------
            if is_digital_image_pdf:
                digital_flags = []

                # annotate?
                if "/Annots" in first_page:
                    digital_flags.append("annotations_detected")

                # multi-layer object?
                if len(xobjects) > 3:
                    digital_flags.append("multiple_layers_detected")

                risk_score = 10 * len(metadata_flags) + 10 * len(digital_flags)

                return {
                    "file_name": params.file.filename,
                    "pdf_type": "digital_image_pdf",
                    "is_encrypted": reader.is_encrypted,
                    "metadata": clean_meta,
                    "metadata_flags": metadata_flags,
                    "digital_edit_flags": digital_flags,
                    "risk_score": risk_score,
                    "status": "digital_document_original" if risk_score < 25 else "digital_document_possibly_modified"
                }

            # ---------------------------------------------------------
            # 4. SCANNED PDF (physical document)
            # ---------------------------------------------------------
            if is_scanned_pdf:
                images = convert_from_bytes(pdf_bytes, dpi=200)
                img = images[0]

                ocr_info = cls.ocr_consistency_check(img)
                stamp_info = cls.detect_stamp_signature(img)
                variance_info = cls.pixel_block_variance(img)

                anomalies = []

                # DPI check
                dpi = img.info.get("dpi", (0, 0))
                if dpi[0] < 150 or dpi[1] < 150:
                    anomalies.append("low_dpi_scan")

                # annotation
                if "/Annots" in first_page:
                    anomalies.append("annotations_present")

                risk_score = (
                    10 * len(metadata_flags) +
                    (20 if ocr_info.get("ocr_status") == "possible_text_edit" else 0) +
                    (15 if stamp_info["stamp_likelihood"] == "stamp_detected" else 0) +
                    (15 if variance_info["block_status"] == "possible_pasted_element" else 0) +
                    10 * len(anomalies)
                )

                return {
                    "file_name": params.file.filename,
                    "pdf_type": "scanned_pdf",
                    "is_encrypted": reader.is_encrypted,
                    "metadata": clean_meta,
                    "metadata_flags": metadata_flags,
                    "scan_anomalies": anomalies,
                    "advanced_ocr_check": ocr_info,
                    "stamp_detection": stamp_info,
                    "pixel_variance": variance_info,
                    "risk_score": risk_score,
                    "status": "scanned_document_original" if risk_score < 35 else "scanned_document_possibly_modified"
                }

            # ---------------------------------------------------------
            # 5. Default: pure digital PDF
            # ---------------------------------------------------------
            digital_flags = []

            if "/Annots" in first_page:
                digital_flags.append("annotations_detected")

            if len(xobjects) > 5:
                digital_flags.append("multiple_layers_detected")

            risk_score = 10 * len(metadata_flags) + 10 * len(digital_flags)

            return {
                "file_name": params.file.filename,
                "pdf_type": "digital_pdf",
                "is_encrypted": reader.is_encrypted,
                "metadata": clean_meta,
                "metadata_flags": metadata_flags,
                "digital_edit_flags": digital_flags,
                "risk_score": risk_score,
                "status": "digital_document_original" if risk_score < 25 else "digital_document_possibly_modified"
            }

        except Exception as e:
            logging.log_error({
                "module": __name__,
                "function": "detect_manipulation_pdf",
                "error": str(e)
            })
            return None
        
    # @classmethod
    # async def detect_manipulation_pdf(cls, params: SDocumentChecker) -> Optional[dict]:
    #     try:
    #         pdf_bytes = await params.file.read()
    #         reader = PdfReader(io.BytesIO(pdf_bytes))

    #         # ---------------------------------------------------------
    #         # 1. METADATA
    #         # ---------------------------------------------------------
    #         metadata = reader.metadata or {}
    #         clean_meta = {k.replace("/", ""): str(v) for k, v in metadata.items()}

    #         suspicious_meta = []

    #         if not metadata:
    #             suspicious_meta.append("metadata_missing")

    #         scanner_keywords = ["samsung", "xerox", "canon", "epson", "hp", "mfp", "scanner"]

    #         def is_scanner_device(value: str):
    #             return any(k in value.lower() for k in scanner_keywords)

    #         # Validate metadata only if PDF is DIGITAL
    #         if "/Producer" in metadata:
    #             producer = metadata["/Producer"]
    #             if not is_scanner_device(producer) and "adobe" not in producer.lower():
    #                 suspicious_meta.append("unusual_producer")

    #         if "/Creator" in metadata:
    #             creator = metadata["/Creator"]
    #             if not is_scanner_device(creator) and "adobe" not in creator.lower():
    #                 suspicious_meta.append("unusual_creator")

    #         # ---------------------------------------------------------
    #         # 2. DETEKSI SCANNED PDF (sangat akurat)
    #         # ---------------------------------------------------------
    #         first_page = reader.pages[0]

    #         try:
    #             resources = first_page.get("/Resources", {})
    #             xobjects = resources.get("/XObject", {})
    #             is_scanned = any(obj.get("/Subtype") == "/Image" for obj in xobjects.values())
    #         except Exception:
    #             is_scanned = False

    #         # ---------------------------------------------------------
    #         # 3. PDF SCAN: DETEKSI TANDA EDIT → tanpa ELA
    #         # ---------------------------------------------------------
    #         anomalies = []

    #         if is_scanned:
    #             # cek DPI image
    #             try:
    #                 images = convert_from_bytes(pdf_bytes, dpi=200)
    #                 img = images[0]

    #                 ocr_info = cls.ocr_consistency_check(img)
    #                 stamp_info = cls.detect_stamp_signature(img)
    #                 variance_info = cls.pixel_block_variance(img)

    #                 dpi = img.info.get("dpi", (0, 0))
    #                 if dpi[0] < 150 or dpi[1] < 150:
    #                     anomalies.append("low_dpi_scan (possible whatsapp compression)")

    #             except Exception:
    #                 anomalies.append("conversion_failed")

    #             # cek annotation / form field
    #             if "/Annots" in first_page:
    #                 anomalies.append("annotations_present (可能编辑)")

    #             status, risk_score = cls.calculate_pdf_risk(
    #                 anomalies,
    #                 ocr_info,
    #                 stamp_info,
    #                 variance_info,
    #                 suspicious_meta
    #             )

    #             return {
    #                 "file_name": params.file.filename,
    #                 "is_scanned_pdf": True,
    #                 "is_encrypted": reader.is_encrypted,
    #                 "metadata": clean_meta,
    #                 "metadata_flags": suspicious_meta,
    #                 "scan_anomalies": anomalies,
    #                 "advanced_ocr_check": ocr_info,
    #                 "stamp_detection": stamp_info,
    #                 "pixel_variance": variance_info,
    #                 "risk_score": risk_score,
    #                 "status": status
    #             }

    #         # ---------------------------------------------------------
    #         # 4. PDF DIGITAL (non-scan) → DETEKSI EDIT SIAPA
    #         # ---------------------------------------------------------
    #         digital_flags = []

    #         # annotation = tanda dokumen ini pernah diedit (highlight, stamp, textbox)
    #         if "/Annots" in first_page:
    #             digital_flags.append("annotations_detected")

    #         # object terlalu banyak → typical hasil editing
    #         object_count = len(first_page.get("/Resources", {}).get("/XObject", {}))
    #         if object_count > 5:
    #             digital_flags.append("multiple_layers_detected (may_be_edited)")

    #         return {
    #             "file_name": params.file.filename,
    #             "is_scanned_pdf": False,
    #             "is_encrypted": reader.is_encrypted,
    #             "metadata": clean_meta,
    #             "metadata_flags": suspicious_meta,
    #             "digital_edit_flags": digital_flags,
    #             "status": (
    #                 "likely_original"
    #                 if not digital_flags and not suspicious_meta
    #                 else "possibly_edited"
    #             )
    #         }

    #     except Exception as e:
    #         logging.log_error({
    #             "module": __name__,
    #             "function": "detect_manipulation_pdf",
    #             "error": "Error PDF check",
    #             "detail": str(e)
    #         })
    #         return None

    @staticmethod
    def ocr_consistency_check(image: Image.Image) -> dict:
        """Check OCR uniformity to detect edited text in scanned PDF."""
        try:
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)

            # Ambil jarak antar bounding box
            boxes = []
            for i in range(len(data['text'])):
                if data['text'][i].strip() != "":
                    x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                    boxes.append((x, y, w, h))

            if len(boxes) < 5:
                return {"ocr_status": "insufficient_text"}

            heights = [b[3] for b in boxes]  # list height teks

            std_height = float(np.std(heights))

            return {
                "ocr_text_count": len(boxes),
                "ocr_height_var": round(std_height, 2),
                "ocr_status": (
                    "uniform_text"
                    if std_height < 3 else
                    "possible_text_edit"
                )
            }
        except Exception as e:
            return {"ocr_status": "ocr_failed", "detail": str(e)}  
        
    @staticmethod
    def detect_stamp_signature(image: Image.Image) -> dict:
        img_np = np.array(image)

        # Konversi ke grayscale
        gray = img_np[:, :, 0] * 0.299 + img_np[:, :, 1] * 0.587 + img_np[:, :, 2] * 0.114

        # Cek spot tinta kuat (threshold)
        ink_spots = (gray < 100).astype(np.uint8).sum()

        # Ratio tinta
        ink_ratio = round((ink_spots / gray.size) * 100, 2)

        return {
            "ink_ratio": ink_ratio,
            "stamp_likelihood": (
                "stamp_detected" if ink_ratio > 1.5 else "no_stamp_detected"
            )
        }
    
    @staticmethod
    def pixel_block_variance(image: Image.Image) -> dict:
        img = image.convert("L")
        pixels = np.array(img)

        h, w = pixels.shape
        block_size = 50

        variances = []

        for i in range(0, h, block_size):
            for j in range(0, w, block_size):
                block = pixels[i:i + block_size, j:j + block_size]
                variances.append(np.var(block))

        avg_var = round(float(np.mean(variances)), 2)

        return {
            "block_variance": avg_var,
            "block_status": (
                "uniform_document"
                if avg_var < 300 else
                "possible_pasted_element"
            )
        }
    
    @staticmethod
    def calculate_pdf_risk(
        anomalies: list,
        ocr_info: dict,
        stamp_info: dict,
        variance_info: dict,
        metadata_flags: list
    ) -> tuple[str, int]:
        score = 0

        # 1. Anomalies sangat signifikan
        score += len(anomalies) * 20

        # 2. OCR text height variance
        if ocr_info.get("ocr_status") == "possible_text_edit":
            score += 25
        elif ocr_info.get("ocr_status") == "insufficient_text":
            score += 10

        # 3. Stamp detection
        if stamp_info.get("stamp_likelihood") == "stamp_detected":
            score -= 10  # dokumen resmi biasanya punya stamp
        else:
            score += 5   # no stamp pada dokumen scan sering mencurigakan

        # 4. Pixel variance (paste element?)
        if variance_info.get("block_status") == "possible_pasted_element":
            score += 30

        # 5. Metadata flags
        score += len(metadata_flags) * 10

        # -------------------------------
        # Final Classification
        # -------------------------------
        if score < 20:
            status = "scanned_document_original"
        elif 20 <= score < 50:
            status = "scanned_document_suspicious"
        else:
            status = "scanned_document_possibly_modified"

        return status, score
    
    # @staticmethod
    # async def detect_manipulation_pdf(params: SDocumentChecker) -> Optional[dict]:
        # try:
        #     pdf_bytes = await params.file.read()
        #     reader = PdfReader(io.BytesIO(pdf_bytes))

        #     # ---- 1. Metadata ----
        #     metadata = reader.metadata or {}
        #     clean_meta = {k.replace("/", ""): str(v) for k, v in metadata.items()}

        #     suspicious_meta = []
        #     if not metadata:
        #         suspicious_meta.append("no_metadata")
        #     if "/Producer" in metadata and "Adobe" not in metadata["/Producer"]:
        #         suspicious_meta.append("non_standard_producer")
        #     if "/Creator" in metadata and "Adobe" not in metadata["/Creator"]:
        #         suspicious_meta.append("non_standard_creator")

        #     # ---- 2. Cek apakah PDF hasil scan ----
        #     first_page = reader.pages[0]
        #     # is_scanned = "/XObject" in str(first_page.resources)
        #     try:
        #         resources = first_page.get("/Resources", {})
        #         xobjects = resources.get("/XObject", {})
        #         is_scanned = len(xobjects) > 0
        #     except Exception:
        #         is_scanned = False

        #     # ---- 3. Convert page → image (ELA pada PDF) ----
        #     images = convert_from_bytes(pdf_bytes, dpi=200)
        #     img = images[0].convert("RGB")
        #     img = img.resize((800, 800), Image.Resampling.LANCZOS)

        #     temp = io.BytesIO()
        #     img.save(temp, "JPEG", quality=75)
        #     temp_img = Image.open(io.BytesIO(temp.getvalue()))

        #     diff = ImageChops.difference(img, temp_img)
        #     diff_enhanced = ImageEnhance.Brightness(diff).enhance(30)

        #     diff_gray = diff_enhanced.convert("L")
        #     pixels = list(diff_gray.getdata())
        #     avg_diff = round(sum(pixels) / len(pixels), 2)

        #     status_text = (
        #         "likely original" if avg_diff < 8 else
        #         "possibly fake" if avg_diff < 20 else
        #         "likely fake"
        #     )

        #     # ---- 4. Encryption ----
        #     encrypted = reader.is_encrypted

        #     return {
        #         "file_name": params.file.filename,
        #         "is_scanned_pdf": is_scanned,
        #         "is_encrypted": encrypted,
        #         "metadata": clean_meta,
        #         "metadata_flags": suspicious_meta,
        #         "manipulation_score": avg_diff,
        #         "status": status_text
        #     }

        # except Exception as e:
        #     logging.log_error({
        #         "module": __name__,
        #         "function": "detect_manipulation_pdf",
        #         "error": "Error PDF check",
        #         "detail": str(e)
        #     })
        #     return None

