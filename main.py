# NarrativaX - Streamlit App
# Finalized and fixed main.py with full inline code (no threads that freeze on Streamlit Cloud)

import os
import json
import requests
import zipfile
import random
import replicate
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

# ========== INITIALIZATION ==========
st.set_page_config(
    page_title="NarrativaX", 
    page_icon="🩶", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# ========== CONSTANTS ==========
LOGO_URL = "https://raw.githubusercontent.com/Prosocr3ature/NarrativaX/main/logo.png"
MAX_TOKENS = 1800
IMAGE_SIZE = (768, 1024)
SAFE_LOADING_MESSAGES = [
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

# ========== UTILITIES ==========
def pil_to_base64(image: Image.Image) -> str:
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

def base64_to_pil(b64_str: str) -> Image.Image:
    return Image.open(BytesIO(base64.b64decode(b64_str)))

def call_openrouter(prompt: str, model: str) -> str:
    headers = {"Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY') or st.secrets.get('OPENROUTER_API_KEY')}"}
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
        return base64_to_pil(st.session_state.image_cache[id_key])
    output = replicate.run(
        IMAGE_MODELS[model_key],
        input={
            "prompt": f"{prompt[:250]} {random.choice(['intricate detail', 'cinematic lighting'])}",
            "negative_prompt": "text, watermark, blur",
            "num_inference_steps": 35,
            "width": IMAGE_SIZE[0],
            "height": IMAGE_SIZE[1]
        }
    )
    if output and isinstance(output, list):
        image_url = output[0]
        image_data = requests.get(image_url).content
        image = Image.open(BytesIO(image_data)).convert("RGB")
        st.session_state.image_cache[id_key] = pil_to_base64(image)
        return image
    return None

# ========== MAIN FLOW ==========
def generate_full_book(prompt, genre, tone, chapters, model, img_model):
    st.session_state.image_cache = {}
    st.session_state.book = {}
    st.session_state.outline = None
    st.session_state.cover = None
    st.session_state.characters = []

    with st.spinner(random.choice(SAFE_LOADING_MESSAGES)):
        # 1. Premise
        premise = call_openrouter(f"Develop a {genre} story premise: {prompt}", model)

        # 2. Outline
        outline_prompt = f"""Create detailed outline for {TONE_MAP[tone]} {genre} novel: {premise}
        Include chapter breakdowns, character arcs, and key plot points."""
        st.session_state.outline = call_openrouter(outline_prompt, model)

        # 3. Chapters
        sections = ["Foreword"] + [f"Chapter {i+1}" for i in range(chapters)] + ["Epilogue"]
        for sec in sections:
            text = call_openrouter(f"Write immersive '{sec}' content: {st.session_state.outline}", model)
            st.session_state.book[sec] = text
            generate_image(text[:300], img_model, sec)

        # 4. Cover & Characters
        st.session_state.cover = generate_image(
            f"Cinematic cover for {genre} novel: {prompt}", img_model, "cover")

        st.session_state.characters = json.loads(call_openrouter(
            f"Generate characters for {genre} novel in JSON format: {st.session_state.outline}\nFormat: [{{'name':'','role':'','personality':'','appearance':''}}]",
            model))

# ========== RENDER ==========
def render_app():
    st.image(LOGO_URL, width=220)
    st.title("NarrativaX — Intelligent Ghostwriter")

    prompt = st.text_area("Your Story Concept", placeholder="A forbidden romance between...", height=100)
    col1, col2, col3 = st.columns(3)
    genre = col1.selectbox("Genre", GENRES)
    tone = col2.selectbox("Tone", list(TONE_MAP))
    chapters = col3.slider("Chapters", 4, 30, 10)
    model = col1.selectbox("Text Model", ["nothingiisreal/mn-celeste-12b", "gryphe/mythomax-l2-13b"])
    img_model = col2.selectbox("Image Model", list(IMAGE_MODELS))

    if st.button("Generate Book", use_container_width=True):
        generate_full_book(prompt, genre, tone, chapters, model, img_model)

    if st.session_state.book:
        st.subheader("Your Book")
        if st.session_state.cover:
            st.image(st.session_state.cover, use_container_width=True)
        st.markdown(f"### Outline\n```
{st.session_state.outline}```")

        for sec, txt in st.session_state.book.items():
            with st.expander(sec):
                st.write(txt)
                if sec in st.session_state.image_cache:
                    st.image(base64_to_pil(st.session_state.image_cache[sec]), use_container_width=True)

        st.markdown("---")
        st.subheader("Characters")
        for char in st.session_state.characters:
            st.markdown(f"**{char['name']}**\nRole: {char['role']}\nPersonality: {char['personality']}\nAppearance: {char['appearance']}")

# ========== EXECUTE ==========
render_app()
