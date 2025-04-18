import os
import json
import requests
import zipfile
import random
import replicate
from docx import Document
from docx.shared import Inches
from fpdf import FPDF
from tempfile import NamedTemporaryFile
from gtts import gTTS
from PIL import Image
from io import BytesIO
import streamlit as st

# ========== CONSTANTS ==========
LOGO_URL = "https://raw.githubusercontent.com/Prosocr3ature/NarrativaX/main/logo.png"
MAX_TOKENS = 1800
IMAGE_SIZE = (768, 1024)
LOADING_MESSAGES = [
    "Sharpening quills...", "Mixing metaphorical ink...",
    "Convincing characters to behave...", "Battling clichés...",
    "Negotiating with plot holes...", "Summoning muses...",
    "Where we're going, we don't need chapters...",
    "Wordsmithing in progress...", "The pen is mightier... loading...",
    "Subverting expectations..."
]
TONE_MAP = {
    "Romantic": "sensual, romantic, literary",
    "Dark Romantic": "moody, passionate, emotional",
    "NSFW": "detailed erotic, emotional, mature",
    # ... (keep all tone mappings)
}
GENRES = [
    "Adventure", "Fantasy", "Dark Fantasy", "Romance", 
    # ... (keep all genres)
]
IMAGE_MODELS = {
    "Realistic Vision v5.1": "lucataco/realistic-vision-v5.1:2c8e954decbf70b7607a4414e5785ef9e4de4b8c51d50fb8b8b349160e0ef6bb",
    "Reliberate V3 (NSFW)": "asiryan/reliberate-v3:d70438fcb9bb7adb8d6e59cf236f754be0b77625e984b8595d1af02cdf034b29"
}

# ========== SESSION STATE ==========
if 'image_cache' not in st.session_state:
    st.session_state.image_cache = {}
for key in ['book', 'outline', 'cover', 'characters', 'gen_progress']:
    st.session_state.setdefault(key, None)

# ========== CORE FUNCTIONS ==========
def dramatic_logo():
    st.markdown(f"""
    <style>
        @keyframes float {{
            0% {{ transform: translate(-50%, -55%) rotate(-5deg); }}
            50% {{ transform: translate(-50%, -60%) rotate(5deg); }}
            100% {{ transform: translate(-50%, -55%) rotate(-5deg); }}
        }}
        @keyframes glow {{
            0% {{ filter: drop-shadow(0 0 10px #ff69b4); }}
            50% {{ filter: drop-shadow(0 0 25px #ff69b4); }}
            100% {{ filter: drop-shadow(0 0 10px #ff69b4); }}
        }}
        .logo-overlay {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.9);
            z-index: 9998;
        }}
        .logo-container {{
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            text-align: center;
            z-index: 9999;
        }}
        .logo-img {{
            width: min(80vw, 600px);
            animation: float 3s ease-in-out infinite, glow 2s ease-in-out infinite;
        }}
        .loading-message {{
            font-family: 'Playfair Display', serif;
            font-size: clamp(1.5rem, 4vw, 2.5rem);
            margin-top: 2rem;
            color: #fff;
            text-shadow: 0 0 10px #ff69b4;
            background: linear-gradient(45deg, #ff69b4, #ff1493);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .quote {{
            font-family: 'Cinzel', serif;
            font-size: clamp(1rem, 2.5vw, 1.4rem);
            color: #fff;
            margin-top: 1.5rem;
            letter-spacing: 0.1em;
            opacity: 0.8;
        }}
    </style>
    <div class="logo-overlay"></div>
    <div class="logo-container">
        <img class="logo-img" src="{LOGO_URL}">
        <div class="loading-message">{random.choice(LOADING_MESSAGES)}</div>
        <div class="quote">"Where ink meets imagination"</div>
    </div>
    """, unsafe_allow_html=True)

