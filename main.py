# main.py - Fullständig version av NarrativaX

import os
import json
import requests
import zipfile
import random
import replicate
import threading
import queue
import base64
import time
from html import escape
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from docx import Document
from docx.shared import Inches
from fpdf import FPDF
from tempfile import NamedTemporaryFile
from gtts import gTTS
from PIL import Image
from io import BytesIO
import streamlit as st
from streamlit.runtime.scriptrunner import add_script_run_ctx

# === INIT ===
st.set_page_config(
    page_title="NarrativaX",
    page_icon="🪶",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# === GLOBALS ===
MAX_TOKENS = 1800
IMAGE_SIZE = (768, 1024)
PROGRESS_QUEUE = queue.Queue()
TIMEOUT = 600

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
    "Realistic Vision v5.1": "lucataco/realistic-vision-v5.1",
    "Reliberate V3 (NSFW)": "asiryan/reliberate-v3"
}

# === SESSION STATE ===
for key in ['book', 'outline', 'cover', 'characters', 'gen_progress']:
    st.session_state.setdefault(key, None)
st.session_state.setdefault('image_cache', {})

# === LOGO ===
def load_logo():
    try:
        with open("logo.png", "rb") as f:
            return "data:image/png;base64," + base64.b64encode(f.read()).decode()
    except:
        return None

LOGO_DATA = load_logo()

# === WRAPPERS ===
def background_generation_wrapper():
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(background_generation_task)
            future.result(timeout=TIMEOUT)
    except TimeoutError:
        PROGRESS_QUEUE.put(("ERROR", "Generation timed out", 0, ""))
    finally:
        st.session_state.gen_progress = None

# === LOADING LOGO ===
def dramatic_logo():
    if LOGO_DATA:
        safe_message = escape(random.choice(SAFE_LOADING_MESSAGES))
        st.markdown(f"""
        <style>
            .logo-overlay {{ position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.9); z-index: 9998; }}
            .logo-container {{ position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); text-align: center; z-index: 9999; }}
            .logo-img {{ width: min(80vw, 400px); animation: float 3s ease-in-out infinite; filter: drop-shadow(0 0 15px #ff69b4); }}
            @keyframes float {{ 0% {{ transform: translate(-50%, -48%) rotate(-1deg); }} 50% {{ transform: translate(-50%, -52%) rotate(1deg); }} 100% {{ transform: translate(-50%, -48%) rotate(-1deg); }} }}
            .loading-message {{ font-size: 1.6rem; color: #ff69b4; animation: pulse 2s infinite; margin-top: 1rem; }}
            @keyframes pulse {{ 0%, 100% {{ opacity: 0.8; }} 50% {{ opacity: 1; }} }}
        </style>
        <div class="logo-overlay"></div>
        <div class="logo-container">
            <img class="logo-img" src="{LOGO_DATA}" />
            <div class="loading-message">{safe_message}</div>
        </div>
        """, unsafe_allow_html=True)

# === PROGRESS ANIMATION ===
def progress_animation():
    try:
        if not PROGRESS_QUEUE.empty():
            status = PROGRESS_QUEUE.get()
            with st.empty() as container:
                while True:
                    if status[0] in ["COMPLETE", "✅"]:
                        st.balloons()
                        break
                    elif status[0] in ["ERROR", "❌"]:
                        st.error(f"🚨 {escape(str(status[1]))[:200]}...")
                        break
                    else:
                        emoji, message, progress, preview = status
                        safe_preview = escape(str(preview))[:150] + "..." if preview else ""
                        container.markdown(f"""
                        <div style='text-align: center; padding: 2rem'>
                            <div style='font-size: 3rem'>{emoji}</div>
                            <h3>{escape(message)}</h3>
                            <progress value='{progress}' max='1' style='width: 100%'></progress>
                            {f'<p style="margin-top:1rem">{safe_preview}</p>' if preview else ''}
                        </div>
                        """, unsafe_allow_html=True)

                    try:
                        status = PROGRESS_QUEUE.get(timeout=0.1)
                    except queue.Empty:
                        break
    except Exception as e:
        st.error(f"Animation Error: {escape(str(e))[:200]}...")
        st.session_state.gen_progress = None

