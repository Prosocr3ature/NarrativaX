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
from docx import Document
from docx.shared import Inches
from fpdf import FPDF
from tempfile import NamedTemporaryFile
from gtts import gTTS
from PIL import Image
from io import BytesIO
import streamlit as st
from streamlit.runtime.scriptrunner import add_script_run_ctx

# ========== INITIALIZATION ==========
st.set_page_config(page_title="NarrativaX", page_icon="🪶", layout="wide", initial_sidebar_state="collapsed")

# ========== CONSTANTS ==========
LOGO_URL = "https://raw.githubusercontent.com/Prosocr3ature/NarrativaX/main/logo.png"
MAX_TOKENS = 1800
IMAGE_SIZE = (768, 1024)
PROGRESS_QUEUE = queue.Queue()
TIMEOUT = 300  # 5 minutes

SAFE_LOADING_MESSAGES = [
    "Sharpening quills...", "Mixing metaphorical ink...", "Convincing characters to behave..."
]

TONE_MAP = {
    "Romantic": "sensual, romantic, literary", "NSFW": "detailed erotic, emotional, mature"
}

GENRES = ["Adventure", "Fantasy", "Romance", "Thriller", "Mystery"]

IMAGE_MODELS = {
    "Realistic Vision v5.1": "lucataco/realistic-vision-v5.1:2c8e954decbf70b7607a4414e5785ef9e4de4b8c51d50fb8b8b349160e0ef6bb"
}

# ========== SESSION STATE ==========
for key in ['book', 'outline', 'cover', 'characters', 'gen_progress']:
    st.session_state.setdefault(key, None)
st.session_state.setdefault('image_cache', {})

# ========== CORE FUNCTIONS ==========
def pil_to_base64(image: Image.Image) -> str:
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

def base64_to_pil(b64_str: str) -> Image.Image:
    return Image.open(BytesIO(base64.b64decode(b64_str)))

def call_openrouter(prompt: str, model: str) -> str:
    headers = {"Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}"}
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.95, "max_tokens": MAX_TOKENS}
    response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=60)
    return response.json().get("choices")[0].get("message").get("content").strip()

def generate_image(prompt: str, model_key: str, id_key: str) -> Image.Image:
    if id_key in st.session_state.image_cache:
        return base64_to_pil(st.session_state.image_cache[id_key])

    output = replicate.run(IMAGE_MODELS[model_key], input={"prompt": f"{escape(prompt[:250])} {random.choice(['8k resolution'])}", "width": IMAGE_SIZE[0], "height": IMAGE_SIZE[1]})
    if output:
        response = requests.get(output[0])
        image = Image.open(BytesIO(response.content)).convert("RGB")
        st.session_state.image_cache[id_key] = pil_to_base64(image)
        return image
    return None

# ========== BOOK GENERATION ==========
def background_generation_task():
    try:
        config = st.session_state.gen_progress
        total_steps = 4 + (config['chapters'] * 3)
        current_step = 0

        def heartbeat():
            while st.session_state.gen_progress:
                PROGRESS_QUEUE.put(("💓", "Processing...", current_step/total_steps, ""))
                time.sleep(10)

        heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
        add_script_run_ctx(heartbeat_thread)
        heartbeat_thread.start()

        # Phase 1: Concept Development
        PROGRESS_QUEUE.put(("🌌", "Developing core concept...", current_step/total_steps, ""))
        premise = call_openrouter(f"Develop a {config['genre']} story premise: {escape(config['prompt'])}", config['model'])
        current_step += 1

        # Phase 2: Outline Generation
        PROGRESS_QUEUE.put(("📜", "Crafting detailed outline...", current_step/total_steps, ""))
        outline_prompt = f"""Create detailed outline for {TONE_MAP[config['tone']]} {config['genre']} novel: {premise}
        Include chapter breakdowns, character arcs, and key plot points."""
        st.session_state.outline = call_openrouter(outline_prompt, config['model'])
        current_step += 1

        # Phase 3: Content Generation
        book = {}
        sections = ["Foreword"] + [f"Chapter {i+1}" for i in range(config['chapters'])] + ["Epilogue"]
        
        for sec in sections:
            PROGRESS_QUEUE.put(("📖", f"Writing {sec}...", current_step/total_steps, ""))
            content = call_openrouter(f"Write immersive '{sec}' content for {config['genre']} novel: {st.session_state.outline}", config['model'])
            book[sec] = content
            current_step += 1

            PROGRESS_QUEUE.put(("🎨", f"Generating {sec} image...", current_step/total_steps, ""))
            generate_image(f"{escape(content[:200])} {TONE_MAP[config['tone']]} style", config['img_model'], sec)
            current_step += 1

        # Phase 4: Final Assets
        PROGRESS_QUEUE.put(("🖼️", "Creating cover art...", current_step/total_steps, ""))
        st.session_state.cover = generate_image(f"Cinematic cover art for {config['genre']} novel: {premise}", config['img_model'], "cover")
        current_step += 1

        PROGRESS_QUEUE.put(("👥", "Developing characters...", current_step/total_steps, ""))
        st.session_state.characters = json.loads(call_openrouter(f"""Generate characters for {config['genre']} novel in JSON format:
        {st.session_state.outline} Format: [{{"name":"","role":"","personality":"","appearance":""}}]""", config['model']))
        current_step += 1

        st.session_state.book = book
        PROGRESS_QUEUE.put(("COMPLETE", "📖 Book generation complete!", 1.0, ""))

    except Exception as e:
        PROGRESS_QUEUE.put(("ERROR", f"Generation failed: {str(e)}", 0, ""))
        st.session_state.gen_progress = None

