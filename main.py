# main.py - NarrativaX
import os
import json
import requests
import zipfile
import random
import replicate
import base64
import time
import warnings
from html import escape
from docx import Document
from docx.shared import Inches
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from tempfile import NamedTemporaryFile
from gtts import gTTS
from PIL import Image
from io import BytesIO
import streamlit as st

# === CONSTANTS ===
FONT_PATHS = {
    "regular": "fonts/NotoSans-Regular.ttf",
    "bold": "fonts/NotoSans-Bold.ttf"
}
MAX_TOKENS = 2500
IMAGE_SIZE = (768, 1024)
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
    "Explicit": "graphic, sexually explicit, adult content",
    "Provocative": "suggestive, tantalizing, boundary-pushing",
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
    "Decision-Making", "Public Speaking", "Mental Clarity",
    "Erotic Romance", "BDSM", "Taboo Fantasy", "Adult Comedy",
    "Sexual Education", "Kink Exploration", "Polyamory Studies"
]

IMAGE_MODELS = {
    "Realistic Vision v5.1": "lucataco/realistic-vision-v5.1:2c8e954decbf70b7607a4414e5785ef9e4de4b8c51d50fb8b8b349160e0ef6bb",
    "Reliberate V3 (NSFW)": "asiryan/reliberate-v3:d70438fcb9bb7adb8d6e59cf236f754be0b77625e984b8595d1af02cdf034b29",
    "AbsoluteReality v1.8.1": "lucataco/absolutereality-v1-8-1:1db0b52c6b8325956a5c1d0ae2d97363212f2d0d5f1e5e2c7d2b2c6c048d0f1"
}

ADULT_MODELS = [
    "leptonai/llama3-70b",
    "cognitivecomputations/dolphin-2.6-mistral-7b",
    "openchat/openchat-7b",
    "undi95/remm-slerp-l2-13b"
]

# === SESSION STATE ===
for key in ['book', 'outline', 'cover', 'characters', 'gen_progress', 'image_cache', 'adult_mode']:
    st.session_state.setdefault(key, {} if key == 'image_cache' else None)

# === API CONFIGURATION ===
def validate_api_keys():
    required_keys = ['OPENROUTER_API_KEY', 'REPLICATE_API_TOKEN']
    missing = [key for key in required_keys if key not in st.secrets]
    if missing:
        st.error(f"Missing API keys in secrets: {', '.join(missing)}")
        st.stop()

validate_api_keys()
os.environ["REPLICATE_API_TOKEN"] = st.secrets["REPLICATE_API_TOKEN"]

# === ENHANCED FUNCTIONALITY ===
def generate_continuation(chapter_num):
    previous_content = "\n".join([st.session_state.book[f"Chapter {i}"] for i in range(1, chapter_num)])
    prompt = f"Continue Chapter {chapter_num} maintaining continuity with previous content:\n{previous_content}\n\nNew content:"
    return call_openrouter(prompt, st.session_state.gen_progress['model'])

def regenerate_chapter(chapter_num):
    chapter_key = f"Chapter {chapter_num}"
    prompt = f"Rewrite {chapter_key} with different approach. Current content:\n{st.session_state.book[chapter_key]}"
    return call_openrouter(prompt, st.session_state.gen_progress['model'])

def handle_image_prompt(prompt):
    if st.session_state.adult_mode:
        return f"{prompt} [NSFW, explicit sexual content, detailed anatomy]"
    return prompt

# === MODIFIED CORE FUNCTIONALITY ===
def generate_book_content():
    config = st.session_state.gen_progress
    genre = config['genre']
    is_dev = genre in ["Personal Development", "Self-Help", "Productivity"]
    progress_bar = st.progress(0)
    
    try:
        total_steps = 4 + (config['chapters'] * (2 if is_dev else 3))
        current_step = 0
        
        # Premise Generation
        current_step += 1
        progress_bar.progress(current_step/total_steps, text="🌟 Building your book idea...")
        premise = call_openrouter(
            f"Develop a {genre} book idea: {escape(config['prompt'])}",
            config['model']
        )
        if not premise:
            raise Exception("Failed to generate premise")
        
        # Enhanced Outline Generation
        current_step += 1
        progress_bar.progress(current_step/total_steps, text="🗂️ Generating detailed outline...")
        outline_prompt = (
            f"Write comprehensive non-fiction outline for {genre} book with chapter progression. Prompt: {config['prompt']}. Tone: {TONE_MAP[config['tone']]}"
            if is_dev else
            f"Create detailed fictional outline for {TONE_MAP[config['tone']]} {genre} story. Include 5-7 plot points per chapter and character development arcs."
        )
        st.session_state.outline = call_openrouter(outline_prompt, config['model'])
        if not st.session_state.outline:
            raise Exception("Failed to generate outline")
        
        # Chapter Generation with Continuity
        book = {}
        previous_content = ""
        for chapter_num in range(1, config['chapters'] + 1):
            current_step += 1
            progress_text = random.choice(SAFE_LOADING_MESSAGES)
            progress_bar.progress(current_step/total_steps, text=f"✍️ Writing Chapter {chapter_num}... {progress_text}")
            
            chapter_prompt = (
                f"Write Chapter {chapter_num} for {genre} book. Previous content: {previous_content}\nOutline: {st.session_state.outline}"
                if is_dev else
                f"Write Chapter {chapter_num} for {genre} story. Previous content: {previous_content}\nOutline: {st.session_state.outline}"
            )
            content = call_openrouter(chapter_prompt, config['model'])
            if not content:
                continue
                
            book[f"Chapter {chapter_num}"] = content
            previous_content += f"\n\nChapter {chapter_num}:\n{content}"
            
            if not is_dev:
                current_step += 1
                progress_bar.progress(current_step/total_steps, text=f"🖼️ Creating image for Chapter {chapter_num}")
                generate_image(
                    handle_image_prompt(f"{content[:200]} {TONE_MAP[config['tone']]}"),
                    config["img_model"],
                    f"chapter_{chapter_num}"
                )
        
        # Finalization
        current_step += 1
        progress_bar.progress(current_step/total_steps, text="📕 Creating cover art...")
        st.session_state.cover = generate_image(
            handle_image_prompt(f"Cover art for {genre} book: {premise}"), 
            config["img_model"], 
            "cover"
        )
        
        st.session_state.book = book
        progress_bar.progress(1.0, text="✅ Book generation complete!")
        time.sleep(2)
        
    except Exception as e:
        st.error(f"Generation Failed: {str(e)}")
        progress_bar.progress(0.0, text="❌ Generation aborted")
    finally:
        progress_bar.empty()

