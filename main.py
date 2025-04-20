# main.py - NarrativaX (Enhanced Version)
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

# === CONSTANTS ===
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
    "General": {
        "Romantic": "sensual, romantic, literary",
        "Wholesome": "uplifting, warm, feel-good",
        "Suspenseful": "tense, thrilling, page-turning",
        "Philosophical": "deep, reflective, thoughtful",
        "Motivational": "inspirational, personal growth, powerful",
        "Educational": "insightful, informative, structured",
        "Satirical": "humorous, ironic, critical",
        "Professional": "formal, business-like, articulate"
    },
    "Adult": {
        "Erotic": "explicit, sensual, adult",
        "Kink-Friendly": "taboo, fetish, experimental",
        "Dark Romance": "obsessive, possessive, intense",
        "BDSM": "power dynamics, domination, submission",
        "Taboo": "forbidden, age-gap, forbidden relationships"
    }
}

GENRES = {
    "General": [
        "Personal Development", "Business", "Memoir", "Self-Help", "Productivity",
        "Adventure", "Romance", "Sci-Fi", "Mystery", "Fantasy", "Historical Fiction",
        "Philosophy", "Psychology", "Leadership", "Creativity"
    ],
    "Adult": [
        "Erotica", "Dark Fantasy", "Taboo Romance", "BDSM", "Harem",
        "Omegaverse", "Paranormal Romance", "Reverse Harem", "Urban Fantasy"
    ]
}

IMAGE_MODELS = {
    "General": {
        "Realistic Vision v5.1": "lucataco/realistic-vision-v5.1:2c8e954decbf70b7607a4414e5785ef9e4de4b8c51d50fb8b8b349160e0ef6bb"
    },
    "Adult": {
        "Reliberate V3 (Adult)": "asiryan/reliberate-v3:d70438fcb9bb7adb8d6e59cf236f754be0b77625e984b8595d1af02cdf034b29",
        "Uber Realistic Porn Merge URPM 1": "ductridev/uber-realistic-porn-merge-urpm-1:1cca487c3bfe167e987fc3639477cf2cf617747cd38772421241b04d27a113a8"
    }
}

LLM_MODELS = {
    "General": [
        "openai/gpt-4",
        "anthropic/claude-2"
    ],
    "Adult": [
        "nothingiisreal/mn-celeste-12b",
        "nousresearch/nous-hermes-llama2-13b",
        "mancer/dolphin-mixtral-8x7b",
        "migtissera/synthia-70b"
    ]
}

# === HELPER FUNCTIONS ===
def get_content_category(genre):
    return "Adult" if genre in GENRES["Adult"] else "General"

def call_openrouter(prompt, model_name):
    headers = {
        "Authorization": f"Bearer {st.secrets['OPENROUTER_API_KEY']}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": MAX_TOKENS
    }
    
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60
        )
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        st.error(f"API Error: {str(e)}")
        return None

def generate_image(prompt, model_id):
    try:
        output = replicate.run(
            model_id,
            input={"prompt": prompt, "width": IMAGE_SIZE[0], "height": IMAGE_SIZE[1]}
        )
        if not output:
            return None
            
        image_url = output[0] if isinstance(output, list) else output
        response = requests.get(image_url)
        return Image.open(BytesIO(response.content))
    except Exception as e:
        st.error(f"Image Generation Error: {str(e)}")
        return None

# === CONTENT GENERATION ===
def generate_book_content():
    config = st.session_state.gen_progress
    content_category = get_content_category(config['genre'])
    
    with st.status("Building Your Masterpiece...", expanded=True) as status:
        # Generate Cover
        st.write("🎨 Crafting Cover Art...")
        cover_prompt = f"Book cover for {config['genre']} story: {config['prompt']}. Style: {TONE_MAP[content_category][config['tone']]}"
        st.session_state.cover = generate_image(
            cover_prompt,
            IMAGE_MODELS[content_category][config['img_model']]
        )
        
        # Generate Chapters
        st.session_state.book = {}
        st.session_state.story_so_far = []
        progress_bar = st.progress(0)
        
        for i in range(1, config['chapters'] + 1):
            status.update(label=f"📝 Writing Chapter {i}/{config['chapters']}")
            content = generate_chapter(i)
            if not content:
                st.error(f"Failed to generate Chapter {i}")
                return
                
            progress_bar.progress(i/config['chapters'])
            time.sleep(0.5)  # Rate limiting
            
        status.update(label="✅ Story Generation Complete!", state="complete")

# === EXPORT FUNCTIONS ===
def create_docx():
    doc = Document()
    doc.add_heading(st.session_state.gen_progress['prompt'], 0)
    
    if st.session_state.cover:
        with NamedTemporaryFile(suffix=".jpg") as temp_file:
            st.session_state.cover.save(temp_file.name)
            doc.add_picture(temp_file.name, width=Inches(6))
    
    for chapter, content in st.session_state.book.items():
        doc.add_heading(chapter, level=1)
        doc.add_paragraph(content)
    
    return doc

