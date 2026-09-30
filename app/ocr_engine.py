import os
import io
import time
import logging
from typing import List, Dict, Any, Optional
from PIL import Image
import fitz  # PyMuPDF

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("NepaliOCREngine")


class NepaliOCREngine:
    """
    Unified Devanagari & Nepali OCR Engine with support for:
    - PyMuPDF Native Devanagari Text Extraction (Fastest for native PDFs)
    - EasyOCR Devanagari Engine (Supporting 'ne' & 'hi')
    - Surya-OCR Engine (High precision layout & multilingual OCR)
    """

    def __init__(self):
        self._easyocr_reader = None
        self._surya_models = None

    def _get_easyocr_reader(self):
        """Lazy load EasyOCR reader for Devanagari / Nepali."""
        if self._easyocr_reader is None:
            try:
                import easyocr
                logger.info("Initialize EasyOCR reader for languages: ['ne', 'hi']...")
                self._easyocr_reader = easyocr.Reader(['ne', 'hi'], gpu=False)
                logger.info("EasyOCR initialized successfully.")
            except Exception as e:
                logger.warning(f"EasyOCR initialization warning: {e}")
                self._easyocr_reader = False
        return self._easyocr_reader if self._easyocr_reader is not False else None

    def _get_surya_ocr(self):
        """Lazy load Surya-OCR model."""
        if self._surya_models is None:
            try:
                # Try Surya v0.22+ Predictor API first
                from surya.recognition import RecognitionPredictor
                logger.info("Initializing Surya-OCR (v0.22+) RecognitionPredictor...")
                rec_predictor = RecognitionPredictor()
                self._surya_models = {
                    "version": "v0.22+",
                    "predictor": rec_predictor
                }
                logger.info("Surya-OCR loaded successfully.")
            except ImportError:
                try:
                    # Fallback for legacy Surya version
                    from surya.ocr import run_ocr
                    from surya.model.detection.model import load_model as load_det_model, load_processor as load_det_processor
                    from surya.model.recognition.model import load_model as load_rec_model
                    from surya.model.recognition.processor import load_processor as load_rec_processor

                    logger.info("Initializing legacy Surya-OCR Devanagari models...")
                    det_model = load_det_model()
                    det_processor = load_det_processor()
                    rec_model = load_rec_model()
                    rec_processor = load_rec_processor()

                    self._surya_models = {
                        "version": "legacy",
                        "run_ocr": run_ocr,
                        "det_model": det_model,
                        "det_processor": det_processor,
                        "rec_model": rec_model,
                        "rec_processor": rec_processor
                    }
                    logger.info("Legacy Surya-OCR loaded successfully.")
                except Exception as e:
                    logger.warning(f"Surya-OCR initialization warning: {e}")
                    self._surya_models = False
            except Exception as e:
                logger.warning(f"Surya-OCR initialization warning: {e}")
                self._surya_models = False
        return self._surya_models if self._surya_models is not False else None

    def pdf_to_images(self, pdf_path: str, dpi: int = 200) -> List[Image.Image]:
        """Renders PDF pages into PIL Images using PyMuPDF."""
        images = []
        doc = fitz.open(pdf_path)
        zoom = dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        
        for page in doc:
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            images.append(img)
            
        doc.close()
        return images

    def extract_native_text(self, pdf_path: str) -> List[Dict[str, Any]]:
        """
        Attempts direct text extraction from PDF via PyMuPDF.
        Returns page texts if PDF contains vector text layer.
        """
        doc = fitz.open(pdf_path)
        pages_data = []
        for i, page in enumerate(doc):
            text = page.get_text("text").strip()
            pages_data.append({
                "page_num": i + 1,
                "text": text,
                "char_count": len(text)
            })
        doc.close()
        return pages_data

    def extract_easyocr(self, images: List[Image.Image]) -> List[str]:
        """Runs EasyOCR on list of PIL images."""
        reader = self._get_easyocr_reader()
        if not reader:
            raise RuntimeError("EasyOCR is not available.")

        import numpy as np
        page_texts = []

        for img in images:
            img_np = np.array(img)
            results = reader.readtext(img_np, detail=0)
            page_text = "\n".join(results)
            page_texts.append(page_text)

        return page_texts

    def extract_surya(self, images: List[Image.Image]) -> List[str]:
        """Runs Surya-OCR on list of PIL images."""
        surya = self._get_surya_ocr()
        if not surya:
            raise RuntimeError("Surya-OCR is not available.")

        if surya.get("version") == "v0.22+":
            predictor = surya["predictor"]
            predictions = predictor(images)
            page_texts = []
            for pred in predictions:
                if hasattr(pred, "text_lines"):
                    lines = [line.text for line in pred.text_lines]
                elif hasattr(pred, "ocr_results"):
                    lines = [item.text for item in pred.ocr_results]
                else:
                    lines = [str(pred)]
                page_texts.append("\n".join(lines))
            return page_texts
        else:
            run_ocr = surya["run_ocr"]
            predictions = run_ocr(
                images,
                langs=[["ne", "hi"]] * len(images),
                det_model=surya["det_model"],
                det_processor=surya["det_processor"],
                rec_model=surya["rec_model"],
                rec_processor=surya["rec_processor"]
            )

            page_texts = []
            for pred in predictions:
                lines = [line.text for line in pred.text_lines]
                page_texts.append("\n".join(lines))
            return page_texts

    def extract_text_from_pdf(
        self,
        pdf_path: str,
        engine: str = "auto",
        dpi: int = 200
    ) -> Dict[str, Any]:
        """
        Main extraction wrapper.
        Engines: 'auto', 'surya', 'easyocr', 'native'
        """
        start_time = time.time()
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        # Check native text first
        native_pages = self.extract_native_text(pdf_path)
        total_native_chars = sum(p["char_count"] for p in native_pages)

        used_engine = engine
        page_results = []

        if engine == "native" or (engine == "auto" and total_native_chars > 50):
            logger.info("Using Native PyMuPDF Text Extraction.")
            used_engine = "native"
            for page in native_pages:
                page_results.append(page["text"])
        else:
            # Scanned / Image PDF or OCR engine requested
            logger.info(f"Rendering PDF pages at {dpi} DPI for OCR...")
            images = self.pdf_to_images(pdf_path, dpi=dpi)

            if engine == "surya":
                try:
                    logger.info("Executing Surya-OCR engine...")
                    page_results = self.extract_surya(images)
                    used_engine = "surya"
                except Exception as e:
                    logger.warning(f"Surya-OCR failed ({e}), falling back to EasyOCR.")
                    page_results = self.extract_easyocr(images)
                    used_engine = "easyocr (fallback)"
            elif engine == "easyocr":
                logger.info("Executing EasyOCR engine...")
                page_results = self.extract_easyocr(images)
                used_engine = "easyocr"
            else: # 'auto' fallback
                try:
                    logger.info("Attempting EasyOCR engine...")
                    page_results = self.extract_easyocr(images)
                    used_engine = "easyocr"
                except Exception as e:
                    logger.warning(f"OCR failed ({e}). Falling back to Native text extraction.")
                    page_results = [p["text"] for p in native_pages]
                    used_engine = "native (fallback)"

        elapsed_time = round(time.time() - start_time, 2)
        raw_combined_text = "\n\n--- Page Break ---\n\n".join(page_results)

        return {
            "engine_used": used_engine,
            "page_count": len(page_results),
            "pages": page_results,
            "raw_combined_text": raw_combined_text,
            "elapsed_seconds": elapsed_time
        }


# Global instance
ocr_engine = NepaliOCREngine()

# Optimized batch size

# Optimized batch size
