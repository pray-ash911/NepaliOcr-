import os
import tempfile
import httpx
import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
from app.config import API_HOST, API_PORT
from app.ocr_engine import ocr_engine
from app.postprocessor import post_processor

st.set_page_config(page_title="Nepali Devanagari PDF OCR", page_icon="🇳🇵", layout="wide")
st.title("🇳🇵 Automated PDF Devanagari/Nepali Text Extractor")

# Sidebar Configuration
st.sidebar.header("⚙️ OCR and Processing Options")
execution_mode = st.sidebar.radio("Processing Backend Mode", ["Direct Engine", "FastAPI HTTP Endpoint (/extract-pdf)"])
engine_choice = st.sidebar.selectbox("OCR Engine", ["auto", "easyocr", "surya", "native"], index=0)
fix_ligatures = st.sidebar.checkbox("Repair Devanagari Ligatures", value=True)
strip_noise = st.sidebar.checkbox("Strip OCR Noise & Artifacts", value=True)

uploaded_file = st.sidebar.file_uploader("Upload Devanagari PDF Document", type=["pdf"])

if uploaded_file:
    col1, col2 = st.columns([1, 1])

    # Save temp file for processing
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        uploaded_bytes = uploaded_file.read()
        tmp_file.write(uploaded_bytes)
        tmp_path = tmp_file.name

    # Left Column: PDF Preview
    with col1:
        st.subheader("📄 PDF Document Preview")
        doc = fitz.open(tmp_path)
        page_num = st.number_input("Page Selector", min_value=1, max_value=len(doc), value=1)
        pix = doc[page_num - 1].get_pixmap(dpi=150)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        st.image(img, caption=f"Page {page_num} of {len(doc)}", use_container_width=True)
        doc.close()

    # Right Column: Extracted Devanagari Markdown Output
    with col2:
        st.subheader("📝 Rendered Devanagari Markdown")
        if st.button("🚀 Extract & Post-Process PDF", type="primary"):
            with st.spinner("Processing PDF with OCR & Ligature Repair..."):
                if execution_mode == "FastAPI HTTP Endpoint (/extract-pdf)":
                    api_url = f"http://{API_HOST}:{API_PORT}/extract-pdf"
                    try:
                        files = {"file": (uploaded_file.name, uploaded_bytes, "application/pdf")}
                        params = {
                            "engine": engine_choice,
                            "fix_ligatures": str(fix_ligatures).lower(),
                            "strip_noise": str(strip_noise).lower()
                        }
                        response = httpx.post(api_url, files=files, params=params, timeout=120.0)
                        if response.status_code == 200:
                            data = response.json()
                            markdown_content = data["markdown_content"]
                            raw_text = data["raw_text"]
                            stats = data["stats"]
                            st.success(f"FastAPI Extracted in {data['elapsed_seconds']}s using {data['engine_used']}!")
                        else:
                            st.error(f"FastAPI Error ({response.status_code}): {response.text}")
                            markdown_content, raw_text, stats = "", "", {}
                    except Exception as e:
                        st.error(f"Could not connect to FastAPI server at {api_url}. Is FastAPI running? Exception: {e}")
                        markdown_content, raw_text, stats = "", "", {}
                else: # Direct Engine
                    res = ocr_engine.extract_text_from_pdf(tmp_path, engine=engine_choice)
                    processed = post_processor.process_text(res["raw_combined_text"], fix_ligatures=fix_ligatures, strip_noise=strip_noise)
                    markdown_content = processed["markdown"]
                    raw_text = res["raw_combined_text"]
                    stats = processed["stats"]
                    st.success(f"Extracted in {res['elapsed_seconds']}s using {res['engine_used']}!")

                if markdown_content:
                    # Rendered Markdown tab & Raw Text tab
                    tab1, tab2, tab3 = st.tabs(["Formatted Markdown", "Raw Extracted Text", "Extraction Stats"])
                    with tab1:
                        st.markdown(markdown_content)
                    with tab2:
                        st.text_area("Raw OCR Text", raw_text, height=350)
                    with tab3:
                        st.json(stats)

                    st.download_button(
                        label="📥 Download Markdown (.md)",
                        data=markdown_content,
                        file_name=f"extracted_{uploaded_file.name}.md",
                        mime="text/markdown"
                    )

    # Cleanup temp file on process end
    try:
        os.remove(tmp_path)
    except Exception:
        pass
else:
    st.info("👈 Please upload a PDF document in the sidebar to begin extraction.")
