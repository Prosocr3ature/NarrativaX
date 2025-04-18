import os
import json
import requests
import zipfile
import random
import replicate
import threading
import queue
from docx import Document
from docx.shared import Inches
from fpdf import FPDF
from tempfile import NamedTemporaryFile
from gtts import gTTS
from PIL import Image
from io import BytesIO
import streamlit as st
from streamlit.runtime.scriptrunner import add_script_run_ctx

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
    "Hardcore": "intense, vulgar, graphic, pornographic",
    "BDSM": "dominant, submissive, explicit, power-play",
    "Playful": "flirty, teasing, lighthearted",
    "Mystical": "dreamlike, surreal, poetic",
    "Gritty": "raw, realistic, street-style",
    "Slow Burn": "subtle, growing tension, emotional depth",
    "Wholesome": "uplifting, warm, feel-good",
    "Suspenseful": "tense, thrilling, page-turning",
    "Philosophical": "deep, reflective, thoughtful"
}
GENRES = [
    "Adventure", "Fantasy", "Dark Fantasy", "Romance", "Thriller",
    "Mystery", "Drama", "Sci-Fi", "Slice of Life", "Horror", "Crime",
    "LGBTQ+", "Action", "Psychological", "Historical Fiction",
    "Supernatural", "Steampunk", "Cyberpunk", "Post-Apocalyptic",
    "Surreal", "Noir", "Erotica", "NSFW", "Hardcore", "BDSM",
    "Futanari", "Incubus/Succubus", "Monster Romance",
    "Dubious Consent", "Voyeurism", "Yaoi", "Yuri", "Taboo Fantasy"
]
IMAGE_MODELS = {
    "Realistic Vision v5.1": "lucataco/realistic-vision-v5.1:2c8e954decbf70b7607a4414e5785ef9e4de4b8c51d50fb8b8b349160e0ef6bb",
    "Reliberate V3 (NSFW)": "asiryan/reliberate-v3:d70438fcb9bb7adb8d6e59cf236f754be0b77625e984b8595d1af02cdf034b29"
}
PROGRESS_QUEUE = queue.Queue()

# ========== INITIALIZATION ==========
st.set_page_config(page_title="NarrativaX", page_icon="🪶", layout="wide")

# Initialize session state
for key in ['image_cache', 'book', 'outline', 'cover', 'characters', 'gen_progress']:
    st.session_state.setdefault(key, None)

# ========== CORE FUNCTIONS ==========
def call_openrouter(prompt: str, model: str) -> str:
    headers = {"Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.95,
        "max_tokens": MAX_TOKENS
    }
    response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()

def generate_image(prompt: str, model_key: str, id_key: str) -> Image.Image:
    if id_key in st.session_state.image_cache:
        return st.session_state.image_cache[id_key]
    
    try:
        output = replicate.run(
            IMAGE_MODELS[model_key],
            input={
                "prompt": prompt[:300],
                "num_inference_steps": 30,
                "guidance_scale": 7.5,
                "width": IMAGE_SIZE[0],
                "height": IMAGE_SIZE[1]
            }
        )
        
        if output and isinstance(output, list):
            image_url = output[0]
            response = requests.get(image_url)
            response.raise_for_status()
            image = Image.open(BytesIO(response.content))
            st.session_state.image_cache[id_key] = image
            return image
    except Exception as e:
        PROGRESS_QUEUE.put(("ERROR", f"Image generation failed: {str(e)}", 0, ""))
    return None

