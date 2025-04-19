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

# ========== INITIALIZATION ==========
st.set_page_config(
    page_title="NarrativaX", 
    page_icon="🪶", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# ========== CONSTANTS ==========
LOGO_URL = "https://raw.githubusercontent.com/Prosocr3ature/NarrativaX/main/logo.png"
MAX_TOKENS = 1800
IMAGE_SIZE = (768, 1024)
PROGRESS_QUEUE = queue.Queue()
TIMEOUT = 300  # 5 minutes

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

# ========== SESSION STATE ==========
for key in ['book', 'outline', 'cover', 'characters', 'gen_progress']:
    st.session_state.setdefault(key, None)
st.session_state.setdefault('image_cache', {})

def render_ui():
    st.markdown(
        f"""
        <style>
            .main-container {{ padding: 1rem; }}
            .header-title {{ font-size: 2.5rem; font-weight: 700; color: #ff69b4; }}
            .subtitle {{ font-size: 1.1rem; color: #ccc; margin-top: -10px; }}
            @media (max-width: 768px) {{
                .header-title {{ font-size: 1.8rem; }}
                .subtitle {{ font-size: 1rem; }}
                .stTextArea textarea {{ font-size: 16px !important; }}
            }}
        </style>
        <div class='main-container'>
            <div class='header-title'>NarrativaX</div>
            <div class='subtitle'>Immersive AI Story Generator</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("""---""")

    prompt = st.text_area("Enter your story concept:", placeholder="e.g. A forbidden romance between a vampire and a hunter in a post-apocalyptic city...", height=120)

    col1, col2, col3 = st.columns(3)
    genre = col1.selectbox("Genre", GENRES)
    tone = col2.selectbox("Narrative Tone", list(TONE_MAP.keys()))
    chapters = col3.slider("Number of Chapters", 4, 30, 10)

    model = col1.selectbox("Text AI Model", ["nothingiisreal/mn-celeste-12b", "gryphe/mythomax-l2-13b"])
    img_model = col2.selectbox("Image AI Model", list(IMAGE_MODELS))

    if st.button("Generate Book", use_container_width=True):
        if not prompt.strip():
            st.warning("Please enter a story prompt to begin.")
            return

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

# MAIN LOGIK
if __name__ == "__main__":
    if st.session_state.get("gen_progress"):
        dramatic_logo()
        progress_animation()
    else:
        render_ui()
        render_sidebar()
        display_content()
