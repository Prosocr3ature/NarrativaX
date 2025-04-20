# main.py - NarrativaX (Enhanced Version)
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
MAX_TOKENS = 1800
IMAGE_SIZE = (768, 1024)
SAFE_LOADING_MESSAGES = [
    "Sharpening quills...", "Mixing metaphorical ink...",
    "Convincing characters to behave...", "Battling clichés...",
    "Summoning muses...", "Where we're going, we don't need chapters..."
]

# Updated with NSFW options
TONE_MAP = {
    "SFW": {
        "Romantic": "sensual, romantic, literary",
        "Wholesome": "uplifting, warm, feel-good",
        "Suspenseful": "tense, thrilling, page-turning",
        "Philosophical": "deep, reflective, thoughtful",
        "Motivational": "inspirational, personal growth, powerful",
        "Educational": "insightful, informative, structured",
        "Satirical": "humorous, ironic, critical",
        "Professional": "formal, business-like, articulate"
    },
    "NSFW": {
        "Erotic": "explicit, sensual, adult",
        "Kink-Friendly": "taboo, fetish, experimental",
        "Dark Romance": "obsessive, possessive, intense",
        "BDSM": "power dynamics, domination, submission",
        "Taboo": "forbidden, age-gap, forbidden relationships"
    }
}

GENRES = {
    "SFW": [
        "Personal Development", "Business", "Memoir", "Self-Help", "Productivity",
        "Adventure", "Romance", "Sci-Fi", "Mystery", "Fantasy", "Historical Fiction",
        "Philosophy", "Psychology", "Leadership", "Creativity"
    ],
    "NSFW": [
        "Erotica", "Dark Fantasy", "Taboo Romance", "BDSM", "Harem",
        "Omegaverse", "Paranormal Romance", "Reverse Harem", "Urban Fantasy"
    ]
}

IMAGE_MODELS = {
    "SFW": {
        "Realistic Vision v5.1": "lucataco/realistic-vision-v5.1:2c8e954decbf70b7607a4414e5785ef9e4de4b8c51d50fb8b8b349160e0ef6bb"
    },
    "NSFW": {
        "Reliberate V3 (NSFW)": "asiryan/reliberate-v3:d70438fcb9bb7adb8d6e59cf236f754be0b77625e984b8595d1af02cdf034b29",
        "Uber Realistic Porn Merge URPM 1": "ductridev/uber-realistic-porn-merge-urpm-1:1cca487c3bfe167e987fc3639477cf2cf617747cd38772421241b04d27a113a8"
    }
}

LLM_MODELS = {
    "SFW": [
        "openai/gpt-4",
        "anthropic/claude-2"
    ],
    "NSFW": [
        "nothingiisreal/mn-celeste-12b",
        "nousresearch/nous-hermes-llama2-13b",
        "mancer/dolphin-mixtral-8x7b",
        "migtissera/synthia-70b"
    ]
}

# === SESSION STATE ===
for key in ['book', 'outline', 'cover', 'characters', 'gen_progress', 'image_cache', 'story_so_far', 'nsfw_mode']:
    st.session_state.setdefault(key, {} if key in ['image_cache', 'characters'] else None)

# === API CONFIGURATION ===
def validate_api_keys():
    required_keys = ['OPENROUTER_API_KEY', 'REPLICATE_API_TOKEN']
    missing = [key for key in required_keys if not st.secrets.get(key)]
    if missing:
        st.error(f"Missing API keys: {', '.join(missing)}")
        st.stop()

validate_api_keys()
os.environ["REPLICATE_API_TOKEN"] = st.secrets["REPLICATE_API_TOKEN"]

# === NEW CHARACTER SYSTEM ===
def generate_character(genre, tone):
    prompt = f"""Create detailed character profile for {genre} story with {tone} tone:
    - Name
    - Age/Gender
    - Physical Description
    - Personality Traits
    - Backstory
    - Motivations
    - Relationships
    - Character Arc"""
    
    response = call_openrouter(prompt, st.session_state.gen_progress['model'])
    if not response:
        return None
        
    character = {
        "profile": response,
        "image": None,
        "extended": False
    }
    return character

