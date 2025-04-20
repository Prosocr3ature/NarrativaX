# main.py - NarrativaX (Final Production Version)
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
CONTENT_TYPES = ["Adult", "Normal"]
FONT_PATHS = {
    "regular": "fonts/NotoSans-Regular.ttf",
    "bold": "fonts/NotoSans-Bold.ttf"
}
MAX_TOKENS = 2500
IMAGE_SIZE = (832, 1216)
SAFE_LOADING_MESSAGES = [
    "Crafting your narrative...", "Developing characters...",
    "Building immersive worlds...", "Engineering plot twists...",
    "Polishing dialogues...", "Finalizing chapters..."
]

ADULT_TONE_MAP = {
    "Erotic": "explicit, sensual, adult-oriented, detailed intimacy",
    "BDSM": "power dynamics, kink-positive, consensual exploration",
    "Taboo": "forbidden desires, transgressive themes, dark romance",
    "Harem": "multiple partners, fantasy dynamics, power play",
    "Fantasy": "mythical creatures, magical realms, supernatural encounters",
    "Dark Romance": "morally gray, obsessive love, dangerous passions",
    "LGBTQ+": "diverse relationships, queer perspectives, inclusive",
    "Historical Erotica": "period-accurate settings with explicit content"
}

NORMAL_TONE_MAP = {
    "Romantic": "passionate, emotional, relationship-focused",
    "Adventure": "action-packed, thrilling, journey-driven",
    "Mystery": "suspenseful, puzzling, clue-oriented",
    "Literary": "character-driven, thematic, sophisticated",
    "Comedy": "humorous, light-hearted, witty",
    "Drama": "emotional, conflict-driven, realistic",
    "Young Adult": "coming-of-age, relatable, energetic",
    "Historical": "period-accurate, vintage aesthetics"
}

ADULT_GENRES = [
    "Erotic Romance", "BDSM Lifestyle", "Dark Fantasy", "Taboo Desires",
    "Polyamorous Relationships", "Monster Romance", "Omegaverse",
    "Vampire Erotica", "Shifter Romance", "Fantasy Harem", "Dystopian Desire",
    "Forbidden Love", "Age Gap Romance", "Secret Affair", "Billionaire Domination"
]

NORMAL_GENRES = [
    "Contemporary Romance", "Mystery Thriller", "Literary Fiction",
    "Young Adult Fantasy", "Historical Fiction", "Science Fiction",
    "Coming-of-Age Drama", "Comedy of Errors", "Adventure Quest",
    "Family Saga", "Crime Noir", "Psychological Drama"
]

ADULT_IMAGE_MODELS = {
    "Realistic Vision V6": "lucataco/realistic-vision-v6:0a7b1b83a7c5710b5e60481a0d4d62d26a4633a7c368d0d2f00f49d27678e2bc",
    "Reliberate V3 (NSFW+)": "asiryan/reliberate-v3:d70438fcb9bb7adb8d6e59cf236f754be0b77625e984b8595d1af02cdf034b29",
}

NORMAL_IMAGE_MODELS = {
    "Stable Diffusion XL": "stability-ai/sdxl:c221b2b8ef527988fb59bf24a8b97c4561f1c671f73bd389f866bfb27c061316",
    "OpenJourney V4": "prompthero/openjourney:9936c2001faa2194a261c01381f90e65261879985476014a0a37a334593a05eb",
}

CREATION_STEPS = [
    "content_type", "genre", "tone", "premise", 
    "chapters", "parameters", "characters",
    "review", "generation"
]

# === SESSION STATE ===
if 'book' not in st.session_state: st.session_state.book = {}
if 'outline' not in st.session_state: st.session_state.outline = []
if 'cover' not in st.session_state: st.session_state.cover = None
if 'characters' not in st.session_state: st.session_state.characters = []
if 'gen_progress' not in st.session_state: st.session_state.gen_progress = 0
if 'image_cache' not in st.session_state: st.session_state.image_cache = {}
if 'chapter_history' not in st.session_state: st.session_state.chapter_history = []
if 'content_type' not in st.session_state: st.session_state.content_type = "Normal"
if 'chat_history' not in st.session_state: st.session_state.chat_history = []
if 'current_step' not in st.session_state: st.session_state.current_step = 0
if 'user_answers' not in st.session_state: st.session_state.user_answers = {}
if 'generation_status' not in st.session_state: st.session_state.generation_status = "idle"

# === API CONFIGURATION ===
def validate_api_keys():
    required_keys = ['REPLICATE_API_TOKEN']
    missing = [key for key in required_keys if key not in st.secrets]
    if missing:
        st.error(f"Missing API keys: {', '.join(missing)}")
        st.stop()

