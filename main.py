import sys
import subprocess
from app.config import API_HOST, API_PORT, STREAMLIT_PORT


def print_banner():
    print("=" * 60)
    print(" 🇳🇵 Nepali & Devanagari Automated PDF OCR & Text Extractor ")
    print("=" * 60)


def start_api():
    print_banner()
    print(f"🚀 Starting FastAPI Server on http://{API_HOST}:{API_PORT} ...")
    print(f"📖 Swagger API Docs available at http://{API_HOST}:{API_PORT}/docs")
    subprocess.run([
        sys.executable, "-m", "uvicorn", "app.api:app",
        "--host", API_HOST, "--port", str(API_PORT), "--reload"
    ])


def start_ui():
    print_banner()
    print(f"🎨 Starting Streamlit UI on http://localhost:{STREAMLIT_PORT} ...")
    subprocess.run([
        sys.executable, "-m", "streamlit", "run", "app/ui.py",
        "--server.port", str(STREAMLIT_PORT)
    ])


def generate_sample():
    from sample_docs.generate_sample_nepali_pdf import generate_sample_pdf
    generate_sample_pdf()


def run_tests():
    subprocess.run([sys.executable, "-m", "unittest", "discover", "tests"])


if __name__ == "__main__":
    arg = sys.argv[1].lower() if len(sys.argv) > 1 else "help"
    
    if arg in ["api", "server"]:
        start_api()
    elif arg in ["ui", "streamlit"]:
        start_ui()
    elif arg in ["sample", "pdf"]:
        generate_sample()
    elif arg == "test":
        run_tests()
    else:
        print_banner()
        print("Usage:")
        print("  python main.py api      -> Start FastAPI Web Endpoint (/extract-pdf)")
        print("  python main.py ui       -> Start Streamlit UI (PDF Preview + Markdown)")
        print("  python main.py sample   -> Generate sample Nepali PDF in sample_docs/")
        print("  python main.py test     -> Run test suite")