def generate_book_components():
    config = st.session_state.gen_progress
    progress_bar = st.progress(0)
    status_container = st.empty()
    preview_column = st.columns(1)[0]
    
    # Calculate total steps
    sections_count = config['chapters'] + 2
    total_steps = 3 + (sections_count * 2)
    current_step = 0
    book = {}

    try:
        # Generate Outline
        with status_container.status("🔮 Crafting story structure...", expanded=True) as status:
            outline = call_openrouter(
                f"Create detailed outline for {config['genre']} novel: {config['prompt']}",
                config['model']
            )
            current_step += 1
            progress_bar.progress(current_step/total_steps)
            status.update(label="📜 Solid outline created!", state="complete")
            preview_column.markdown(f"**Outline Preview:**\n```\n{outline[:200]}...\n```")

        # Generate Chapters
        sections = ["Foreword"] + [f"Chapter {i+1}" for i in range(config['chapters'])] + ["Epilogue"]
        for sec in sections:
            # Text
            with status_container.status(f"📖 Authoring {sec}...", expanded=True) as status:
                content = call_openrouter(
                    f"Write {sec} content for {config['genre']} novel: {outline}",
                    config['model']
                )
                current_step += 1
                progress_bar.progress(current_step/total_steps)
                status.update(label=f"✅ {sec} polished!", state="complete")
                book[sec] = content
                preview_column.markdown(f"**{sec} Preview:**\n{content[:150]}...")

            # Image
            with status_container.status(f"🎨 Painting {sec} visual...", expanded=True) as status:
                generate_image(content, config['img_model'], sec)
                current_step += 1
                progress_bar.progress(current_step/total_steps)
                status.update(label=f"🖼️ {sec} image complete!", state="complete")
                if img := st.session_state.image_cache.get(sec):
                    preview_column.image(img, use_container_width=True)

        # Generate Cover
        with status_container.status("🖼️ Crafting cover...", expanded=True) as status:
            st.session_state.cover = generate_image(
                f"Cinematic cover: {config['prompt']}", 
                config['img_model'], 
                "cover"
            )
            current_step += 1
            progress_bar.progress(current_step/total_steps)
            status.update(label="🎉 Cover complete!", state="complete")

        # Generate Characters
        with status_container.status("👥 Creating characters...", expanded=True) as status:
            st.session_state.characters = json.loads(call_openrouter(
                f"Create characters for {config['genre']} novel: {outline}",
                config['model']
            ))
            current_step += 1
            progress_bar.progress(current_step/total_steps)
            status.update(label="🤩 Characters ready!", state="complete")

        st.session_state.book = book
        st.balloons()
        st.success("📖 Book Ready!")
        st.session_state.gen_progress = None

    except Exception as e:
        st.error(f"🚨 Error: {str(e)}")
        st.session_state.gen_progress = None

# ========== UI COMPONENTS ==========
def main_interface():
    if st.session_state.get('gen_progress'):
        dramatic_logo()
        generate_book_components()
    else:
        st.markdown(f'<img src="{LOGO_URL}" width="300" style="float:right; margin:-50px -20px 0 0">', 
                   unsafe_allow_html=True)
        st.title("NarrativaX — Immersive AI Book Creator")
        
        with st.container():
            prompt = st.text_area("🖋️ Your Story Concept", height=120,
                                placeholder="A forbidden romance between...")
            col1, col2, col3 = st.columns(3)
            genre = col1.selectbox("📖 Genre", GENRES)
            tone = col2.selectbox("🎨 Tone", list(TONE_MAP))
            chapters = col3.slider("📚 Chapters", 4, 30, 10)
            model = col1.selectbox("🤖 AI Model", ["nothingiisreal/mn-celeste-12b", "gryphe/mythomax-l2-13b"])
            img_model = col2.selectbox("🖼️ Image Model", list(IMAGE_MODELS))

            if st.button("🚀 Create Book", use_container_width=True):
                st.session_state.gen_progress = {
                    "prompt": prompt, "genre": genre, "tone": tone,
                    "chapters": chapters, "model": model, "img_model": img_model
                }

def render_sidebar():
    with st.sidebar:
        st.markdown(f'<img src="{LOGO_URL}" width="200" style="margin-bottom:20px">', unsafe_allow_html=True)
        
        # Project Management
        if st.button("💾 Save Project"):
            try:
                with open("session.json", "w") as f:
                    json.dump({
                        'book': st.session_state.book,
                        'outline': st.session_state.outline,
                        'cover': st.session_state.cover,
                        'characters': st.session_state.characters,
                        'image_cache': st.session_state.image_cache
                    }, f)
                st.success("Project saved!")
            except Exception as e:
                st.error(f"Save failed: {str(e)}")

        if st.button("📂 Load Project"):
            try:
                with open("session.json", "r") as f:
                    st.session_state.update(json.load(f))
                st.success("Project loaded!")
            except Exception as e:
                st.error(f"Load failed: {str(e)}")

        # Export
        if st.session_state.book and st.button("📦 Export Book"):
            with st.spinner("Packaging..."):
                try:
                    with NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
                        with zipfile.ZipFile(tmp.name, 'w') as zipf:
                            # Add documents
                            create_docx(st.session_state.book, st.session_state.image_cache, 
                                      st.session_state.characters, "book.docx")
                            create_pdf(st.session_state.book, st.session_state.image_cache,
                                     st.session_state.characters, "book.pdf")
                            zipf.write("book.docx")
                            zipf.write("book.pdf")
                            os.remove("book.docx")
                            os.remove("book.pdf")
                            
                            # Add audio
                            for i, (sec, content) in enumerate(st.session_state.book.items()):
                                audio_path = f"chapter_{i+1}.mp3"
                                tts = gTTS(text=content, lang='en')
                                tts.save(audio_path)
                                zipf.write(audio_path)
                                os.remove(audio_path)
                            
                        with open(tmp.name, "rb") as f:
                            st.download_button("⬇️ Download", f.read(), "book.zip")
                        os.remove(tmp.name)
                except Exception as e:
                    st.error(f"Export failed: {str(e)}")

# ========== RUN APP ==========
if __name__ == "__main__":
    main_interface()
    render_sidebar()
    
    if st.session_state.book:
        st.header("Your Book")
        # ... (content display implementation from previous versions)
