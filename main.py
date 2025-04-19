# START OF FILE
# main.py

import os
import json
import requests
import zipfile
import base64
import threading
import time
import queue
import replicate
import random
from io import BytesIO
from PIL import Image
from tempfile import NamedTemporaryFile
from html import escape
from docx import Document
from docx.shared import Inches
from fpdf import FPDF
from ebooklib import epub
from gtts import gTTS
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import streamlit as st
from streamlit.runtime.scriptrunner import add_script_run_ctx

# ========== CONFIG ==========
st.set_page_config(page_title="NarrativaX", page_icon="🪶", layout="wide")

LOGO_URL = "https://raw.githubusercontent.com/Prosocr3ature/NarrativaX/main/logo.png"
MAX_TOKENS = 1800
IMAGE_SIZE = (768, 1024)
PROGRESS_QUEUE = queue.Queue()
TIMEOUT = 600

LANGS = {
    "English": "en", "Swedish": "sv", "French": "fr",
    "German": "de", "Spanish": "es", "Japanese": "ja"
}

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

GENRES = ["Fantasy", "Romance", "Thriller", "Sci-Fi", "NSFW", "Dark Fantasy"]

IMAGE_MODELS = {
    "Realistic Vision": "lucataco/realistic-vision-v5.1:2c8e954...",
    "Reliberate V3": "asiryan/reliberate-v3:d70438fc..."
}

for key in ['book', 'outline', 'cover', 'characters', 'gen_progress', 'lang']:
    st.session_state.setdefault(key, None)

st.session_state.setdefault('image_cache', {})

# ========== UTILITIES ==========
def pil_to_base64(image: Image.Image) -> str:
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

def base64_to_pil(b64_str: str) -> Image.Image:
    return Image.open(BytesIO(base64.b64decode(b64_str)))

# ========== LLM CALL ==========
def call_openrouter(prompt: str, model: str) -> str:
    headers = {"Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.95,
        "max_tokens": MAX_TOKENS
    }
    res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
    return res.json()["choices"][0]["message"]["content"].strip()

# ========== IMAGE ==========
def generate_image(prompt: str, model_key: str, id_key: str) -> Image.Image:
    if id_key in st.session_state.image_cache:
        cached = st.session_state.image_cache[id_key]
        return base64_to_pil(cached) if isinstance(cached, str) else cached

    output = replicate.run(
        IMAGE_MODELS[model_key],
        input={
            "prompt": prompt,
            "width": IMAGE_SIZE[0], "height": IMAGE_SIZE[1],
            "num_inference_steps": 30, "guidance_scale": 7.5
        }
    )
    if output and isinstance(output, list):
        response = requests.get(output[0])
        image = Image.open(BytesIO(response.content)).convert("RGB")
        st.session_state.image_cache[id_key] = pil_to_base64(image)
        return image
    return None

# ========== GENERATION ==========
def background_generation():
    config = st.session_state.gen_progress
    total = 3 + config['chapters'] * 2
    current = 0

    outline = call_openrouter(
        f"Write a detailed outline for a {config['tone']} {config['genre']} novel: {config['prompt']}",
        config['model']
    ); current += 1
    st.session_state.outline = outline
    book = {}

    sections = [f"Chapter {i+1}" for i in range(config['chapters'])]
    for sec in sections:
        text = call_openrouter(f"Write {sec} based on outline: {outline}", config['model'])
        book[sec] = text; current += 1
        generate_image(text[:300], config['img_model'], sec); current += 1

    st.session_state.cover = generate_image(f"Cover for {config['prompt']}", config['img_model'], "cover")
    st.session_state.book = book

    st.session_state.characters = json.loads(call_openrouter(
        f"Generate characters in JSON list for {config['genre']}: {outline}", config['model']
    ))
    st.session_state.outline = outline
    PROGRESS_QUEUE.put(("DONE",))

# ========== UI ==========
def main():
    st.image(LOGO_URL, width=200)
    st.title("NarrativaX")

    mode = st.radio("Mode", ["Classic", "Wizard"])
    prompt = st.text_area("Story idea:")
    col1, col2 = st.columns(2)
    genre = col1.selectbox("Genre", GENRES)
    tone = col2.selectbox("Tone", list(TONE_MAP))
    chapters = st.slider("Chapters", 3, 20, 6)
    model = col1.selectbox("Model", ["nothingiisreal/mn-celeste-12b", "gryphe/mythomax-l2-13b"])
    img_model = col2.selectbox("Image Model", list(IMAGE_MODELS))
    lang = st.selectbox("Language", list(LANGS.keys()))

    if st.button("Generate"):
        st.session_state.gen_progress = {
            "prompt": prompt, "genre": genre, "tone": tone,
            "chapters": chapters, "model": model, "img_model": img_model
        }
        st.session_state.lang = LANGS[lang]
        t = threading.Thread(target=background_generation)
        add_script_run_ctx(t); t.start()
        st.rerun()

    if st.session_state.book:
        st.success("Book generated!")
        st.image(st.session_state.cover)
        st.markdown(f"### Outline\n```
{st.session_state.outline}```")
        for k, v in st.session_state.book.items():
            with st.expander(k):
                st.write(v)
                tts = gTTS(text=v, lang=st.session_state.lang)
                tmp = NamedTemporaryFile(delete=False, suffix=".mp3")
                tts.save(tmp.name)
                st.audio(tmp.name)
                img = st.session_state.image_cache.get(k)
                if img:
                    st.image(base64_to_pil(img) if isinstance(img, str) else img)

        if st.button("Export EPUB"):
            book = epub.EpubBook()
            book.set_title("NarrativaX Book")
            book.set_language(st.session_state.lang)

            chapters = []
            for title, content in st.session_state.book.items():
                ch = epub.EpubHtml(title=title, file_name=f"{title}.xhtml", lang=st.session_state.lang)
                ch.content = f"<h1>{title}</h1><p>{content}</p>"
                book.add_item(ch)
                chapters.append(ch)
            book.toc = tuple(chapters)
            book.add_item(epub.EpubNcx())
            book.add_item(epub.EpubNav())
            book.spine = ['nav'] + chapters

            tmp = NamedTemporaryFile(delete=False, suffix=".epub")
            epub.write_epub(tmp.name, book)
            with open(tmp.name, "rb") as f:
                st.download_button("📘 Download EPUB", f.read(), file_name="narrativax.epub")

if __name__ == "__main__":
    main()
# END OF FILE
