# main.py - NarrativaX Enhanced
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
    # Normal tones
    "Wholesome": "uplifting, warm, feel-good",
    "Suspenseful": "tense, thrilling, page-turning",
    "Philosophical": "deep, reflective, thoughtful",
    "Motivational": "inspirational, personal growth, powerful",
    "Educational": "insightful, informative, structured",
    "Professional": "formal, business-like, articulate",
    # Adult tones
    "NSFW": "explicit, erotic, adult",
    "Graphic": "visceral, detailed, intense",
    "Kinky": "fetish, BDSM, power dynamics",
    "Taboo": "forbidden, controversial, transgressive",
    "Sensual": "slow-burn, intimate, passionate"
}

GENRES = [
    # Normal genres
    "Personal Development", "Business", "Memoir", "Self-Help", "Productivity",
    "Adventure", "Romance", "Sci-Fi", "Mystery", "Fantasy", "Horror",
    "Historical Fiction", "Philosophy", "Psychology",
    # Adult genres
    "Erotica", "BDSM", "Taboo Romance", "LGBTQ+ Erotica", "Harem",
    "Omegaverse", "Dark Romance", "Fantasy Erotica", "Historical Smut",
    "Bisexual Fiction", "Polyamory", "Fetish Exploration"
]

IMAGE_MODELS = {
    "Realistic Vision v5.1": "lucataco/realistic-vision-v5.1:2c8e954decbf70b7607a4414e5785ef9e4de4b8c51d50fb8b8b349160e0ef6bb",
    "Reliberate V3 (NSFW)": "asiryan/reliberate-v3:d70438fcb9bb7adb8d6e59cf236f754be0b77625e984b8595d1af02cdf034b29",
    "AbsoluteReality v1.8.1": "lucataco/absolutereality-v1.8.1:1dfa0b8a474d55f4d6f9c0e1e7a9d5c09f2d8940d13b8f2a8d00a8673c1b115b3"
}

ADULT_MODELS = {
    "KoboldAI/Psyfighter-13B": "koboldai/psyfighter-13b",
    "Mancer/Weaver (Alpha)": "mancer/weaver",
    "MythoMax-L2-13B": "mythomax-l2-13b"
}

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
    previous_content = st.session_state.book.get(f"Chapter {chapter_num}", "")
    prompt = f"Continue and expand this chapter, maintaining continuity:\n{previous_content}"
    new_content = call_openrouter(prompt, st.session_state.gen_progress['model'])
    if new_content:
        st.session_state.book[f"Chapter {chapter_num}"] += "\n\n" + new_content

def regenerate_chapter(chapter_num):
    chapter_key = f"Chapter {chapter_num}"
    previous_content = st.session_state.book.get(chapter_key, "")
    prompt = f"Rewrite this chapter with different execution but same plot points:\n{previous_content}"
    new_content = call_openrouter(prompt, st.session_state.gen_progress['model'])
    if new_content:
        st.session_state.book[chapter_key] = new_content

def generate_character_bios():
    prompt = f"Generate detailed character profiles for: {', '.join(st.session_state.characters.keys())}"
    bios = call_openrouter(prompt, st.session_state.gen_progress['model'])
    st.session_state.characters = json.loads(bios) if bios else {}

# === MODIFIED CORE FUNCTIONALITY ===
def generate_book_content():
    config = st.session_state.gen_progress
    genre = config['genre']
    is_dev = genre in ["Personal Development", "Self-Help", "Productivity"]
    progress_bar = st.progress(0)
    
    try:
        total_steps = 5 + (config['chapters'] * (3 if is_dev else 4))
        current_step = 0
        
        # Character Development
        if st.session_state.characters:
            current_step += 1
            progress_bar.progress(current_step/total_steps, text="🎭 Developing characters...")
            generate_character_bios()
        
        # Premise Generation
        current_step += 1
        progress_bar.progress(current_step/total_steps, text="🌟 Building your book idea...")
        premise_prompt = f"Develop a {genre} book idea: {escape(config['prompt'])}"
        if st.session_state.characters:
            premise_prompt += f"\nCharacters: {json.dumps(st.session_state.characters)}"
        premise = call_openrouter(premise_prompt, config['model'])
        
        # Enhanced Outline Generation
        current_step += 1
        progress_bar.progress(current_step/total_steps, text="🗂️ Generating detailed outline...")
        outline_prompt = f"""
        Create a detailed {genre} outline with:
        - 3-5 key plot points per chapter
        - Character development arcs
        - Thematic progression
        - Setup/payoff structure
        Genre: {genre}
        Premise: {premise}
        Tone: {TONE_MAP[config['tone']]}
        """
        st.session_state.outline = call_openrouter(outline_prompt, config['model'])
        
        # Chapter Generation with Continuity
        book = {}
        previous_chapter = ""
        for chapter_num in range(1, config['chapters'] + 1):
            current_step += 1
            progress_text = random.choice(SAFE_LOADING_MESSAGES)
            progress_bar.progress(current_step/total_steps, text=f"✍️ Writing Chapter {chapter_num}... {progress_text}")
            
            chapter_prompt = f"""
            Write Chapter {chapter_num} for: {genre}
            Outline: {st.session_state.outline}
            Previous Chapter: {previous_chapter[:1000]}
            Tone: {TONE_MAP[config['tone']}
            {"Include explicit content" if st.session_state.adult_mode else ""}
            """
            content = call_openrouter(chapter_prompt, config['model'])
            if content:
                book[f"Chapter {chapter_num}"] = content
                previous_chapter = content
            
            # Image Generation
            if not is_dev:
                current_step += 1
                progress_bar.progress(current_step/total_steps, text=f"🖼️ Creating image for Chapter {chapter_num}")
                img_prompt = f"{content[:200]} {TONE_MAP[config['tone']]}"
                if st.session_state.adult_mode:
                    img_prompt += " (NSFW:1.3)"
                generate_image(img_prompt, config["img_model"], f"chapter_{chapter_num}")

        # Finalization
        current_step += 1
        progress_bar.progress(current_step/total_steps, text="📕 Creating cover art...")
        cover_prompt = f"Cover art for {genre} book: {premise}"
        if st.session_state.adult_mode:
            cover_prompt += " (NSFW, erotic)"
        st.session_state.cover = generate_image(cover_prompt, config["img_model"], "cover")
        
        st.session_state.book = book
        progress_bar.progress(1.0, text="✅ Book generation complete!")
        time.sleep(2)
        
    except Exception as e:
        st.error(f"Generation Failed: {str(e)}")
    finally:
        progress_bar.empty()

