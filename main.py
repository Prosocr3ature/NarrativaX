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

# Simplified setup to only demonstrate the final display_content() function
st.set_page_config(page_title="NarrativaX", page_icon="🪶", layout="wide")

def pil_to_base64(image: Image.Image) -> str:
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

def base64_to_pil(b64_str: str) -> Image.Image:
    return Image.open(BytesIO(base64.b64decode(b64_str)))

def display_content():
    try:
        if st.session_state.book:
            st.header("📖 Your Generated Book")

            # Cover
            with st.expander("📔 Book Cover", expanded=True):
                if st.session_state.cover:
                    st.image(st.session_state.cover, use_container_width=True)
                else:
                    st.warning("No cover image available.")

            # Outline
            with st.expander("📝 Full Outline", expanded=False):
                if st.session_state.outline:
                    st.code(st.session_state.outline, language="markdown")
                else:
                    st.warning("No outline available.")

            # Characters
            with st.expander("👥 Character Bios", expanded=False):
                if st.session_state.characters:
                    for char in st.session_state.characters:
                        with st.container():
                            cols = st.columns([1, 3])
                            cols[0].subheader(escape(char.get("name", "Unnamed")))
                            cols[1].markdown(f"""
                                **Role:** {escape(char.get('role', 'Unknown'))}  
                                **Personality:** {escape(char.get('personality', 'N/A'))}  
                                **Appearance:** {escape(char.get('appearance', 'Not specified'))}
                            """)
                else:
                    st.warning("No characters available.")

            # Sections
            for section, content in st.session_state.book.items():
                with st.expander(f"📜 {escape(section)}", expanded=False):
                    col1, col2 = st.columns([3, 2])
                    with col1:
                        st.markdown(f"##### {escape(section)}")
                        st.write(escape(content))

                        # Audio playback
                        with NamedTemporaryFile(suffix=".mp3") as tf:
                            tts = gTTS(text=content, lang='en')
                            tts.save(tf.name)
                            st.audio(tf.name, format="audio/mp3")

                    with col2:
                        img = st.session_state.image_cache.get(section)
                        if img:
                            if isinstance(img, str):
                                img = base64_to_pil(img)
                            st.image(img, use_container_width=True)
                        else:
                            st.warning("No image for this section.")
    except Exception as e:
        st.error(f"⚠️ Content Error: {escape(str(e))[:200]}...")

# Dummy session state for standalone testing (remove for production)
st.session_state.book = {"Foreword": "This is the foreword text.", "Chapter 1": "Once upon a time..."}
st.session_state.outline = "This is a sample outline for your story."
st.session_state.cover = None
st.session_state.characters = [{"name": "Alice", "role": "Protagonist", "personality": "Brave", "appearance": "Tall with red hair."}]
st.session_state.image_cache = {}

display_content()
def main_interface():
    try:
        st.title("NarrativaX — Immersive AI Book Creator")
        st.markdown("Let your imagination take the lead...")

        with st.container():
            prompt = st.text_area("🖋️ Your Story Concept", height=120,
                                  placeholder="A forbidden romance between a vampire and a demon lord...")
            col1, col2, col3 = st.columns(3)
            genre = col1.selectbox("📖 Genre", GENRES)
            tone = col2.selectbox("🎨 Tone", list(TONE_MAP))
            chapters = col3.slider("📚 Chapters", 4, 30, 10)
            model = col1.selectbox("🤖 AI Model", ["nothingiisreal/mn-celeste-12b", "gryphe/mythomax-l2-13b"])
            img_model = col2.selectbox("🖼️ Image Model", list(IMAGE_MODELS))

            if st.button("🚀 Create Book", use_container_width=True):
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
        st.error(f"Application Error: {escape(str(e))[:200]}...")
        st.session_state.gen_progress = None
        st.stop()

def render_sidebar():
    try:
        with st.sidebar:
            st.image(LOGO_URL, width=200)

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

    except Exception as e:
        st.error(f"Sidebar Error: {escape(str(e))[:200]}...")

def display_content():
    try:
        if st.session_state.book:
            st.header("Your Generated Book")

            if st.session_state.cover:
                st.image(st.session_state.cover, caption="Book Cover", use_container_width=True)

            st.markdown("### Outline\n```\n" + escape(st.session_state.outline) + "\n```")

            st.markdown("### Characters")
            for char in st.session_state.characters:
                st.markdown(f"""
                **{escape(char.get('name', 'Unnamed'))}**  
                *Role:* {escape(char.get('role', 'Unknown'))}  
                *Personality:* {escape(char.get('personality', 'N/A'))}  
                *Appearance:* {escape(char.get('appearance', 'Not specified'))}
                """)

            for section, content in st.session_state.book.items():
                with st.expander(f"📜 {escape(section)}"):
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
                            st.image(img, use_container_width=True)
                        else:
                            st.warning("No image for this section")
    except Exception as e:
        st.error(f"Display Error: {escape(str(e))[:200]}...")

def progress_animation():
    try:
        if not PROGRESS_QUEUE.empty():
            status = PROGRESS_QUEUE.get()
            with st.empty() as container:
                while True:
                    if status[0] == "COMPLETE":
                        st.success("Done!")
                        st.balloons()
                        break
                    elif status[0] == "ERROR":
                        st.error(f"🚨 {escape(str(status[1]))[:200]}...")
                        break
                    else:
                        emoji, message, progress, preview = status
                        safe_preview = escape(str(preview))[:150] + "..." if preview else ""
                        container.markdown(f"""
                            <div style="text-align: center; padding: 2rem">
                                <div style="font-size: 3rem">{emoji}</div>
                                <h3>{escape(message)}</h3>
                                <progress value="{progress}" max="1" style="width: 100%; height: 10px"></progress>
                                {f"<div style='margin-top:1em;'>{safe_preview}</div>" if preview else ""}
                            </div>
                        """, unsafe_allow_html=True)
                    try:
                        status = PROGRESS_QUEUE.get(timeout=0.1)
                    except queue.Empty:
                        break
    except Exception as e:
        st.error(f"Animation Error: {escape(str(e))[:200]}...")

# ========== ENTRY POINT ==========
if __name__ == "__main__":
    if st.session_state.get("gen_progress"):
        dramatic_logo()
        progress_animation()
        time.sleep(0.1)
        st.experimental_rerun()
    else:
        main_interface()
        render_sidebar()
        display_content()

    st.markdown("""
    <style>
        .stTextArea textarea {
            font-size: 16px !important;
        }
        .stProgress > div > div > div {
            background-color: #ff69b4 !important;
        }
    </style>
    """, unsafe_allow_html=True)
