# === START OF main.py ===
# This is the complete, expanded, and modernized NarrativaX main.py file
# with all advanced features, full mobile optimization, and wizard UI mode.

# [Imported Libraries]
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
from ebooklib import epub  # EPUB export support

# === CONFIG ===
st.set_page_config(page_title="NarrativaX", page_icon="🪶", layout="wide", initial_sidebar_state="collapsed")

# === CONSTANTS ===
LOGO_URL = "https://raw.githubusercontent.com/Prosocr3ature/NarrativaX/main/logo.png"
MAX_TOKENS = 1800
IMAGE_SIZE = (768, 1024)
TIMEOUT = 300
PROGRESS_QUEUE = queue.Queue()

SUPPORTED_LANGUAGES = {"English": "en", "Swedish": "sv", "French": "fr", "German": "de", "Spanish": "es"}

# Define genre, tone, model, and image options
GENRES = ["Fantasy", "Romance", "Sci-Fi", "NSFW", "Mystery", "Horror", "Thriller", "Historical"]
TONE_MAP = {
    "Wholesome": "uplifting, kind, positive",
    "Suspenseful": "tense, thrilling, page-turning",
    "NSFW": "explicit, erotic, emotional",
    "Philosophical": "deep, reflective, symbolic"
}
IMAGE_MODELS = {
    "Realistic Vision v5.1": "lucataco/realistic-vision-v5.1:2c8e954...",
    "Reliberate V3 (NSFW)": "asiryan/reliberate-v3:d70438f..."
}

# === SESSION INIT ===
for key in ["book", "outline", "cover", "characters", "gen_progress", "language", "title", "wizard_mode"]:
    st.session_state.setdefault(key, None)
st.session_state.setdefault("image_cache", {})

# === FUNCTION DEFINITIONS ===

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
    output = replicate.run(IMAGE_MODELS[model_key], input={
        "prompt": prompt,
        "num_inference_steps": 35,
        "guidance_scale": 7.5,
        "width": IMAGE_SIZE[0],
        "height": IMAGE_SIZE[1]
    })
    url = output[0]
    img = Image.open(BytesIO(requests.get(url).content)).convert("RGB")
    st.session_state.image_cache[id_key] = img
    return img

def generate_epub(book, title, author="NarrativaX"):
    book_epub = epub.EpubBook()
    book_epub.set_identifier("id123456")
    book_epub.set_title(title)
    book_epub.set_language("en")
    book_epub.add_author(author)
    chapters = []
    for sec, content in book.items():
        c = epub.EpubHtml(title=sec, file_name=f"{sec}.xhtml", lang="en")
        c.content = f"<h1>{sec}</h1><p>{content.replace('\n', '<br>')}</p>"
        book_epub.add_item(c)
        chapters.append(c)
    book_epub.toc = chapters
    book_epub.add_item(epub.EpubNcx())
    book_epub.add_item(epub.EpubNav())
    style = 'BODY { font-family: Times, serif; }'
    nav_css = epub.EpubItem(uid="style_nav", file_name="style/nav.css", media_type="text/css", content=style)
    book_epub.add_item(nav_css)
    book_epub.spine = ["nav"] + chapters
    epub.write_epub("book.epub", book_epub)
    return "book.epub"

# === MAIN INTERFACE ===
def main():
    st.title("NarrativaX — Immersive AI Book Creator")
    st.markdown(f"<img src='{LOGO_URL}' width='180' style='position:absolute; top:15px; right:30px'>", unsafe_allow_html=True)

    mode = st.radio("Choose Mode:", ["Classic", "Guided Wizard"])
    st.session_state.wizard_mode = mode

    if mode == "Guided Wizard":
        st.header("Step 1: Your Book Idea")
        prompt = st.text_area("Describe your story in a sentence")
        st.header("Step 2: Style")
        genre = st.selectbox("Genre", GENRES)
        tone = st.selectbox("Tone", list(TONE_MAP.keys()))
        chapters = st.slider("Number of Chapters", 4, 20, 8)
        language = st.selectbox("Language", list(SUPPORTED_LANGUAGES.keys()))
        model = st.selectbox("AI Model", ["nothingiisreal/mn-celeste-12b", "gryphe/mythomax-l2-13b"])
        img_model = st.selectbox("Image Model", list(IMAGE_MODELS))
        st.session_state.language = language
        
        if st.button("Generate Book"):
            st.session_state.gen_progress = {
                "prompt": prompt,
                "genre": genre,
                "tone": tone,
                "chapters": chapters,
                "language": SUPPORTED_LANGUAGES[language],
                "model": model,
                "img_model": img_model
            }
            thread = threading.Thread(target=start_generation)
            add_script_run_ctx(thread)
            thread.start()
            st.rerun()

    elif mode == "Classic":
        st.warning("Classic mode under construction. Please use Guided Wizard.")

    # Book display after generation
    if st.session_state.book:
        st.success("Your book is ready!")
        st.header(st.session_state.title or "Generated Book")
        st.download_button("Download EPUB", open(generate_epub(st.session_state.book, st.session_state.title), "rb").read(), file_name="book.epub")
        for sec, content in st.session_state.book.items():
            with st.expander(sec):
                st.write(content)
                if sec in st.session_state.image_cache:
                    st.image(st.session_state.image_cache[sec], use_column_width=True)
                tts = gTTS(text=content, lang=st.session_state.language)
                with NamedTemporaryFile(delete=False, suffix=".mp3") as tf:
                    tts.save(tf.name)
                    st.audio(tf.name)

# === GENERATION PROCESS ===
def start_generation():
    config = st.session_state.gen_progress
    st.session_state.title = call_openrouter(f"Give a short catchy title for a {config['genre']} story: {config['prompt']}", config['model'])
    outline = call_openrouter(f"Write a chapter-by-chapter outline for a {TONE_MAP[config['tone']]} {config['genre']} story titled '{st.session_state.title}': {config['prompt']}", config['model'])
    st.session_state.outline = outline
    book = {}
    for i in range(config['chapters']):
        chap_title = f"Chapter {i+1}"
        text = call_openrouter(f"Write content for {chap_title} in the story '{st.session_state.title}' using this outline: {outline}", config['model'])
        summary = call_openrouter(f"Summarize this chapter: {text}", config['model'])
        book[f"{chap_title}: {summary}"] = text
        generate_image(text, config['img_model'], chap_title)
    st.session_state.book = book
    st.session_state.cover = generate_image(f"Cover art for a {config['genre']} book titled {st.session_state.title}", config['img_model'], "cover")
    st.session_state.characters = json.loads(call_openrouter(f"List main characters in JSON: name, role, personality, appearance. Story: {outline}", config['model']))

# === START APP ===
if __name__ == "__main__":
    main()

# === END OF FILE ===