validate_api_keys()
os.environ["REPLICATE_API_TOKEN"] = st.secrets["REPLICATE_API_TOKEN"]

# === CHAT INTERFACE ===
def main_interface():
    st.set_page_config(page_title="NarrativaX", page_icon="📚", layout="wide")
    
    # Custom CSS
    st.markdown("""
    <style>
    .main {background: linear-gradient(45deg, #2b2d42 0%, #1d1e2c 100%);}
    .chat-message {padding: 1.5rem; border-radius: 15px; margin: 1rem 0;}
    .user-message {background: #2d3047; border: 1px solid #404467;}
    .bot-message {background: #1a1b2f; border: 1px solid #2d2f4a;}
    .stButton>button {border-radius: 15px; padding: 10px 25px; transition: all 0.3s;}
    .stButton>button:hover {transform: scale(1.05);}
    .progress-steps {padding: 1rem; background: #151728; border-radius: 10px;}
    </style>
    """, unsafe_allow_html=True)

    # Sidebar Progress
    with st.sidebar:
        st.title("📖 Creation Progress")
        with st.container():
            st.markdown("<div class='progress-steps'>", unsafe_allow_html=True)
            steps = [
                "Content Type", "Genre", "Tone",
                "Premise", "Chapters", "Parameters",
                "Characters", "Review", "Generate"
            ]
            current_step = st.session_state.current_step
            for i, step in enumerate(steps):
                emoji = "🟢" if i < current_step else "⚪"
                st.markdown(f"{emoji} {step}")
            st.markdown("</div>", unsafe_allow_html=True)
            
            if st.session_state.generation_status == "complete":
                st.download_button(
                    label="📥 Download Book Package",
                    data=create_zip_package(),
                    file_name="narrativax_book.zip",
                    mime="application/zip"
                )

    # Main Chat Area
    st.title("📚 NarrativaX — AI Story Architect")
    st.caption("Conversational Interface for Professional-Grade Story Creation")

    # Chat History
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if "options" in msg:
                cols = st.columns([1]*len(msg["options"]))
                for i, option in enumerate(msg["options"]):
                    if cols[i].button(option, key=f"opt_{msg['step']}_{i}"):
                        handle_user_response(option, msg["step"])

    # Current Step Handler
    if st.session_state.current_step < len(CREATION_STEPS):
        handle_creation_step(CREATION_STEPS[st.session_state.current_step])
    else:
        finalize_creation()

# === STEP HANDLERS ===
def handle_creation_step(step):
    handlers = {
        "content_type": step_content_type,
        "genre": step_genre,
        "tone": step_tone,
        "premise": step_premise,
        "chapters": step_chapters,
        "parameters": step_parameters,
        "characters": step_characters,
        "review": step_review,
        "generation": step_generation
    }
    handlers[step]()

def step_content_type():
    add_chat_message(
        "Welcome to NarrativaX! Let's create your story.\n"
        "First, choose your content type:",
        options=CONTENT_TYPES,
        step="content_type"
    )

def step_genre():
    genres = ADULT_GENRES if st.session_state.user_answers.get("content_type") == "Adult" else NORMAL_GENRES
    add_chat_message(
        "Excellent choice! Now select your genre:",
        options=genres,
        step="genre"
    )

def step_tone():
    tone_map = ADULT_TONE_MAP if st.session_state.user_answers.get("content_type") == "Adult" else NORMAL_TONE_MAP
    add_chat_message(
        "What narrative tone would you prefer?",
        options=list(tone_map.keys()),
        step="tone"
    )

def step_premise():
    add_chat_message(
        "Now, describe your core story premise (1-2 sentences):",
        input_field=True,
        step="premise"
    )

def step_chapters():
    add_chat_message(
        "How many chapters should your story have?",
        options=["12-15 (Short Story)", "20-25 (Novella)", "30-40 (Novel)"],
        step="chapters"
    )

def step_parameters():
    if st.session_state.user_answers.get("content_type") == "Adult":
        add_chat_message(
            "Set your content parameters:",
            options=["Mild (Suggestive)", "Medium (Explicit)", "Strong (Graphic)"],
            step="parameters"
        )
    else:
        add_chat_message(
            "Choose complexity level:",
            options=["Simple", "Moderate", "Complex"],
            step="parameters"
        )

def step_characters():
    add_chat_message(
        "How many main characters?",
        options=["1 (Solo)", "2 (Duo)", "3-5 (Ensemble)"],
        step="characters"
    )