# === MODIFIED MAIN INTERFACE ===
def main_interface():
    st.title("NarrativaX — Enhanced AI Book Creator")
    
    # Adult Mode Toggle
    st.session_state.adult_mode = st.sidebar.checkbox("🔞 Adult Mode", 
        help="Enable NSFW content generation")
    
    with st.form("book_form"):
        col_main = st.columns([3, 1])
        prompt = col_main[0].text_area("🖋️ Your Idea or Prompt", height=120,
            placeholder="E.g. A forbidden romance between a knight and dragon shapeshifter...")
        
        # Character Creation
        with col_main[1].expander("🧑‍🎨 Add Characters"):
            char_name = st.text_input("Name")
            char_desc = st.text_input("Description")
            if st.button("Add Character"):
                if char_name and char_desc:
                    st.session_state.characters[char_name] = char_desc
        
        # Dynamic Filters
        col_filters = st.columns(2)
        available_genres = [g for g in GENRES if ("Erotica" not in g and "BDSM" not in g) 
                          if not st.session_state.adult_mode else GENRES]
        available_tones = [t for t in TONE_MAP.keys() if t not in ["NSFW", "Graphic"] 
                         if not st.session_state.adult_mode else TONE_MAP.keys()]
        
        genre = col_filters[0].selectbox("📚 Genre", sorted(available_genres))
        tone = col_filters[1].selectbox("🎭 Tone", available_tones)
        
        # Model Selection
        col_models = st.columns(2)
        available_llms = ["nothingiisreal/mn-celeste-12b", "openai/gpt-4"] + (
            list(ADULT_MODELS.keys()) if st.session_state.adult_mode else [])
        available_img_models = ["Realistic Vision v5.1", "AbsoluteReality v1.8.1"] + (
            ["Reliberate V3 (NSFW)"] if st.session_state.adult_mode else [])
        
        model = col_models[0].selectbox("🤖 LLM", available_llms)
        img_model = col_models[1].selectbox("🖼️ Image Model", available_img_models)
        
        # Chapter Controls
        chapters = st.slider("📖 Chapters", 3, 50, 12,
            help="For complex stories, 15-25 chapters recommended")
        
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

    # Display Generated Content
    if st.session_state.book:
        st.header("📚 Generated Content")
        tabs = st.tabs(["Chapters", "Outline", "Characters", "Export"])
        
        with tabs[0]:
            for chapter in sorted(st.session_state.book.keys()):
                with st.expander(chapter):
                    col_chapter = st.columns([4, 1])
                    chapter_num = int(chapter.split()[-1])
                    
                    with col_chapter[0]:
                        st.write(st.session_state.book[chapter])
                        st.download_button(
                            label=f"📥 Download {chapter}",
                            data=st.session_state.book[chapter],
                            file_name=f"{chapter.lower().replace(' ', '_')}.txt"
                        )
                        
                        col_actions = st.columns(2)
                        col_actions[0].button(
                            "🔄 Regenerate", key=f"reg_{chapter_num}",
                            on_click=regenerate_chapter, args=(chapter_num,)
                        )
                        col_actions[1].button(
                            "🔁 Continue", key=f"cont_{chapter_num}",
                            on_click=generate_continuation, args=(chapter_num,)
                        )
                    
                    with col_chapter[1]:
                        image_key = f"chapter_{chapter_num}"
                        if image_key in st.session_state.image_cache:
                            st.image(st.session_state.image_cache[image_key])
        
        with tabs[1]:
            st.markdown("### Book Outline")
            st.write(st.session_state.outline)
        
        with tabs[2]:
            st.markdown("### Character Profiles")
            for char, desc in st.session_state.characters.items():
                with st.expander(char):
                    st.write(desc)
        
        with tabs[3]:
            with st.spinner("📦 Packing your masterpiece..."):
                zip_path = create_export_zip()
                st.download_button(
                    label="📥 Download Complete Package",
                    data=open(zip_path, "rb").read(),
                    file_name="narrativax_book.zip",
                    mime="application/zip"
                )
            if st.button("🧹 Clear Session"):
                st.session_state.clear()
                st.rerun()

if __name__ == "__main__":
    main_interface()