# ========== BACKEND ==========
def background_generation_task():
    try:
        config = st.session_state.gen_progress
        genre = config['genre']
        is_dev = genre in PERSONAL_DEV_GENRES
        total_steps = 4 + (config['chapters'] * (2 if is_dev else 3))
        current_step = 0

        def heartbeat():
            while st.session_state.gen_progress:
                PROGRESS_QUEUE.put(("💓", "Processing...", current_step/total_steps, ""))
                time.sleep(10)

        threading.Thread(target=heartbeat, daemon=True).start()

        # Step 1: Premise
        PROGRESS_QUEUE.put(("🌟", "Building your book idea...", current_step/total_steps, ""))
        premise = call_openrouter(
            f"Develop a {genre} book idea based on this input: {escape(config['prompt'])}",
            config['model']
        )
        current_step += 1

        # Step 2: Outline
        PROGRESS_QUEUE.put(("🗂️", "Generating outline...", current_step/total_steps, ""))
        if is_dev:
            st.session_state.outline = call_openrouter(
                f"Write a full non-fiction outline for a book about {genre}. Prompt: {config['prompt']}. Tone: {TONE_MAP[config['tone']]}.",
                config['model']
            )
        else:
            st.session_state.outline = call_openrouter(
                f"Create a detailed fictional outline for a {TONE_MAP[config['tone']]} {genre} story. Include major plot points and character arcs.",
                config['model']
            )
        current_step += 1

        # Step 3: Content
        book = {}
        sections = [f"Chapter {i+1}" for i in range(config['chapters'])]

        for section in sections:
            PROGRESS_QUEUE.put(("✍️", f"Writing {section}...", current_step/total_steps, ""))
            if is_dev:
                content = call_openrouter(
                    f"Write the full content of the section '{section}' for a non-fiction book about {genre}. Based on this outline: {st.session_state.outline}",
                    config['model']
                )
            else:
                content = call_openrouter(
                    f"Write immersive {section} content for the fictional {genre} story. Use this outline:\n{st.session_state.outline}",
                    config["model"]
                )
            book[section] = content
            current_step += 1

            # Skip image gen for personal dev
            if not is_dev:
                PROGRESS_QUEUE.put(("🖼️", f"Generating image for {section}...", current_step/total_steps, ""))
                generate_image(f"{content[:200]} {TONE_MAP[config['tone']]}", config["img_model"], section)
                current_step += 1

        # Step 4: Cover
        PROGRESS_QUEUE.put(("📕", "Creating cover art...", current_step/total_steps, ""))
        st.session_state.cover = generate_image(
            f"Cover art for {genre} book: {premise}", config["img_model"], "cover"
        )
        current_step += 1

        # Step 5: Characters (skip if non-fiction)
        if not is_dev:
            PROGRESS_QUEUE.put(("🧬", "Generating characters...", current_step/total_steps, ""))
            st.session_state.characters = json.loads(call_openrouter(
                f"Generate main characters in JSON format from this outline:\n{st.session_state.outline}",
                config["model"]
            ))
            current_step += 1
        else:
            st.session_state.characters = []

        st.session_state.book = book
        PROGRESS_QUEUE.put(("✅", "Book generation complete!", 1.0, ""))

    except Exception as e:
        PROGRESS_QUEUE.put(("❌", f"Error: {str(e)}", 0, ""))
        st.session_state.gen_progress = None