def background_generation_task():
    try:
        config = dict(st.session_state.gen_progress)
        total_steps = 3 + (config['chapters'] + 2) * 2
        current_step = 0
        book = {}

        # Outline
        PROGRESS_QUEUE.put(("🔮", "Crafting story structure...", current_step/total_steps, ""))
        outline = call_openrouter(
            f"Create detailed outline for {TONE_MAP[config['tone']]} {config['genre']} novel: {config['prompt']}", 
            config['model']
        )
        current_step += 1
        PROGRESS_QUEUE.put(("📜", "Outline complete!", current_step/total_steps, outline[:200]))

        # Chapters
        sections = ["Foreword"] + [f"Chapter {i+1}" for i in range(config['chapters'])] + ["Epilogue"]
        for sec in sections:
            # Text
            PROGRESS_QUEUE.put(("📖", f"Writing {sec}...", current_step/total_steps, ""))
            content = call_openrouter(f"Write immersive '{sec}' content: {outline}", config['model'])
            book[sec] = content
            current_step += 1
            PROGRESS_QUEUE.put(("✅", f"{sec} text complete!", current_step/total_steps, content[:150]))

            # Image
            PROGRESS_QUEUE.put(("🎨", f"Painting {sec} visual...", current_step/total_steps, ""))
            generate_image(content, config['img_model'], sec)
            current_step += 1
            PROGRESS_QUEUE.put(("🖼️", f"{sec} image complete!", current_step/total_steps, ""))

        # Cover
        PROGRESS_QUEUE.put(("🖼️", "Creating cover...", current_step/total_steps, ""))
        st.session_state.cover = generate_image(
            f"Cinematic cover: {config['prompt']}, {config['genre']}, {config['tone']}", 
            config['img_model'], 
            "cover"
        )
        current_step += 1
        PROGRESS_QUEUE.put(("🎉", "Cover complete!", current_step/total_steps, ""))

        # Characters
        PROGRESS_QUEUE.put(("👥", "Creating characters...", current_step/total_steps, ""))
        st.session_state.characters = json.loads(call_openrouter(
            f"""Create characters for {config['genre']} novel in JSON format:
            {outline}
            Format: [{{"name":"","role":"","personality":"","appearance":""}}]""",
            config['model']
        ))
        current_step += 1
        PROGRESS_QUEUE.put(("🤩", "Characters ready!", current_step/total_steps, ""))

        st.session_state.book = book
        PROGRESS_QUEUE.put(("COMPLETE", "📖 Book generation complete!", 1.0, ""))

    except Exception as e:
        PROGRESS_QUEUE.put(("ERROR", f"Generation failed: {str(e)}", 0, ""))
        st.session_state.gen_progress = None

