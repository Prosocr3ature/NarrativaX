# main.py — NarrativaX Full App (Modern GUI + Mobile-Friendly)

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

# === Page Config ===
st.set_page_config(
    page_title="NarrativaX", 
    page_icon="🩶", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# === Constants ===
LOGO_URL = "https://raw.githubusercontent.com/Prosocr3ature/NarrativaX/main/logo.png"
MAX_TOKENS = 1800
IMAGE_SIZE = (768, 1024)
PROGRESS_QUEUE = queue.Queue()
TIMEOUT = 300

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

# === Session Init ===
for key in ["book", "outline", "cover", "characters", "gen_progress"]:
    st.session_state.setdefault(key, None)
st.session_state.setdefault("image_cache", {})

# === Core Functions ===
def pil_to_base64(image):
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()

def base64_to_pil(b64):
    return Image.open(BytesIO(base64.b64decode(b64)))

def call_openrouter(prompt, model):
    headers = {"Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.95,
        "max_tokens": MAX_TOKENS
    }
    try:
        res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=60)
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        PROGRESS_QUEUE.put(("ERROR", f"API Error: {str(e)}", 0, ""))
        raise

def generate_image(prompt, model_key, id_key):
    if id_key in st.session_state.image_cache:
        cached = st.session_state.image_cache[id_key]
        return base64_to_pil(cached) if isinstance(cached, str) else cached

    output = replicate.run(
        IMAGE_MODELS[model_key],
        input={
            "prompt": f"{escape(prompt[:250])} cinematic lighting, intricate, 8k",
            "negative_prompt": "text, watermark, blurry",
            "num_inference_steps": 35,
            "width": IMAGE_SIZE[0],
            "height": IMAGE_SIZE[1]
        }
    )
    if output and isinstance(output, list):
        response = requests.get(output[0], timeout=30)
        image = Image.open(BytesIO(response.content)).convert("RGB")
        st.session_state.image_cache[id_key] = pil_to_base64(image)
        return image
    return None

# === Background Thread ===
def background_generation_task():
    try:
        config = st.session_state.gen_progress
        total_steps = 4 + (config['chapters'] * 3)
        current_step = 0

        book = {}
        premise = call_openrouter(f"Develop a {config['genre']} story premise: {escape(config['prompt'])}", config['model'])
        current_step += 1
        PROGRESS_QUEUE.put(("🌌", "Developed premise", current_step/total_steps, premise))

        outline = call_openrouter(f"Create detailed outline for {TONE_MAP[config['tone']]} {config['genre']} novel: {premise}", config['model'])
        st.session_state.outline = outline
        current_step += 1
        PROGRESS_QUEUE.put(("📜", "Outline ready", current_step/total_steps, outline[:150]))

        sections = ["Foreword"] + [f"Chapter {i+1}" for i in range(config['chapters'])] + ["Epilogue"]
        for sec in sections:
            text = call_openrouter(f"Write {sec} for novel: {outline}", config['model'])
            book[sec] = text
            current_step += 1
            PROGRESS_QUEUE.put(("✍️", f"{sec} written", current_step/total_steps, text[:150]))
            generate_image(f"{escape(text[:200])} {TONE_MAP[config['tone']]}", config['img_model'], sec)
            current_step += 1

        st.session_state.cover = generate_image(f"Cinematic book cover for: {premise}", config['img_model'], "cover")
        current_step += 1

        characters = call_openrouter(f"List characters for novel as JSON: {outline}", config['model'])
        st.session_state.characters = json.loads(characters)
        current_step += 1

        st.session_state.book = book
        PROGRESS_QUEUE.put(("COMPLETE", "Book complete", 1.0, ""))

    except Exception as e:
        PROGRESS_QUEUE.put(("ERROR", f"Generation error: {str(e)}", 0, ""))
        st.session_state.gen_progress = None

# === Interface ===
def main():
    st.image(LOGO_URL, width=160)
    st.title("NarrativaX — AI Book Creator")

    prompt = st.text_area("Describe your story idea", height=120)
    col1, col2, col3 = st.columns(3)
    genre = col1.selectbox("Genre", GENRES)
    tone = col2.selectbox("Tone", list(TONE_MAP))
    chapters = col3.slider("Chapters", 4, 30, 10)
    model = col1.selectbox("AI Model", ["nothingiisreal/mn-celeste-12b", "gryphe/mythomax-l2-13b"])
    img_model = col2.selectbox("Image Model", list(IMAGE_MODELS))

    if st.button("Create Book"):
        st.session_state.gen_progress = {
            "prompt": prompt, "genre": genre, "tone": tone,
            "chapters": chapters, "model": model, "img_model": img_model
        }
        thread = threading.Thread(target=background_generation_task)
        add_script_run_ctx(thread)
        thread.start()
        st.rerun()

    if st.session_state.get("book"):
        st.subheader("Cover")
        if st.session_state.cover:
            st.image(st.session_state.cover, use_container_width=True)

        st.subheader("Outline")
        st.markdown(f"```
{st.session_state.outline}
```")

        st.subheader("Characters")
        for c in st.session_state.characters:
            st.markdown(f"**{c['name']}** — {c['role']}, *{c['personality']}*\n> {c['appearance']}")

        for sec, content in st.session_state.book.items():
            st.markdown(f"### {sec}")
            st.write(content)
            if sec in st.session_state.image_cache:
                img = st.session_state.image_cache[sec]
                if isinstance(img, str):
                    img = base64_to_pil(img)
                st.image(img, use_container_width=True)

if __name__ == "__main__":
    main()