# ========== MAIN INTERFACE ==========
def main_interface():
    try:
        if st.session_state.get('gen_progress'):
            dramatic_logo()
            progress_animation()
            time.sleep(0.1)
            st.rerun()
        else:
            st.markdown(f'<img src="logo.png" width="200" style="float:right; margin:-50px -10px 0 0">', unsafe_allow_html=True)
            st.title("NarrativaX — Immersive AI Book Creator")

            st.markdown("""
            <style>
                @media (max-width: 768px) {
                    .stTextArea textarea { font-size: 16px !important; }
                    .stSelectbox div { font-size: 16px !important; }
                    .stSlider label, .stSlider span { font-size: 16px !important; }
                }
            </style>
            """, unsafe_allow_html=True)

            with st.form("book_form"):
                prompt = st.text_area("🖋️ Your Idea or Prompt", height=120, placeholder="E.g. How to build unstoppable self-discipline...")
                col1, col2 = st.columns(2)
                genre = col1.selectbox("📚 Choose Genre", sorted(set(GENRES)))
                tone = col2.selectbox("🎭 Choose Tone", list(TONE_MAP.keys()))
                chapters = st.slider("📖 Number of Chapters", min_value=3, max_value=30, value=10)
                col3, col4 = st.columns(2)
                model = col3.selectbox("🤖 LLM (OpenRouter)", ["nothingiisreal/mn-celeste-12b", "gryphe/mythomax-l2-13b"])
                img_model = col4.selectbox("🖼️ Image Model", list(IMAGE_MODELS.keys()))

                submit = st.form_submit_button("🚀 Create Book")
                if submit:
                    if not prompt.strip():
                        st.warning("Please enter your idea or prompt.")
                    else:
                        st.session_state.image_cache.clear()
                        st.session_state.cover = None
                        st.session_state.book = None
                        st.session_state.outline = None
                        st.session_state.characters = None

                        st.session_state.gen_progress = {
                            "prompt": prompt, "genre": genre, "tone": tone,
                            "chapters": chapters, "model": model, "img_model": img_model
                        }

                        gen_thread = threading.Thread(target=background_generation_wrapper, daemon=True)
                        add_script_run_ctx(gen_thread)
                        gen_thread.start()
                        st.rerun()
    except Exception as e:
        st.error(f"UI Error: {escape(str(e))[:300]}")

# ========== CHARACTER MANAGEMENT ==========
def regenerate_character(char_index, outline, genre, model):
    try:
        new_char_json = call_openrouter(
            f"""Regenerate a single character for this {genre} novel.
Outline:
{outline}
Format: {{"name":"","role":"","personality":"","appearance":""}}""", model)
        return json.loads(new_char_json)
    except Exception as e:
        st.error(f"Could not regenerate character: {e}")
        return None

def display_character_editor():
    try:
        st.subheader("👥 Character Management")
        if not st.session_state.characters:
            st.warning("No characters available.")
            return

        new_chars = st.session_state.characters.copy()
        for i, char in enumerate(st.session_state.characters):
            with st.expander(f"{char.get('name', 'Unnamed')} — {char.get('role', 'Unknown')}", expanded=False):
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
                        regenerated = regenerate_character(i, st.session_state.outline, st.session_state.gen_progress["genre"], st.session_state.gen_progress["model"])
                        if regenerated:
                            new_chars[i] = regenerated
                            st.success(f"Character {regenerated['name']} regenerated!")

                    if st.button("❌ Remove", key=f"delete_{i}"):
                        new_chars.pop(i)
                        st.success(f"Character removed.")
                        break  # restart to avoid index error

        st.session_state.characters = new_chars
    except Exception as e:
        st.error(f"Character Editor Error: {escape(str(e))}")

