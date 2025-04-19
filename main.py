# main.py - NarrativaX (Complete Enhanced Version)
import os
import json
import requests
import zipfile
import random
import replicate
import base64
import time
from html import escape
from docx import Document
from docx.shared import Inches
from fpdf import FPDF
from tempfile import NamedTemporaryFile
from gtts import gTTS
from PIL import Image
from io import BytesIO
import streamlit as st

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
    "Realistic Vision v5.1": "stability-ai/sdxl:c221b2b8ef527988fb59bf24a8b97c4561f1c671f73bd389f866bfb27c061316",
    "Reliberate V3 (NSFW)": "cjwbw/deliberate:0d0d2a8d5abf0e98e2b21b4725b19e2a0d052a31f9b5d15d9d4c8ddf47e1cdaa"
}

# === SESSION STATE ===
for key in ['book', 'outline', 'cover', 'characters', 'gen_progress']:
    st.session_state.setdefault(key, None)
st.session_state.setdefault('image_cache', {})

# === CENTERED LOGO ===
def load_logo():
    try:
        with open("logo.png", "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception as e:
        st.error(f"Logo Error: {str(e)}")
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
            json=payload
        )
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        st.error(f"API Error: {str(e)}")
        return None

def generate_image(prompt, model_name, section):
    try:
        output = replicate.run(
            IMAGE_MODELS[model_name],
            input={"prompt": f"{prompt} [Style: {TONE_MAP[st.session_state.gen_progress['tone']]}"}
        )
        image_url = output[0]
        image = Image.open(requests.get(image_url, stream=True).raw)
        st.session_state.image_cache[section] = image
        return image
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
        
        # Outline Generation
        current_step += 1
        progress_bar.progress(current_step/total_steps, text="🗂️ Generating outline...")
        if is_dev:
            st.session_state.outline = call_openrouter(
                f"Write non-fiction outline for {genre} book. Prompt: {config['prompt']}. Tone: {TONE_MAP[config['tone']]}.",
                config['model']
            )
        else:
            st.session_state.outline = call_openrouter(
                f"Create fictional outline for {TONE_MAP[config['tone']]} {genre} story. Include plot points and character arcs.",
                config['model']
            )
        
        # Chapter Generation
        book = {}
        for chapter_num in range(1, config['chapters'] + 1):
            current_step += 1
            progress_bar.progress(current_step/total_steps, text=f"✍️ Writing Chapter {chapter_num}...")
            
            if is_dev:
                content = call_openrouter(
                    f"Write Chapter {chapter_num} for {genre} book. Outline: {st.session_state.outline}",
                    config['model']
                )
            else:
                content = call_openrouter(
                    f"Write Chapter {chapter_num} for {genre} story. Outline: {st.session_state.outline}",
                    config['model']
                )
                
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

# === CHARACTER MANAGEMENT ===
def regenerate_character(char_index):
    try:
        new_char = call_openrouter(
            f"Regenerate character {st.session_state.characters[char_index]['name']} "
            f"for {st.session_state.gen_progress['genre']} story. Original outline: {st.session_state.outline}",
            st.session_state.gen_progress['model']
        )
        st.session_state.characters[char_index] = json.loads(new_char)
        st.rerun()
    except Exception as e:
        st.error(f"Character regeneration failed: {str(e)}")

def display_characters():
    st.subheader("👥 Character Management")
    if not st.session_state.characters:
        st.warning("No characters available.")
        return

    new_chars = st.session_state.characters.copy()
    for i, char in enumerate(st.session_state.characters):
        with st.expander(f"{char.get('name', 'Unnamed')} - {char.get('role', 'Unknown')}"):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(f"""
                    **Name:** {char.get('name', '')}  
                    **Role:** {char.get('role', '')}  
                    **Personality:** {char.get('personality', '')}  
                    **Appearance:** {char.get('appearance', '')}
                """)
            with col2:
                if st.button("♻️ Regenerate", key=f"regen_{i}"):
                    regenerate_character(i)
                if st.button("❌ Remove", key=f"remove_{i}"):
                    del new_chars[i]
                    st.rerun()
    st.session_state.characters = new_chars

# === EXPORT FUNCTIONALITY ===
def create_export_zip():
    with NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
        with zipfile.ZipFile(tmp.name, 'w') as zipf:
            # PDF Export
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            pdf.cell(200, 10, txt=st.session_state.book.get('title', 'Untitled'), ln=True)
            for chapter, text in st.session_state.book.items():
                pdf.multi_cell(0, 10, txt=f"{chapter}\n\n{text}")
            pdf.output("book.pdf")
            zipf.write("book.pdf")
            
            # DOCX Export
            doc = Document()
            doc.add_heading(st.session_state.book.get('title', 'Untitled'), 0)
            for chapter, text in st.session_state.book.items():
                doc.add_heading(chapter, level=1)
                doc.add_paragraph(text)
            doc.save("book.docx")
            zipf.write("book.docx")
            
            # MP3 Export
            for idx, (chapter, text) in enumerate(st.session_state.book.items()):
                tts = gTTS(text=text, lang='en')
                tts.save(f"chapter_{idx+1}.mp3")
                zipf.write(f"chapter_{idx+1}.mp3")
        
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
                    "prompt": prompt, "genre": genre, "tone": tone,
                    "chapters": chapters, "model": model, "img_model": img_model
                }
                generate_book_content()

    if st.session_state.book:
        st.header("📚 Generated Content")
        
        tabs = st.tabs(["Chapters", "Outline", "Characters", "Export"])
        
        with tabs[0]:
            for chapter, content in st.session_state.book.items():
                with st.expander(chapter):
                    col1, col2 = st.columns([3, 2])
                    with col1:
                        st.write(content)
                        tts = gTTS(text=content, lang='en')
                        with NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                            tts.save(fp.name)
                            st.audio(fp.name)
                    with col2:
                        if f"chapter_{chapter.split()[-1]}" in st.session_state.image_cache:
                            st.image(st.session_state.image_cache[f"chapter_{chapter.split()[-1]}"])
        
        with tabs[1]:
            st.code(st.session_state.outline)
        
        with tabs[2]:
            display_characters()
        
        with tabs[3]:
            st.download_button(
                label="📥 Download Complete Book",
                data=open(create_export_zip(), "rb").read(),
                file_name="narrativax_book.zip",
                mime="application/zip"
            )

# === RUN APPLICATION ===
if __name__ == "__main__":
    main_interface()
