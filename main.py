# main.py - NarrativaX (Production-Ready Version with Fixes)
import os
import json
import requests
import zipfile
import random
import replicate
import base64
import time
import warnings
from html import escape
from docx import Document
from docx.shared import Inches
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from tempfile import NamedTemporaryFile
from gtts import gTTS
from PIL import Image
from io import BytesIO
import streamlit as st

# Suppress warnings
warnings.filterwarnings("ignore", category=UserWarning, module="streamlit")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="fpdf")

# === INITIALIZATION ===
st.set_page_config(
    page_title="NarrativaX",
    page_icon="🪶",
    layout="wide",
    initial_sidebar_state="expanded"
)

# === CONSTANTS ===
MAX_TOKENS = 1800
IMAGE_SIZE = (768, 1024)
SAFE_LOADING_MESSAGES = [
    "Sharpening quills...", "Mixing metaphorical ink...",
    "Convincing characters to behave...", "Battling clichés...",
    "Summoning muses...", "Where we're going, we don't need chapters..."
]

TONE_MAP = {
    "Romantic": "sensual, romantic, literary",
    "NSFW": "explicit, erotic, adult",
    "Wholesome": "uplifting, warm, feel-good",
    "Suspenseful": "tense, thrilling, page-turning",
    "Philosophical": "deep, reflective, thoughtful",
    "Motivational": "inspirational, personal growth, powerful",
    "Educational": "insightful, informative, structured",
    "Satirical": "humorous, ironic, critical",
    "Professional": "formal, business-like, articulate",
    "Instructive": "clear, structured, motivational",
    "Authoritative": "firm, knowledgeable, professional",
    "Conversational": "relatable, friendly, informal",
    "Reflective": "thoughtful, introspective, wise"
}

GENRES = [
    "Personal Development", "Business", "Memoir", "Self-Help", "Productivity",
    "Adventure", "Romance", "Sci-Fi", "Mystery", "Fantasy", "Horror",
    "NSFW", "Erotica", "Historical Fiction", "Philosophy", "Psychology",
    "Self-Discipline", "Time Management", "Wealth Building", "Confidence",
    "Mindfulness", "Goal Setting", "Stoicism", "Creativity",
    "Fitness & Health", "Habits", "Social Skills", "Leadership", "Focus",
    "Decision-Making", "Public Speaking", "Mental Clarity"
]

IMAGE_MODELS = {
    "Realistic Vision v5.1": "lucataco/realistic-vision-v5.1:2c8e954decbf70b7607a4414e5785ef9e4de4b8c51d50fb8b8b349160e0ef6bb",
    "Reliberate V3 (NSFW)": "asiryan/reliberate-v3:d70438fcb9bb7adb8d6e59cf236f754be0b77625e984b8595d1af02cdf034b29"
}

# === SESSION STATE ===
for key in ['book', 'outline', 'cover', 'characters', 'gen_progress', 'image_cache']:
    st.session_state.setdefault(key, {} if key == 'image_cache' else None)

# === API CONFIGURATION ===
def validate_api_keys():
    required_keys = ['OPENROUTER_API_KEY', 'REPLICATE_API_TOKEN']
    missing = [key for key in required_keys if key not in st.secrets]
    if missing:
        st.error(f"Missing API keys in secrets: {', '.join(missing)}")
        st.stop()

validate_api_keys()
os.environ["REPLICATE_API_TOKEN"] = st.secrets["REPLICATE_API_TOKEN"]

# === LOGO HANDLING ===
def load_logo():
    try:
        with open("logo.png", "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return None

LOGO_DATA = load_logo()
if LOGO_DATA:
    st.markdown(f"""
    <div style="display: flex; justify-content: center; margin: 2rem 0;">
        <img src="data:image/png;base64,{LOGO_DATA}" width="300" style="filter: drop-shadow(0 0 15px #ff69b4);">
    </div>
    """, unsafe_allow_html=True)

# === API INTEGRATIONS ===
def call_openrouter(prompt, model):
    headers = {
        "Authorization": f"Bearer {st.secrets['OPENROUTER_API_KEY']}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://narrativax.com",
        "X-Title": "NarrativaX Book Generator"
    }
    
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": MAX_TOKENS,
        "temperature": 0.7
    }
    
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        st.error(f"API Error: {str(e)}")
        return None