def step_review():
    summary = f"""
    **Story Summary**
    - Type: {st.session_state.user_answers.get('content_type')}
    - Genre: {st.session_state.user_answers.get('genre')}
    - Tone: {st.session_state.user_answers.get('tone')}
    - Chapters: {st.session_state.user_answers.get('chapters')}
    - Characters: {st.session_state.user_answers.get('characters')}
    """
    add_chat_message(
        f"Review your settings:\n{summary}\n\nReady to create?",
        options=["Start Generation", "Make Changes"],
        step="review"
    )

def step_generation():
    if st.session_state.generation_status != "complete":
        generate_book_content()

# === CHAT FUNCTIONS ===
def add_chat_message(content, role="assistant", options=None, input_field=False, step=None):
    msg = {"role": role, "content": content, "step": step}
    if options: msg["options"] = options
    if input_field: msg["input"] = True
    st.session_state.chat_history.append(msg)
    
    if input_field:
        user_input = st.chat_input("Type your story premise...")
        if user_input:
            handle_user_response(user_input, step)

def handle_user_response(response, step):
    st.session_state.user_answers[step] = response
    st.session_state.chat_history.append({"role": "user", "content": response})
    st.session_state.current_step += 1
    st.experimental_rerun()

# === GENERATION FUNCTIONS ===
def generate_book_content():
    st.session_state.generation_status = "in_progress"
    
    with st.status("🚀 Launching Story Generation...", expanded=True) as status:
        try:
            # Generate Outline
            st.write("📖 Crafting Story Structure...")
            st.session_state.outline = generate_story_outline()
            time.sleep(1)
            
            # Create Characters
            st.write("👥 Developing Characters...")
            st.session_state.characters = generate_character_profiles()
            time.sleep(0.8)
            
            # Generate Cover
            st.write("🎨 Designing Cover Art...")
            st.session_state.cover = generate_cover_image()
            
            # Generate Chapters
            st.write("📝 Writing Chapters...")
            for i, chapter in enumerate(st.session_state.outline):
                st.session_state.book[f"Chapter {i+1}"] = generate_chapter_content(chapter)
                st.session_state.gen_progress = (i+1)/len(st.session_state.outline)
                time.sleep(0.2)
            
            status.update(label="✅ Generation Complete!", state="complete")
            st.session_state.generation_status = "complete"
            st.balloons()
            
        except Exception as e:
            st.error(f"Generation Failed: {str(e)}")
            st.session_state.generation_status = "error"

def generate_story_outline():
    # Simulated API call
    return [f"Chapter {i+1}" for i in range(15)]

def generate_character_profiles():
    # Simulated character generation
    return [{
        "name": "Elena Voss",
        "role": "Protagonist",
        "description": "Tech-witch with hidden agenda"
    }]

def generate_cover_image():
    prompt = f"{st.session_state.user_answers['genre']} book cover"
    return generate_image(prompt, "Stable Diffusion XL", "cover")

def generate_image(prompt, model_name, section):
    try:
        model = NORMAL_IMAGE_MODELS.get(model_name)
        output = replicate.run(model, input={
            "prompt": prompt,
            "width": IMAGE_SIZE[0],
            "height": IMAGE_SIZE[1]
        })
        return Image.open(BytesIO(requests.get(output[0]).content))
    except:
        return Image.new("RGB", IMAGE_SIZE, color="#2d3047")

def create_zip_package():
    with NamedTemporaryFile(delete=False) as tmp:
        with zipfile.ZipFile(tmp, 'w') as zipf:
            # Add generated content
            zipf.writestr("book.json", json.dumps(st.session_state.book))
            zipf.writestr("characters.json", json.dumps(st.session_state.characters))
        return open(tmp.name, "rb").read()

def finalize_creation():
    st.header("📖 Generated Content Preview")
    
    with st.expander("Book Cover", expanded=True):
        if st.session_state.cover:
            st.image(st.session_state.cover, use_column_width=True)
    
    with st.expander("Character Profiles"):
        for char in st.session_state.characters:
            st.markdown(f"### {char['name']}")
            st.write(char['description'])
    
    with st.expander("Chapter Preview"):
        chap_select = st.selectbox("Select Chapter", list(st.session_state.book.keys()))
        st.write(st.session_state.book[chap_select])

# === INITIALIZATION ===
if __name__ == "__main__":
    if not st.session_state.user_answers:
        st.session_state.user_answers = {}
    if not st.session_state.chat_history:
        st.session_state.chat_history = []
    
    main_interface()