def background_generation_wrapper():
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(background_generation_task)
            future.result(timeout=TIMEOUT)
    except TimeoutError:
        PROGRESS_QUEUE.put(("ERROR", "Generation timed out after 5 minutes", 0, ""))
    finally:
        st.session_state.gen_progress = None

# ========== UI COMPONENTS ==========
def dramatic_logo():
    safe_message = escape(random.choice(SAFE_LOADING_MESSAGES))
    st.markdown(f"""
    <style>
        .logo-overlay {{ position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.9); }}
        .logo-container {{ position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); text-align: center; }}
        .logo-img {{ width: min(80vw, 600px); animation: float 3.5s ease-in-out infinite; filter: drop-shadow(0 0 20px #ff69b480); }}
        .loading-message {{ font-size: clamp(2rem, 5vw, 3rem); margin-top: 2rem; color: #ff69b4; animation: pulse 1.5s infinite; }}
    </style>
    <div class="logo-overlay"></div>
    <div class="logo-container">
        <img class="logo-img" src="{LOGO_URL}">
        <div class="loading-message">{safe_message}</div>
    </div>
    """, unsafe_allow_html=True)

def progress_animation():
    if not PROGRESS_QUEUE.empty():
        status = PROGRESS_QUEUE.get()
        with st.empty() as container:
            while status[0] != "COMPLETE":
                emoji, message, progress, preview = status
                container.markdown(f"""
                <div style="text-align: center; padding: 2rem">
                    <div style="font-size: 3rem;">{emoji}</div>
                    <h3>{escape(message)}</h3>
                    <progress value="{progress}" max="1"></progress>
                </div>
                """, unsafe_allow_html=True)
                status = PROGRESS_QUEUE.get(timeout=0.1)

# ========== MAIN EXECUTION ==========
def main_interface():
    if st.session_state.get('gen_progress'):
        dramatic_logo()
        progress_animation()
        st.experimental_rerun()
    else:
        st.title("NarrativaX — Immersive AI Book Creator")
        with st.container():
            prompt = st.text_area("🖋️ Your Story Concept", height=120, placeholder="A forbidden romance between...")
            col1, col2 = st.columns(3)
            genre = col1.selectbox("📖 Genre", GENRES)
            tone = col2.selectbox("🎨 Tone", list(TONE_MAP))
            chapters = col1.slider("📚 Chapters", 4, 30, 10)
            model = col1.selectbox("🤖 AI Model", ["nothingiisreal/mn-celeste-12b", "gryphe/mythomax-l2-13b"])
            img_model = col2.selectbox("🖼️ Image Model", list(IMAGE_MODELS))

            if st.button("🚀 Create Book", use_container_width=True):
                st.session_state.gen_progress = {"prompt": prompt, "genre": genre, "tone": tone, "chapters": chapters, "model": model, "img_model": img_model}
                gen_thread = threading.Thread(target=background_generation_wrapper, daemon=True)
                gen_thread.start()

if __name__ == "__main__":
    main_interface()
    progress_animation()