def generate_image(prompt, model_name, section):
    try:
        model_version = IMAGE_MODELS[model_name]
        output = replicate.run(
            model_version,
            input={
                "prompt": f"{prompt} [Style: {TONE_MAP[st.session_state.gen_progress['tone']]}]",
                "width": IMAGE_SIZE[0],
                "height": IMAGE_SIZE[1],
                "negative_prompt": "text, watermark" if "NSFW" in model_name else ""
            }
        )
        
        if not output:
            raise Exception("No image generated")
            
        image_url = output[0] if isinstance(output, list) else output
        response = requests.get(image_url, timeout=15)
        response.raise_for_status()
        
        image = Image.open(BytesIO(response.content))
        st.session_state.image_cache[section] = image
        return image
        
    except replicate.exceptions.ModelError as e:
        st.error(f"Model Error: {str(e)}")
        return None
    except requests.exceptions.HTTPError as e:
        st.error(f"HTTP Error: {e.response.status_code} - {e.response.text}")
        return None
    except Exception as e:
        st.error(f"Image Generation Failed: {str(e)}")
        return None

# === CORE FUNCTIONALITY ===
def generate_book_content():
    config = st.session_state.gen_progress
    genre = config['genre']
    is_dev = genre in ["Personal Development", "Self-Help", "Productivity"]
    progress_bar = st.progress(0)
    
    try:
        total_steps = 4 + (config['chapters'] * (2 if is_dev else 3))
        current_step = 0
        
        # Premise Generation
        current_step += 1
        progress_bar.progress(current_step/total_steps, text="🌟 Building your book idea...")
        premise = call_openrouter(
            f"Develop a {genre} book idea: {escape(config['prompt'])}",
            config['model']
        )
        if not premise:
            raise Exception("Failed to generate premise")
        
        # Outline Generation
        current_step += 1
        progress_bar.progress(current_step/total_steps, text="🗂️ Generating outline...")
        outline_prompt = (
            f"Write non-fiction outline for {genre} book. Prompt: {config['prompt']}. Tone: {TONE_MAP[config['tone']]}."
            if is_dev else
            f"Create fictional outline for {TONE_MAP[config['tone']]} {genre} story. Include plot points and character arcs."
        )
        st.session_state.outline = call_openrouter(outline_prompt, config['model'])
        if not st.session_state.outline:
            raise Exception("Failed to generate outline")
        
        # Chapter Generation
        book = {}
        for chapter_num in range(1, config['chapters'] + 1):
            current_step += 1
            progress_text = random.choice(SAFE_LOADING_MESSAGES)
            progress_bar.progress(current_step/total_steps, text=f"✍️ Writing Chapter {chapter_num}... {progress_text}")
            
            chapter_prompt = (
                f"Write Chapter {chapter_num} for {genre} book. Outline: {st.session_state.outline}"
                if is_dev else
                f"Write Chapter {chapter_num} for {genre} story. Outline: {st.session_state.outline}"
            )
            content = call_openrouter(chapter_prompt, config['model'])
            if not content:
                continue
                
            book[f"Chapter {chapter_num}"] = content
            
            if not is_dev:
                current_step += 1
                progress_bar.progress(current_step/total_steps, text=f"🖼️ Creating image for Chapter {chapter_num}")
                generate_image(
                    f"{content[:200]} {TONE_MAP[config['tone']]}",
                    config["img_model"],
                    f"chapter_{chapter_num}"
                )
        
        # Finalization
        current_step += 1
        progress_bar.progress(current_step/total_steps, text="📕 Creating cover art...")
        st.session_state.cover = generate_image(
            f"Cover art for {genre} book: {premise}", 
            config["img_model"], 
            "cover"
        )
        
        st.session_state.book = book
        progress_bar.progress(1.0, text="✅ Book generation complete!")
        time.sleep(2)
        
    except Exception as e:
        st.error(f"Generation Failed: {str(e)}")
        progress_bar.progress(0.0, text="❌ Generation aborted")
    finally:
        progress_bar.empty()