def handle_character_image(character, prompt):
    try:
        image = generate_image(
            f"Character portrait: {prompt}",
            st.session_state.gen_progress['img_model'],
            f"character_{len(st.session_state.characters)}"
        )
        character['image'] = image
    except Exception as e:
        st.error(f"Character image failed: {str(e)}")

# === ENHANCED CHAPTER GENERATION ===
def generate_chapter(chapter_num, is_extension=False):
    config = st.session_state.gen_progress
    story_context = "\n\n".join([
        f"Chapter {i}: {content}"
        for i, content in enumerate(st.session_state.story_so_far, 1)
    ])
    
    character_context = "\n".join([
        f"{char['name']}: {char['profile']}"
        for char in st.session_state.characters.values()
    ]) if st.session_state.characters else ""
    
    # Chapter generation prompt
prompt = f"""Write {'an extension to ' if is_extension else ''}Chapter {chapter_num} for {config['genre']} story.
Story Context: {story_context}
Characters: {character_context}
Tone: {TONE_MAP['NSFW' if st.session_state.nsfw_mode else 'SFW'][config['tone']]}
Include: Detailed scene descriptions, character development, plot progression"""
    
    content = call_openrouter(prompt, config['model'])
    if content:
        if is_extension:
            st.session_state.book[f"Chapter {chapter_num}"] += "\n\n" + content
        else:
            st.session_state.book[f"Chapter {chapter_num}"] = content
        st.session_state.story_so_far.append(content)
        
    return content

# === UPDATED CORE FUNCTIONALITY ===
def generate_book_content():
    config = st.session_state.gen_progress
    progress_bar = st.progress(0)
    
    try:
        # Character Generation
        if st.session_state.characters:
            progress_bar.progress(0.1, text="🎭 Generating character arcs...")
            for char_id, character in st.session_state.characters.items():
                if not character.get('image'):
                    handle_character_image(character, character['profile'])
        
        # Outline Generation with Characters
        outline_prompt = f"""Create {config['chapters']}-chapter outline for {config['genre']} story.
        Characters: {json.dumps(st.session_state.characters)}
        Tone: {TONE_MAP['NSFW' if st.session_state.nsfw_mode else 'SFW'][config['tone']}
        Include: Plot structure, character development milestones, key scenes"""
        
        st.session_state.outline = call_openrouter(outline_prompt, config['model'])
        
        # Chapter Generation with Continuity
        st.session_state.story_so_far = []
        for chapter_num in range(1, config['chapters'] + 1):
            progress = chapter_num/config['chapters']
            progress_bar.progress(progress, text=f"📖 Writing Chapter {chapter_num}")
            generate_chapter(chapter_num)
            
            if not config.get('is_non_fiction'):
                progress_bar.progress(progress + 0.05, text=f"🖼️ Generating chapter art")
                generate_image(
                    f"Scene illustration: {st.session_state.book[f'Chapter {chapter_num}'][:200]}",
                    config['img_model'],
                    f"chapter_{chapter_num}"
                )
        
        progress_bar.progress(1.0, text="✅ Book complete!")
        
    except Exception as e:
        st.error(f"Generation Failed: {str(e)}")
    finally:
        progress_bar.empty()