# ========== UI COMPONENTS ==========
def dramatic_logo():
    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@500&family=Cinzel:wght@500&display=swap');
        @keyframes float {{
            0% {{ transform: translate(-50%, -55%) rotate(-5deg); }}
            50% {{ transform: translate(-50%, -60%) rotate(5deg); }}
            100% {{ transform: translate(-50%, -55%) rotate(-5deg); }}
        }}
        @keyframes pulse-text {{
            0% {{ opacity: 0.8; text-shadow: 0 0 10px #ff69b4; }}
            50% {{ opacity: 1; text-shadow: 0 0 20px #ff69b4; }}
            100% {{ opacity: 0.8; text-shadow: 0 0 10px #ff69b4; }}
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
            animation: float 3s ease-in-out infinite;
            filter: drop-shadow(0 0 20px #ff69b480);
        }}
        .loading-message {{
            font-family: 'Playfair Display', serif;
            font-size: clamp(1.5rem, 4vw, 2.5rem);
            margin-top: 2rem;
            color: #ff69b4;
            animation: pulse-text 2s infinite;
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

def progress_animation():
    if not PROGRESS_QUEUE.empty():
        status = PROGRESS_QUEUE.get()
        
        with st.empty() as container:
            while True:
                if status[0] == "COMPLETE":
                    st.balloons()
                    st.session_state.gen_progress = None
                    break
                elif status[0] == "ERROR":
                    st.error(f"🚨 {status[1]}")
                    st.session_state.gen_progress = None
                    break
                else:
                    emoji, message, progress, preview = status
                    container.markdown(f"""
                    <style>
                        @keyframes pulse {{
                            0% {{ transform: scale(0.95); opacity: 0.8; }}
                            50% {{ transform: scale(1.1); opacity: 1; }}
                            100% {{ transform: scale(0.95); opacity: 0.8; }}
                        }}
                        .status-emoji {{
                            font-size: 3rem;
                            animation: pulse 1.5s infinite;
                            display: inline-block;
                        }}
                        .preview-box {{
                            background: rgba(255,255,255,0.1);
                            border-radius: 10px;
                            padding: 1rem;
                            margin: 1rem 0;
                            border: 1px solid #ffffff20;
                        }}
                    </style>
                    <div style="text-align: center; padding: 2rem">
                        <div class="status-emoji">{emoji}</div>
                        <h3 style="margin: 1rem 0">{message}</h3>
                        <progress value="{progress}" max="1" style="width: 100%; height: 10px"></progress>
                        {f'<div class="preview-box">{preview}...</div>' if preview else ''}
                    </div>
                    """, unsafe_allow_html=True)
                
                try:
                    status = PROGRESS_QUEUE.get(timeout=0.1)
                except queue.Empty:
                    break

def main_interface():
    if st.session_state.get('gen_progress'):
        dramatic_logo()
        progress_animation()
    else:
        st.markdown(f'<img src="{LOGO_URL}" width="300" style="float:right; margin:-50px -20px 0 0">', unsafe_allow_html=True)
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
                gen_thread = threading.Thread(target=background_generation_task, daemon=True)
                add_script_run_ctx(gen_thread)
                gen_thread.start()
                st.rerun()

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
                            # Add DOCX
                            doc = Document()
                            for sec, content in st.session_state.book.items():
                                doc.add_heading(sec, level=1)
                                doc.add_paragraph(content)
                                if st.session_state.image_cache.get(sec):
                                    try:
                                        img = st.session_state.image_cache[sec]
                                        img_io = BytesIO()
                                        img.save(img_io, format='PNG')
                                        doc.add_picture(img_io, width=Inches(5))
                                    except Exception as e:
                                        st.error(f"Error adding image: {e}")
                            doc.save("book.docx")
                            zipf.write("book.docx")
                            os.remove("book.docx")

                            # Add PDF
                            pdf = FPDF()
                            pdf.add_page()
                            pdf.set_font("Arial", size=12)
                            for sec, content in st.session_state.book.items():
                                pdf.set_font("Arial", 'B', 16)
                                pdf.cell(200, 10, txt=sec, ln=True)
                                pdf.set_font("Arial", size=12)
                                pdf.multi_cell(0, 10, txt=content)
                            pdf.output("book.pdf")
                            zipf.write("book.pdf")
                            os.remove("book.pdf")

                            # Add Audio
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

def display_content():
    if st.session_state.book:
        st.header("Your Generated Book")
        
        with st.expander("📔 Book Cover", expanded=True):
            if st.session_state.cover:
                try:
                    st.image(st.session_state.cover, use_container_width=True)
                except Exception as e:
                    st.error(f"Error displaying cover: {str(e)}")
            else:
                st.warning("No cover generated yet")
        
        with st.expander("📝 Full Outline"):
            st.markdown(f"```\n{st.session_state.outline}\n```")
        
        with st.expander("👥 Character Bios"):
            for char in st.session_state.characters:
                with st.container():
                    cols = st.columns([1, 3])
                    cols[0].subheader(char.get('name', 'Unnamed'))
                    cols[1].write(f"""
                    **Role:** {char.get('role', 'Unknown')}  
                    **Personality:** {char.get('personality', 'N/A')}  
                    **Appearance:** {char.get('appearance', 'Not specified')}
                    """)

        for section, content in st.session_state.book.items():
            with st.expander(f"📜 {section}"):
                col1, col2 = st.columns([3, 2])
                with col1:
                    st.write(content)
                    with NamedTemporaryFile(suffix=".mp3") as tf:
                        tts = gTTS(text=content, lang='en')
                        tts.save(tf.name)
                        audio_bytes = open(tf.name, "rb").read()
                        st.audio(audio_bytes, format="audio/mp3")
                with col2:
                    if st.session_state.image_cache.get(section):
                        try:
                            st.image(
                                st.session_state.image_cache[section],
                                use_container_width=True
                            )
                        except Exception as e:
                            st.error(f"Image error: {str(e)}")
                    else:
                        st.warning("No image for this section")

# ========== RUN APPLICATION ==========
if __name__ == "__main__":
    main_interface()
    render_sidebar()
    display_content()
