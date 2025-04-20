import os
import json
import requests
import zipfile
import random
import replicate
import base64
import time
from io import BytesIO
from tempfile import NamedTemporaryFile
from html import escape
from PIL import Image
from docx import Document
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from gtts import gTTS
import streamlit as st
from streamlit_sortables import sort_items

# ====================
# CONSTANTS & CONFIG
# ====================
FONT_PATHS = {
    "regular": "fonts/NotoSans-Regular.ttf",
    "bold": "fonts/NotoSans-Bold.ttf"
}
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
    "Erotica", "Dark Fantasy", "Historical Fiction", "Cyberpunk",
    "Psychological", "Crime", "LGBTQ+", "Action", "Paranormal",
    "NSFW", "Philosophy", "Psychology", "Self-Discipline", "Time Management"
]

IMAGE_MODELS = {
    "Realistic Vision v5.1": "lucataco/realistic-vision-v5.1:2c8e954decbf70b7607a4414e5785ef9e4de4b8c51d50fb8b8b349160e0ef6bb",
    "Reliberate V3 (NSFW)": "asiryan/reliberate-v3:d70438fcb9bb7adb8d6e59cf236f754be0b77625e984b8595d1af02cdf034b29",
    "Stable Diffusion (General Purpose)": "stability-ai/stable-diffusion:ac732df83cea7fff18b8472768c88ad041fa750ff7682a21affe81863cbe77e4"
}

MODELS = [
    "nothingiisreal/mn-celeste-12b",
    "openchat/openchat-3.5-0106",
    "gryphe/mythomax-l2-13b",
    "nousresearch/nous-capybara-7b",
    "cognitivecomputations/dolphin-mixtral"
]