# === NEW UI COMPONENTS ===
def character_manager():
    with st.expander("🧑🎨 Character Development"):
        col1, col2 = st.columns([3,1])
        with col1:
            new_char_btn = st.button("➕ Create New Character")
        with col2:
            auto_gen = st.checkbox("Auto-Generate", help="Generate characters automatically based on genre")
        
        if new_char_btn or auto_gen:
            with st.spinner("Developing compelling characters..."):
                new_char = generate_character(
                    st.session_state.gen_progress['genre'],
                    st.session_state.gen_progress['tone']
                )
                if new_char:
                    char_id = f"char_{len(st.session_state.characters)+1}"
                    st.session_state.characters[char_id] = new_char
        
        for char_id, character in st.session_state.characters.items():
            with st.container(border=True):
                cols = st.columns([1,4])
                with cols[0]:
                    if character['image']:
                        st.image(character['image'], width=150)
                    else:
                        st.button("🖼️ Generate Image", key=f"{char_id}_img",
                                 on_click=handle_character_image,
                                 args=(character, character['profile']))
                
                with cols[1]:
                    st.markdown(f"**{character.get('name', 'Unnamed')}**")
                    st.write(character['profile'])
                    
                    c1, c2, c3 = st.columns(3)
                    c1.button("✏️ Extend", key=f"{char_id}_extend",
                             help="Add more backstory and details")
                    c2.button("🔄 Regenerate", key=f"{char_id}_regen",
                             help="Create new version of this character")
                    c3.button("❌ Delete", key=f"{char_id}_del",
                             on_click=lambda c=char_id: st.session_state.characters.pop(c))

def chapter_controls():
    st.divider()
    st.subheader("Chapter Management")
    
    for chapter in list(st.session_state.book.keys()):
        col1, col2, col3 = st.columns([4,1,1])
        with col1:
            st.markdown(f"**{chapter}**")
            edited = st.text_area(f"Edit {chapter}", value=st.session_state.book[chapter],
                                height=200, key=f"edit_{chapter}")
            st.session_state.book[chapter] = edited
            
        with col2:
            if st.button(f"🔄 Regenerate {chapter}"):
                with st.spinner(f"Rewriting {chapter}..."):
                    generate_chapter(chapter.split()[-1])
                    st.rerun()
                    
        with col3:
            if st.button(f"✨ Extend {chapter}"):
                with st.spinner(f"Expanding {chapter}..."):
                    generate_chapter(chapter.split()[-1], is_extension=True)
                    st.rerun()

# === UPDATED MAIN INTERFACE ===
def main_interface():
    st.title("NarrativaX — AI-Powered Story Studio")
    
    # NSFW Toggle Sidebar
    with st.sidebar:
        st.header("Configuration")
        st.session_state.nsfw_mode = st.toggle("NSFW Mode", value=False)
        
        # Model Selection
        model_type = "NSFW" if st.session_state.nsfw_mode else "SFW"
        selected_model = st.selectbox(
            "🤖 LLM Model",
            LLM_MODELS[model_type],
            index=0
        )
        
        # Image Model Selection
        img_models = IMAGE_MODELS[model_type]
        selected_img_model = st.selectbox(
            "🖼️ Image Model",
            list(img_models.keys()),
            index=0
        )
    
    # Main Form
    with st.form("story_form"):
        col1, col2 = st.columns(2)
        genre = col1.selectbox(
            "📚 Genre",
            sorted(GENRES[model_type]),
            key="genre_select"
        )
        tone = col2.selectbox(
            "🎭 Tone",
            sorted(TONE_MAP[model_type].keys()),
            key="tone_select"
        )
        
        prompt = st.text_area("✨ Story Premise", height=120,
                            placeholder="A dystopian society where emotions are controlled...")
        chapters = st.slider("📖 Chapters", 3, 50, 12)
        
        if st.form_submit_button("🚀 Generate Story"):
            st.session_state.gen_progress = {
                "prompt": prompt,
                "genre": genre,
                "tone": tone,
                "chapters": chapters,
                "model": selected_model,
                "img_model": selected_img_model
            }
            generate_book_content()
    
    # Character Management
    character_manager()
    
    # Generated Content Display
    if st.session_state.get('book'):
        chapter_controls()
        
        # Export System
        with st.sidebar:
            st.download_button("📥 Export Book", 
                              data=create_export_zip(),
                              file_name="narrativax_story.zip",
                              mime="application/zip")
            
            if st.button("🧹 Reset Session"):
                st.session_state.clear()
                st.rerun()

if __name__ == "__main__":
    main_interface()