def create_pdf():
    pdf = FPDF()
    pdf.add_font("NotoSans", style="", fname=FONT_PATHS["regular"], uni=True)
    pdf.add_font("NotoSans", style="B", fname=FONT_PATHS["bold"], uni=True)
    
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    # Title
    pdf.set_font("NotoSans", "B", 16)
    pdf.multi_cell(0, 10, st.session_state.gen_progress['prompt'])
    pdf.ln(10)
    
    # Cover Image
    if st.session_state.cover:
        with NamedTemporaryFile(suffix=".jpg") as temp_file:
            st.session_state.cover.save(temp_file.name)
            pdf.image(temp_file.name, w=pdf.epw)
    
    # Chapters
    pdf.set_font("NotoSans", "", 12)
    for chapter, content in st.session_state.book.items():
        pdf.set_font("", "B", 14)
        pdf.cell(0, 10, chapter, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("", "", 12)
        pdf.multi_cell(0, 8, content)
        pdf.ln(5)
    
    return pdf

# === UI COMPONENTS ===
def show_exports():
    with st.expander("📤 Export Options"):
        col1, col2, col3 = st.columns(3)
        
        # DOCX
        with col1:
            doc = create_docx()
            with NamedTemporaryFile(suffix=".docx") as tmp:
                doc.save(tmp.name)
                st.download_button(
                    "📝 Download DOCX",
                    data=open(tmp.name, "rb").read(),
                    file_name="story.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
        
        # PDF
        with col2:
            pdf = create_pdf()
            st.download_button(
                "📄 Download PDF",
                data=pdf.output(dest="S").encode("latin1"),
                file_name="story.pdf",
                mime="application/pdf"
            )
        
        # Audio
        with col3:
            if st.button("🎧 Generate Audiobook"):
                with st.spinner("Generating Audio..."):
                    full_text = "\n".join(st.session_state.book.values())
                    tts = gTTS(full_text, lang='en', slow=False)
                    with NamedTemporaryFile(suffix=".mp3") as fp:
                        tts.save(fp.name)
                        st.audio(fp.read(), format="audio/mp3")

def main_interface():
    st.title("NarrativaX — AI-Powered Story Studio")
    
    with st.sidebar:
        st.header("Configuration")
        selected_genre = st.session_state.get('genre_select', GENRES["General"][0])
        content_category = get_content_category(selected_genre)
        
        selected_model = st.selectbox(
            "🤖 LLM Model",
            LLM_MODELS[content_category],
            index=0
        )
        
        selected_img_model = st.selectbox(
            "🖼️ Image Model",
            list(IMAGE_MODELS[content_category].keys()),
            index=0
        )

    if st.session_state.get('book'):
        st.subheader("Generated Content")
        
        if st.session_state.cover:
            st.image(st.session_state.cover, use_column_width=True)
            
        for chapter, content in st.session_state.book.items():
            with st.expander(chapter):
                st.write(content)
        
        show_exports()
        return

    with st.form("story_form"):
        col1, col2 = st.columns(2)
        genre = col1.selectbox(
            "📚 Genre",
            sorted(GENRES["General"] + GENRES["Adult"]),
            key="genre_select"
        )
        tone = col2.selectbox(
            "🎭 Tone",
            sorted(TONE_MAP[get_content_category(genre)].keys()),
            key="tone_select"
        )
        
        prompt = st.text_area("✨ Story Premise", height=120,
                            placeholder="A dystopian society where emotions are controlled...")
        chapters = st.slider("📖 Chapters", 3, 50, 12)
        
        if st.form_submit_button("🚀 Generate Story"):
            st.session_state.gen_progress = {
                "prompt": prompt,
                "genre": genre,
                "tone": tone,
                "chapters": chapters,
                "model": selected_model,
                "img_model": selected_img_model
            }
            generate_book_content()
            st.rerun()

# === INITIALIZATION ===
if __name__ == "__main__":
    for key in ['book', 'outline', 'cover', 'characters', 'gen_progress', 'image_cache', 'story_so_far']:
        st.session_state.setdefault(key, {} if key in ['image_cache', 'characters'] else None)
    
    if not st.secrets.get("OPENROUTER_API_KEY") or not st.secrets.get("REPLICATE_API_TOKEN"):
        st.error("Missing required API keys in secrets.toml")
        st.stop()
    
    os.environ["REPLICATE_API_TOKEN"] = st.secrets["REPLICATE_API_TOKEN"]
    warnings.filterwarnings("ignore", category=UserWarning)  # Suppress PIL warnings
    
    main_interface()