# ========== SIDEBAR ==========
def render_sidebar():
    try:
        with st.sidebar:
            st.markdown(f'<img src="logo.png" width="200" style="margin-bottom:20px">', unsafe_allow_html=True)
            
            if st.button("💾 Save Project"):
                try:
                    save_data = {
                        'book': st.session_state.book,
                        'outline': st.session_state.outline,
                        'characters': st.session_state.characters,
                        'image_cache': st.session_state.image_cache,
                        'cover': pil_to_base64(st.session_state.cover) if st.session_state.cover else None
                    }
                    with open("session.narrx", "w") as f:
                        json.dump(save_data, f)
                    st.success("Project saved!")
                except Exception as e:
                    st.error(f"Save failed: {escape(str(e))[:200]}...")

            if st.button("📂 Load Project"):
                try:
                    with open("session.narrx", "r") as f:
                        data = json.load(f)
                    
                    st.session_state.book = data.get('book')
                    st.session_state.outline = data.get('outline')
                    st.session_state.characters = data.get('characters')
                    st.session_state.image_cache = {
                        k: base64_to_pil(v) if isinstance(v, str) else v 
                        for k, v in data.get('image_cache', {}).items()
                    }
                    if data.get('cover'):
                        st.session_state.cover = base64_to_pil(data['cover'])
                    st.success("Project loaded!")
                except Exception as e:
                    st.error(f"Load failed: {escape(str(e))[:200]}...")

            if st.session_state.characters and st.button("📤 Export Characters (JSON)"):
                st.download_button(
                    label="Download JSON",
                    data=json.dumps(st.session_state.characters, indent=2),
                    file_name="characters.json",
                    mime="application/json"
                )

            if st.session_state.characters and st.button("🖼️ Export Character Collage"):
                try:
                    portrait_images = []
                    for char in st.session_state.characters:
                        name = char.get("name", "")
                        if name in st.session_state.image_cache:
                            img = st.session_state.image_cache[name]
                            if isinstance(img, str):
                                img = base64_to_pil(img)
                            portrait_images.append(img)

                    if not portrait_images:
                        st.warning("No character portraits to export.")
                    else:
                        widths, heights = zip(*(img.size for img in portrait_images))
                        total_width = sum(widths)
                        max_height = max(heights)
                        collage = Image.new('RGB', (total_width, max_height), (255, 255, 255))

                        x_offset = 0
                        for img in portrait_images:
                            collage.paste(img, (x_offset, 0))
                            x_offset += img.width

                        collage_io = BytesIO()
                        collage.save(collage_io, format='PNG')
                        st.download_button("⬇️ Download Collage", collage_io.getvalue(), "character_collage.png", "image/png")
                except Exception as e:
                    st.error(f"Collage export failed: {escape(str(e))[:200]}...")

            if st.session_state.book and st.button("📦 Export Book"):
                with st.spinner("Packaging your masterpiece..."):
                    try:
                        with NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
                            with zipfile.ZipFile(tmp.name, 'w') as zipf:
                                # DOCX
                                doc = Document()
                                for sec, content in st.session_state.book.items():
                                    doc.add_heading(sec, level=1)
                                    doc.add_paragraph(content)
                                    if sec in st.session_state.image_cache:
                                        img = st.session_state.image_cache[sec]
                                        if isinstance(img, str):
                                            img = base64_to_pil(img)
                                        img_io = BytesIO()
                                        img.save(img_io, format='PNG')
                                        doc.add_picture(img_io, width=Inches(5))
                                doc.save("book.docx")
                                zipf.write("book.docx")
                                os.remove("book.docx")

                                # PDF
                                pdf = FPDF()
                                pdf.set_auto_page_break(auto=True, margin=15)
                                if st.session_state.cover:
                                    cover_path = "cover.png"
                                    st.session_state.cover.save(cover_path)
                                    pdf.image(cover_path, x=0, y=0, w=pdf.w, h=pdf.h)
                                    pdf.add_page()
                                pdf.set_font("Arial", size=12)
                                for sec, content in st.session_state.book.items():
                                    pdf.set_font("Arial", 'B', 16)
                                    pdf.cell(0, 10, sec, ln=True)
                                    pdf.set_font("Arial", size=12)
                                    pdf.multi_cell(0, 10, content)
                                pdf.output("book.pdf")
                                zipf.write("book.pdf")
                                os.remove("book.pdf")

                                # Audio
                                for i, (sec, content) in enumerate(st.session_state.book.items()):
                                    with NamedTemporaryFile(delete=False, suffix=".mp3") as audio_tmp:
                                        tts = gTTS(text=content, lang='en')
                                        tts.save(audio_tmp.name)
                                        zipf.write(audio_tmp.name, f"chapter_{i+1}.mp3")
                                        os.remove(audio_tmp.name)

                            with open(tmp.name, "rb") as f:
                                st.download_button("⬇️ Download ZIP", f.read(), "narrativax_book.zip")
                            os.remove(tmp.name)
                    except Exception as e:
                        st.error(f"Export failed: {escape(str(e))[:200]}...")
    except Exception as e:
        st.error(f"Sidebar Error: {escape(str(e))[:200]}...")

