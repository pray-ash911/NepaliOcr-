import os
import shutil
import uuid
from typing import Optional
from fastapi import FastAPI, File, UploadFile, Query, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.config import (
    API_TITLE, API_VERSION, UPLOAD_DIR, OUTPUT_DIR,
    MAX_FILE_SIZE_MB, ALLOWED_EXTENSIONS
)
from app.ocr_engine import ocr_engine
from app.postprocessor import post_processor

app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    description="Automated PDF Devanagari/Nepali Text Extractor & Post-Processing API"
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    """API Index and Health check."""
    return {
        "status": "online",
        "service": API_TITLE,
        "version": API_VERSION,
        "endpoints": {
            "extract_pdf": "POST /extract-pdf",
            "download_markdown": "GET /download/{filename}",
            "health": "GET /health"
        }
    }


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


def cleanup_temp_file(filepath: str):
    """Background task to remove temporary uploaded file."""
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
    except Exception:
        pass


@app.post("/extract-pdf")
async def extract_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="PDF file containing Devanagari/Nepali text"),
    engine: str = Query("auto", enum=["auto", "surya", "easyocr", "native"], description="OCR Engine choice"),
    fix_ligatures: bool = Query(True, description="Repair broken Devanagari ligatures"),
    strip_noise: bool = Query(True, description="Strip OCR noise and control characters"),
    dpi: int = Query(200, ge=100, le=400, description="DPI resolution for page rendering")
):
    """
    Extracts Devanagari/Nepali texts from uploaded PDFs, applies post-processing,
    and returns rendered Markdown and raw extracted data.
    """
    # 1. File Extension Validations
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file extension '{ext}'. Only PDF files (.pdf) are allowed."
        )

    # 2. Save Uploaded PDF Files
    file_id = str(uuid.uuid4())[:8]
    sanitized_filename = f"{file_id}_{os.path.basename(file.filename)}"
    upload_path = os.path.join(UPLOAD_DIR, sanitized_filename)

    try:
        with open(upload_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Check File Size
        file_size_mb = os.path.getsize(upload_path) / (1024 * 1024)
        if file_size_mb > MAX_FILE_SIZE_MB:
            os.remove(upload_path)
            raise HTTPException(
                status_code=400,
                detail=f"File size ({file_size_mb:.2f} MB) exceeds maximum limit of {MAX_FILE_SIZE_MB} MB."
            )

        # 3. Perform OCR Extraction
        ocr_result = ocr_engine.extract_text_from_pdf(
            pdf_path=upload_path,
            engine=engine,
            dpi=dpi
        )

        # 4. Perform Post-Processing
        processed_result = post_processor.process_text(
            raw_text=ocr_result["raw_combined_text"],
            fix_ligatures=fix_ligatures,
            strip_noise=strip_noise
        )

        # 5. Save Output Markdown File
        markdown_filename = f"extracted_{file_id}.md"
        markdown_path = os.path.join(OUTPUT_DIR, markdown_filename)
        with open(markdown_path, "w", encoding="utf-8") as f:
            f.write(processed_result["markdown"])

        # Schedule temp file cleanup
        background_tasks.add_task(cleanup_temp_file, upload_path)

        return JSONResponse(content={
            "success": True,
            "filename": file.filename,
            "engine_used": ocr_result["engine_used"],
            "page_count": ocr_result["page_count"],
            "elapsed_seconds": ocr_result["elapsed_seconds"],
            "markdown_filename": markdown_filename,
            "download_url": f"/download/{markdown_filename}",
            "stats": processed_result["stats"],
            "markdown_content": processed_result["markdown"],
            "raw_text": ocr_result["raw_combined_text"]
        })

    except Exception as e:
        if os.path.exists(upload_path):
            os.remove(upload_path)
        raise HTTPException(status_code=500, detail=f"OCR Processing error: {str(e)}")


@app.get("/download/{filename}")
def download_markdown(filename: str):
    """Download generated Markdown file."""
    filepath = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Requested file not found.")

    return FileResponse(
        path=filepath,
        filename=filename,
        media_type="text/markdown"
    )