# === MODIFIED MAIN INTERFACE ===
def main_interface():
    try:
        verify_fonts()
    except FileNotFoundError as e:
        st.error("System configuration error. Missing font files. Please contact support.")
        st.stop()

    st.title("NarrativaX — AI-Powered Book Creator")
    
    # Adult Mode Toggle
    st.session_state.adult_mode = st.sidebar.checkbox("🔞 Adult Mode", value=False)
    
    with st.form("book_form"):
        col_main = st.columns([3, 1])
        with col_main[0]:
            prompt = st.text_area("🖋️ Your Idea or Prompt", height=120, 
                                 placeholder="E.g. How to build unstoppable self-discipline...")
        
        # Dynamic Content Filtering
        filtered_genres = [g for g in GENRES if ("NSFW" not in g and "Erotic" not in g) 
                          if not st.session_state.adult_mode else GENRES]
        filtered_tones = [t for t in TONE_MAP if t not in ["NSFW", "Explicit", "Provocative"] 
                         if not st.session_state.adult_mode else TONE_MAP]
        
        col1, col2 = st.columns(2)
        genre = col1.selectbox("📚 Choose Genre", sorted(set(filtered_genres)))
        tone = col2.selectbox("🎭 Choose Tone", filtered_tones)
        
        chapters = st.slider("📖 Number of Chapters", 3, 50, 10)
        
        col3, col4 = st.columns(2)
        model_list = ADULT_MODELS + ["nothingiisreal/mn-celeste-12b", "openai/gpt-4"] if st.session_state.adult_mode else ["nothingiisreal/mn-celeste-12b", "openai/gpt-4"]
        model = col3.selectbox("🤖 LLM", model_list)
        img_model = col4.selectbox("🖼️ Image Model", list(IMAGE_MODELS.keys()))
        
        if st.form_submit_button("🚀 Create Book"):
            if not prompt.strip():
                st.warning("Please enter your idea or prompt.")
            else:
                st.session_state.image_cache.clear()
                st.session_state.gen_progress = {
                    "prompt": prompt, 
                    "genre": genre, 
                    "tone": tone,
                    "chapters": chapters, 
                    "model": model, 
                    "img_model": img_model
                }
                generate_book_content()

    if st.session_state.book:
        st.header("📚 Generated Content")
        
        tabs = st.tabs(["Chapters", "Outline", "Export"])
        
        with tabs[0]:
            for chapter, content in st.session_state.book.items():
                with st.expander(chapter):
                    col1, col2 = st.columns([3, 2])
                    with col1:
                        st.write(content)
                        col_btns = st.columns([1,1,2])
                        if col_btns[0].button(f"🔄 Regenerate {chapter}", key=f"reg_{chapter}"):
                            new_content = regenerate_chapter(int(chapter.split()[-1]))
                            if new_content:
                                st.session_state.book[chapter] = new_content
                                st.rerun()
                        if col_btns[1].button(f"🔗 Extend {chapter}", key=f"ext_{chapter}"):
                            extended_content = generate_continuation(int(chapter.split()[-1]))
                            if extended_content:
                                st.session_state.book[chapter] += "\n\n" + extended_content
                                st.rerun()
                        with NamedTemporaryFile(suffix=".mp3") as fp:
                            tts = gTTS(text=content, lang='en')
                            tts.save(fp.name)
                            st.audio(fp.name)
                    with col2:
                        image_key = f"chapter_{chapter.split()[-1]}"
                        if image_key in st.session_state.image_cache:
                            st.image(st.session_state.image_cache[image_key])
        
        with tabs[1]:
            st.markdown("### Book Outline")
            st.write(st.session_state.outline)
            if st.button("🔄 Regenerate Outline"):
                del st.session_state.outline
                generate_book_content()
        
        with tabs[2]:
            st.download_button(
                label="📥 Download Complete Book",
                data=open(create_export_zip(), "rb").read(),
                file_name="narrativax_book.zip",
                mime="application/zip"
            )
            if st.button("🧹 Clear Session"):
                st.session_state.clear()
                st.rerun()

# === RUN APPLICATION ===
if __name__ == "__main__":
    main_interface()