# ========== DISPLAY CONTENT ==========
def display_content():
    try:
        if st.session_state.book:
            st.header("📚 Your Generated Book")

            tabs = st.tabs(["📔 Cover", "📝 Outline", "👥 Characters", "📖 Chapters"])

            # --- COVER ---
            with tabs[0]:
                if st.session_state.cover:
                    st.image(st.session_state.cover, use_column_width=True)
                else:
                    st.warning("No cover generated yet.")

            # --- OUTLINE ---
            with tabs[1]:
                st.markdown(f"```\n{escape(st.session_state.outline)}\n```")

            # --- CHARACTERS ---
            with tabs[2]:
                display_character_editor()

            # --- CHAPTERS ---
            with tabs[3]:
                for section, content in st.session_state.book.items():
                    with st.expander(f"📜 {escape(section)}", expanded=False):
                        col1, col2 = st.columns([3, 2])
                        with col1:
                            st.write(escape(content))
                            with NamedTemporaryFile(suffix=".mp3") as tf:
                                tts = gTTS(text=content, lang='en')
                                tts.save(tf.name)
                                st.audio(tf.name, format="audio/mp3")
                        with col2:
                            if section in st.session_state.image_cache:
                                img = st.session_state.image_cache[section]
                                if isinstance(img, str):
                                    img = base64_to_pil(img)
                                st.image(img, use_column_width=True)
                            else:
                                st.warning("No image for this section.")
    except Exception as e:
        st.error(f"Display Error: {escape(str(e))[:200]}...")

# ========== MAIN APP ==========
def main_interface():
    try:
        if st.session_state.get('gen_progress'):
            dramatic_logo()
            progress_animation()
            time.sleep(0.1)
            st.rerun()
        else:
            st.markdown(f'<img src="logo.png" width="200" style="float:right; margin:-50px -10px 0 0">', unsafe_allow_html=True)
            st.title("NarrativaX — Immersive AI Book Creator")

            st.markdown("""
            <style>
                @media (max-width: 768px) {
                    .stTextArea textarea { font-size: 16px !important; }
                    .stSelectbox div { font-size: 16px !important; }
                    .stSlider label, .stSlider span { font-size: 16px !important; }
                }
                .stSlider > div[data-baseweb="slider"] > div {
                    background-color: #ff69b4 !important;
                }
            </style>
            """, unsafe_allow_html=True)

            with st.form("book_form"):
                prompt = st.text_area("🖋️ Your Idea or Prompt", height=120, placeholder="E.g. How to build unstoppable self-discipline...")
                col1, col2 = st.columns(2)
                genre = col1.selectbox("📚 Choose Genre", sorted(set(GENRES)))
                tone = col2.selectbox("🎭 Choose Tone", list(TONE_MAP.keys()))
                chapters = st.slider("📖 Number of Chapters", min_value=3, max_value=30, value=10)
                col3, col4 = st.columns(2)
                model = col3.selectbox("🤖 LLM (OpenRouter)", ["nothingiisreal/mn-celeste-12b", "gryphe/mythomax-l2-13b"])
                img_model = col4.selectbox("🖼️ Image Model", list(IMAGE_MODELS.keys()))

                submit = st.form_submit_button("🚀 Create Book")
                if submit:
                    if not prompt.strip():
                        st.warning("Please enter your idea or prompt.")
                    else:
                        st.session_state.image_cache.clear()
                        st.session_state.cover = None
                        st.session_state.book = None
                        st.session_state.outline = None
                        st.session_state.characters = None

                        st.session_state.gen_progress = {
                            "prompt": prompt, "genre": genre, "tone": tone,
                            "chapters": chapters, "model": model, "img_model": img_model
                        }

                        gen_thread = threading.Thread(target=background_generation_wrapper, daemon=True)
                        add_script_run_ctx(gen_thread)
                        gen_thread.start()
                        st.rerun()
    except Exception as e:
        st.error(f"UI Error: {escape(str(e))[:300]}")

# ========== RUN APP ==========
if __name__ == "__main__":
    main_interface()
    render_sidebar()
    display_content()