# ====================
# CORE FUNCTIONALITY
# ====================
class PDFStyler(FPDF):
    def __init__(self):
        super().__init__()
        self.font_configured = False
    
    def header(self):
        if self.font_configured:
            self.set_font('NotoSans', 'B', 12)
            self.cell(0, 10, 'NarrativaX Generated Book', 0, 1, 'C')
    
    def footer(self):
        if self.font_configured:
            self.set_y(-15)
            self.set_font('NotoSans', '', 8)
            self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def initialize_state():
    defaults = {
        "last_saved": None,
        "feedback_history": [],
        "characters": [],
        "chapter_order": [],
        "book": {},
        "outline": "",
        "cover": None,
        "gen_progress": {},
        "image_cache": {}
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

def validate_environment():
    required_keys = ['OPENROUTER_API_KEY', 'REPLICATE_API_TOKEN']
    missing = [key for key in required_keys if key not in st.secrets]
    if missing:
        st.error(f"Missing API keys: {', '.join(missing)}")
        st.stop()
    
    try:
        replicate.Client(api_token=st.secrets["REPLICATE_API_TOKEN"])
    except Exception as e:
        st.error(f"Replicate authentication failed: {str(e)}")
        st.stop()

def verify_fonts():
    missing = []
    for font_type, path in FONT_PATHS.items():
        if not os.path.exists(path):
            missing.append(path)
    if missing:
        raise FileNotFoundError(f"Missing fonts: {', '.join(missing)}")

# ====================
# AI INTEGRATIONS
# ====================
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
        
    except Exception as e:
        st.error(f"Image Generation Failed: {str(e)}")
        return None

# ====================
# CONTENT GENERATION
# ====================
def generate_book_content():
    config = st.session_state.gen_progress
    progress_bar = st.progress(0)
    
    try:
        total_steps = 4 + config['chapters'] * 3
        current_step = 0
        
        # Generate Outline
        current_step += 1
        progress_bar.progress(current_step/total_steps, text="🌟 Building your book idea...")
        st.session_state.outline = call_openrouter(
            f"Create outline for {config['genre']} book: {escape(config['prompt'])}. "
            f"Tone: {TONE_MAP[config['tone']]}. Chapters: {config['chapters']}",
            config['model']
        )
        
        # Generate Chapters
        book = {}
        sections = ["Foreword", "Introduction"] + [f"Chapter {i+1}" for i in range(config['chapters'])] + ["Final Words"]
        
        for idx, sec in enumerate(sections):
            current_step += 1
            progress_text = random.choice(SAFE_LOADING_MESSAGES)
            progress_bar.progress(current_step/total_steps, text=f"✍️ Writing {sec}... {progress_text}")
            
            content = call_openrouter(
                f"Write {sec} for {config['genre']} book. Outline: {st.session_state.outline}",
                config['model']
            )
            if content:
                book[sec] = content
                
            # Generate chapter image
            current_step += 1
            progress_bar.progress(current_step/total_steps, text=f"🖼️ Creating image for {sec}")
            generate_image(
                f"{content[:200]} {TONE_MAP[config['tone']]}",
                config["img_model"],
                f"section_{idx}"
            )
        
        # Generate Cover
        current_step += 1
        progress_bar.progress(current_step/total_steps, text="📕 Creating cover art...")
        st.session_state.cover = generate_image(
            f"Cover art for {config['genre']} book: {config['prompt']}", 
            config["img_model"], 
            "cover"
        )
        
        st.session_state.book = book
        st.session_state.chapter_order = sections
        progress_bar.progress(1.0, text="✅ Book generation complete!")
        time.sleep(2)
        
    except Exception as e:
        st.error(f"Generation Failed: {str(e)}")
    finally:
        progress_bar.empty()

# ====================
# EXPORT HANDLING
# ====================
def create_export_zip():
    try:
        verify_fonts()
        
        with NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
            with zipfile.ZipFile(tmp.name, 'w') as zipf:
                # PDF Export
                pdf = PDFStyler()
                pdf.add_page()
                pdf.add_font('NotoSans', '', FONT_PATHS["regular"])
                pdf.add_font('NotoSans', 'B', FONT_PATHS["bold"])
                pdf.font_configured = True

                title = st.session_state.gen_progress.get('prompt', 'Untitled')
                pdf.set_font("NotoSans", "B", size=16)
                pdf.cell(200, 10, text=title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.ln(10)

                pdf.set_font("NotoSans", size=12)
                for chapter, text in st.session_state.book.items():
                    pdf.set_font("NotoSans", "B", size=14)
                    pdf.multi_cell(w=pdf.epw, h=10, text=chapter)
                    pdf.ln(2)
                    pdf.set_font("NotoSans", "", size=12)
                    pdf.multi_cell(w=pdf.epw, h=10, text=text)
                    pdf.ln(8)

                pdf_path = "book.pdf"
                pdf.output(pdf_path)
                zipf.write(pdf_path)
                os.remove(pdf_path)

                # DOCX Export
                doc = Document()
                doc.add_heading(title, 0)
                for chapter, text in st.session_state.book.items():
                    doc.add_heading(chapter, level=1)
                    doc.add_paragraph(text)
                docx_path = "book.docx"
                doc.save(docx_path)
                zipf.write(docx_path)
                os.remove(docx_path)

                # Audio Export
                for idx, (chapter, text) in enumerate(st.session_state.book.items()):
                    tts = gTTS(text=text, lang='en')
                    mp3_path = f"chapter_{idx+1}.mp3"
                    tts.save(mp3_path)
                    zipf.write(mp3_path)
                    os.remove(mp3_path)

        return tmp.name
    except Exception as e:
        st.error(f"Export failed: {str(e)}")
        raise

# ====================
# UI COMPONENTS
# ====================
def main_interface():
    st.set_page_config(page_title="NarrativaX Studio", layout="wide")
    initialize_state()
    validate_environment()
    
    try:
        verify_fonts()
    except FileNotFoundError as e:
        st.error("System configuration error. Missing font files.")
        st.stop()

    # Sidebar
    with st.sidebar:
        st.image("https://i.imgur.com/vGV9N5k.png", width=200)
        st.markdown("**NarrativaX v3**")
        
        if st.button("💾 Save Session"):
            st.session_state.last_saved = time.time()
            with open("session.json", "w") as f:
                json.dump(st.session_state.book, f)
            st.success("Session saved!")
            
        if st.button("📂 Load Session"):
            try:
                with open("session.json") as f:
                    st.session_state.book = json.load(f)
                    st.session_state.chapter_order = list(st.session_state.book.keys())
                st.success("Session loaded!")
            except Exception as e:
                st.error(f"Load failed: {str(e)}")
                
        if st.session_state.last_saved:
            st.info(f"Last saved {int(time.time() - st.session_state.last_saved)}s ago")

    # Main Form
    with st.form("book_form"):
        st.text_area("📖 Book Concept", height=150, key="prompt",
                    placeholder="E.g. A dystopian romance about AI lovers...")
        
        col1, col2 = st.columns(2)
        genre = col1.selectbox("🎭 Genre", sorted(set(GENRES)))
        tone = col2.selectbox("🎨 Tone", list(TONE_MAP.keys()))
        
        col3, col4 = st.columns(2)
        chapters = col3.slider("📚 Chapters", 3, 30, 10)
        model = col4.selectbox("🤖 AI Model", MODELS)
        
        img_model = st.selectbox("🖼️ Image Model", list(IMAGE_MODELS.keys()))
        
        if st.form_submit_button("🚀 Generate Book"):
            st.session_state.image_cache.clear()
            st.session_state.gen_progress = {
                "prompt": st.session_state.prompt, 
                "genre": genre, 
                "tone": tone,
                "chapters": chapters, 
                "model": model, 
                "img_model": img_model
            }
            generate_book_content()

    # Tabs Interface
    if st.session_state.book:
        tabs = st.tabs(["📖 Chapters", "🎙️ Narration", "🖼️ Illustrations", "📤 Export", "👥 Characters", "💬 Feedback"])
        
        with tabs[0]:
            st.subheader("Reorder Chapters")
            reordered = sort_items(st.session_state.chapter_order)
            if reordered:
                st.session_state.chapter_order = reordered

            for title in st.session_state.chapter_order:
                content = st.session_state.book.get(title, "")
                with st.expander(title):
                    st.markdown(content)
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"🔄 Regenerate {title}", key=f"regen_{title}"):
                            st.session_state.book[title] = call_openrouter(
                                f"Rewrite this chapter: {content}", 
                                st.session_state.gen_progress['model']
                            )
                    with col2:
                        if st.button(f"✏️ AI Edit {title}", key=f"edit_{title}"):
                            instruction = st.text_input("Edit instructions", key=f"inst_{title}")
                            if instruction:
                                st.session_state.book[title] = call_openrouter(
                                    f"{instruction}:\n\n{content}", 
                                    st.session_state.gen_progress['model']
                                )

        with tabs[1]:
            for title, content in st.session_state.book.items():
                with st.expander(f"🔊 {title}"):
                    if st.button(f"Narrate {title}", key=f"narrate_{title}"):
                        with NamedTemporaryFile(suffix=".mp3") as fp:
                            tts = gTTS(text=content, lang='en')
                            tts.save(fp.name)
                            st.audio(fp.name)

        with tabs[2]:
            if st.session_state.cover:
                st.image(st.session_state.cover, caption="Book Cover", use_container_width=True)
                
            cols = st.columns(3)
            for idx, (section, image) in enumerate(st.session_state.image_cache.items()):
                with cols[idx % 3]:
                    st.image(image, caption=section.replace("_", " ").title())

        with tabs[3]:
            st.download_button(
                label="📦 Download Complete Package",
                data=open(create_export_zip(), "rb").read(),
                file_name="narrativax_book.zip",
                mime="application/zip"
            )
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Export DOCX"):
                    path = export_docx(st.session_state.book)
                    st.download_button("Download DOCX", open(path, "rb"), "book.docx")
            with col2:
                if st.button("Export PDF"):
                    path = export_pdf(st.session_state.book)
                    st.download_button("Download PDF", open(path, "rb"), "book.pdf")

        with tabs[4]:
            count = st.number_input("Number of Characters", 1, 20, 3)
            if st.button("Generate Characters"):
                new_chars = call_openrouter(
                    f"Generate {count} characters for {st.session_state.gen_progress['prompt']}",
                    st.session_state.gen_progress['model']
                ).split("\n\n")
                st.session_state.characters.extend(new_chars)

            for i, desc in enumerate(st.session_state.characters):
                with st.expander(f"Character {i+1}"):
                    updated = st.text_area(f"Edit Character {i+1}", desc, key=f"char_{i}")
                    if updated != desc:
                        st.session_state.characters[i] = updated

        with tabs[5]:
            with st.form("feedback_form"):
                feedback = st.text_area("Your suggestions for improvement")
                if st.form_submit_button("Submit Feedback"):
                    st.session_state.feedback_history.append(feedback)
                    st.success("Thank you for your feedback!")

            if st.session_state.feedback_history:
                st.subheader("Recent Feedback")
                for fb in st.session_state.feedback_history[-3:]:
                    st.info(fb)

if __name__ == "__main__":
    main_interface()