# === EXPORT FUNCTIONALITY ===
def create_export_zip():
    with NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
        with zipfile.ZipFile(tmp.name, 'w') as zipf:
            # PDF Export
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Helvetica", size=12)
            pdf.cell(200, 10, text=st.session_state.gen_progress.get('prompt', 'Untitled'), 
                    new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            
            for chapter, text in st.session_state.book.items():
                pdf.multi_cell(w=pdf.epw, h=10, text=f"{chapter}\n\n{text}")
            
            pdf_path = "book.pdf"
            pdf.output(pdf_path)
            zipf.write(pdf_path)
            os.remove(pdf_path)
            
            # DOCX Export
            doc = Document()
            doc.add_heading(st.session_state.gen_progress.get('prompt', 'Untitled'), 0)
            for chapter, text in st.session_state.book.items():
                doc.add_heading(chapter, level=1)
                doc.add_paragraph(text)
            docx_path = "book.docx"
            doc.save(docx_path)
            zipf.write(docx_path)
            os.remove(docx_path)
            
            # MP3 Export
            for idx, (chapter, text) in enumerate(st.session_state.book.items()):
                tts = gTTS(text=text, lang='en')
                mp3_path = f"chapter_{idx+1}.mp3"
                tts.save(mp3_path)
                zipf.write(mp3_path)
                os.remove(mp3_path)
        
        return tmp.name

# === MAIN INTERFACE ===
def main_interface():
    st.title("NarrativaX — AI-Powered Book Creator")
    
    with st.form("book_form"):
        prompt = st.text_area("🖋️ Your Idea or Prompt", height=120, 
                            placeholder="E.g. How to build unstoppable self-discipline...")
        
        col1, col2 = st.columns(2)
        genre = col1.selectbox("📚 Choose Genre", sorted(set(GENRES)))
        tone = col2.selectbox("🎭 Choose Tone", list(TONE_MAP.keys()))
        
        chapters = st.slider("📖 Number of Chapters", 3, 30, 10)
        
        col3, col4 = st.columns(2)
        model = col3.selectbox("🤖 LLM", ["nothingiisreal/mn-celeste-12b", "openai/gpt-4"])
        img_model = col4.selectbox("🖼️ Image Model", list(IMAGE_MODELS.keys()))
        
        if st.form_submit_button("🚀 Create Book"):
            if not prompt.strip():
                st.warning("Please enter your idea or prompt.")
            else:
                st.session_state.image_cache.clear()
                st.session_state.gen_progress = {
                    "prompt": prompt, 
                    "genre": genre, 
                    "tone": tone,
                    "chapters": chapters, 
                    "model": model, 
                    "img_model": img_model
                }
                generate_book_content()

    if st.session_state.book:
        st.header("📚 Generated Content")
        
        tabs = st.tabs(["Chapters", "Outline", "Export"])
        
        with tabs[0]:
            for chapter, content in st.session_state.book.items():
                with st.expander(chapter):
                    col1, col2 = st.columns([3, 2])
                    with col1:
                        st.write(content)
                        with NamedTemporaryFile(suffix=".mp3") as fp:
                            tts = gTTS(text=content, lang='en')
                            tts.save(fp.name)
                            st.audio(fp.name)
                    with col2:
                        image_key = f"chapter_{chapter.split()[-1]}"
                        if image_key in st.session_state.image_cache:
                            st.image(st.session_state.image_cache[image_key])
        
        with tabs[1]:
            st.markdown("### Book Outline")
            st.write(st.session_state.outline)
        
        with tabs[2]:
            st.download_button(
                label="📥 Download Complete Book",
                data=open(create_export_zip(), "rb").read(),
                file_name="narrativax_book.zip",
                mime="application/zip"
            )
            if st.button("🧹 Clear Session"):
                st.session_state.clear()
                st.rerun()

# === RUN APPLICATION ===
if __name__ == "__main__":
    main_interface()
