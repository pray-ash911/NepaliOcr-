import os
from pathlib import Path

# Base Directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Storage Paths
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "outputs"
SAMPLE_DIR = BASE_DIR / "sample_docs"

# Create directories if they don't exist
for path in [DATA_DIR, UPLOAD_DIR, OUTPUT_DIR, SAMPLE_DIR]:
    path.mkdir(parents=True, exist_ok=True)

# OCR Configuration
DEFAULT_LANGUAGES = ["ne", "hi"]  # Nepali and Hindi (Devanagari scripts)
MAX_FILE_SIZE_MB = 25
ALLOWED_EXTENSIONS = {".pdf"}

# API Config
API_TITLE = "Automated Devanagari/Nepali PDF OCR API"
API_VERSION = "1.0.0"
API_HOST = "127.0.0.1"
API_PORT = 8000
STREAMLIT_PORT = 8501

# Updated log configurations

# Updated log configuration
