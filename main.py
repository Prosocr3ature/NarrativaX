# main.py
import os
import json
import requests
import zipfile
import random
import replicate
import base64
import time
from io import BytesIO
from tempfile import NamedTemporaryFile
from PIL import Image
from docx import Document
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from gtts import gTTS
import streamlit as st
from streamlit_sortables import sort_items

# ====================
# CONSTANTS & CONFIG
# ====================
FONT_PATHS = {
    "regular": "fonts/NotoSans-Regular.ttf",
    "bold": "fonts/NotoSans-Bold.ttf"
}
MAX_TOKENS = 1800
IMAGE_SIZE = (768, 1024)
SAFE_LOADING_MESSAGES = [
    "📚 Plotting character arcs...", "🎨 Mixing narrative tones...",
    "💡 Crafting plot twists...", "🌌 Building worlds...",
    "🔥 Igniting conflicts...", "💔 Developing relationships..."
]

GENRES = {
    "📖 Literary": ["thoughtful", "reflective", "literary"],
    "💖 Romance": ["sensual", "emotional", "passionate"],
    "🔞 Adult": ["explicit", "erotic", "provocative"],
    "🚀 Sci-Fi": ["futuristic", "technological", "cosmic"],
    "🪄 Fantasy": ["magical", "epic", "mythical"],
    "🔪 Thriller": ["tense", "suspenseful", "dark"],
    "💼 Business": ["professional", "insightful", "strategic"],
    "🌱 Self-Help": ["motivational", "inspirational", "practical"]
}

TONES = {
    "😊 Wholesome": "uplifting, positive, family-friendly",
    "😈 Explicit": "graphic, explicit, adult-oriented",
    "🤔 Philosophical": "contemplative, deep, existential",
    "😄 Humorous": "witty, lighthearted, amusing",
    "😱 Dark": "gritty, intense, disturbing",
    "💡 Educational": "informative, structured, factual"
}

IMAGE_MODELS = {
    "🎨 Realistic Vision": "lucataco/realistic-vision-v5.1:2c8e954decbf70b7607a4414e5785ef9e4de4b8c51d50fb8b8b349160e0ef6bb",
    "🔥 Reliberate NSFW": "asiryan/reliberate-v3:d70438fcb9bb7adb8d6e59cf236f754be0b77625e984b8595d1af02cdf034b29"
}

MODELS = {
    "🧠 MythoMax": "gryphe/mythomax-l2-13b",
    "🐬 Dolphin": "cognitivecomputations/dolphin-mixtral",
    "🤖 OpenChat": "openchat/openchat-3.5-0106"
}

# ====================
# CORE FUNCTIONALITY
# ====================
class PDFStyler(FPDF):
    def __init__(self):
        super().__init__()
        self.font_configured = False
        self.add_font('NotoSans', style='', fname=FONT_PATHS["regular"])
        self.add_font('NotoSans', style='B', fname=FONT_PATHS["bold"])
        self.font_configured = True
    
    def header(self):
        if self.font_configured:
            self.set_font('NotoSans', 'B', 12)
            self.cell(0, 10, 'NarrativaX Generated Book', 
                     new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
            self.ln(10)
    
    def footer(self):
        if self.font_configured:
            self.set_y(-15)
            self.set_font('NotoSans', '', 8)
            self.cell(0, 10, f'Page {self.page_no()}', 
                     new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')

def initialize_state():
    defaults = {
        "last_saved": None,
        "feedback_history": [],
        "characters": [],
        "chapter_order": [],
        "book": {},
        "outline": "",
        "cover": None,
        "gen_progress": {},
        "image_cache": {},
        "explicit_level": 0,
        "selected_genre": None,
        "selected_tone": None
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

def validate_environment():
    required_keys = ['OPENROUTER_API_KEY', 'REPLICATE_API_TOKEN']
    missing = [key for key in required_keys if key not in st.secrets]
    if missing:
        st.error(f"Missing API keys: {', '.join(missing)}")
        st.stop()
    
    try:
        replicate.Client(api_token=st.secrets["REPLICATE_API_TOKEN"])
    except Exception as e:
        st.error(f"Replicate authentication failed: {str(e)}")
        st.stop()

# ====================
# AI INTEGRATIONS
# ====================
def call_openrouter(prompt, model):
    headers = {
        "Authorization": f"Bearer {st.secrets['OPENROUTER_API_KEY']}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://narrativax.com",
        "X-Title": "NarrativaX Book Generator"
    }
    
    explicit_prompt = ""
    if st.session_state.explicit_level > 0:
        explicit_prompt = f"[Explicit Level: {st.session_state.explicit_level}/100] "
    
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": explicit_prompt + prompt}],
        "max_tokens": MAX_TOKENS,
        "temperature": 0.7 + (st.session_state.explicit_level * 0.002)
    }
    
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        st.error(f"API Error: {str(e)}")
        return None

def generate_image(prompt, model_name, section):
    try:
        model_version = IMAGE_MODELS[model_name]
        explicit_addition = ""
        if st.session_state.explicit_level > 0:
            explicit_addition = f", explicit content level {st.session_state.explicit_level}/100"
        
        output = replicate.run(
            model_version,
            input={
                "prompt": f"{prompt}{explicit_addition}",
                "width": IMAGE_SIZE[0],
                "height": IMAGE_SIZE[1],
                "negative_prompt": "text, watermark" if "NSFW" in model_name else "",
                "guidance_scale": 7.5 + (st.session_state.explicit_level * 0.1)
            }
        )
        
        image_url = output[0] if isinstance(output, list) else output
        response = requests.get(image_url, timeout=15)
        response.raise_for_status()
        
        image = Image.open(BytesIO(response.content))
        st.session_state.image_cache[section] = image
        return image
        
    except Exception as e:
        st.error(f"Image Generation Failed: {str(e)}")
        return None

# ====================
# UI COMPONENTS
# ====================
def genre_selector():
    st.subheader("🎭 Choose Your Genre")
    cols = st.columns(4)
    for idx, (genre, tags) in enumerate(GENRES.items()):
        with cols[idx % 4]:
            if st.button(
                genre,
                key=f"genre_{idx}",
                use_container_width=True,
                help=f"Tags: {', '.join(tags)}"
            ):
                st.session_state.selected_genre = genre
                st.session_state.gen_progress['genre'] = genre

def tone_selector():
    st.subheader("🎨 Select Narrative Tone")
    cols = st.columns(3)
    for idx, (tone, desc) in enumerate(TONES.items()):
        with cols[idx % 3]:
            if st.button(
                tone,
                key=f"tone_{idx}",
                use_container_width=True,
                help=desc
            ):
                st.session_state.selected_tone = tone
                st.session_state.gen_progress['tone'] = tone

def explicit_controls():
    st.subheader("🔞 Content Intensity")
    st.session_state.explicit_level = st.slider(
        "Sexual Content Level (0 = Clean, 100 = Explicit)",
        0, 100, 0,
        help="Adjust the level of romantic/sexual content in your book"
    )
    st.caption("Note: Higher levels may trigger content filters")

# ====================
# MAIN INTERFACE
# ====================
def main_interface():
    st.set_page_config(
        page_title="NarrativaX Studio",
        page_icon="📚",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Custom CSS
    st.markdown("""
    <style>
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        color: #ffffff;
    }
    .stButton>button {
        background: #2a2a4a;
        color: white;
        border-radius: 10px;
        padding: 10px 24px;
        transition: all 0.3s;
    }
    .stButton>button:hover {
        background: #3a3a5a;
        transform: scale(1.05);
    }
    .selected {
        background: #4a4a6a !important;
        border: 2px solid #6c5b7b !important;
    }
    </style>
    """, unsafe_allow_html=True)

    initialize_state()
    validate_environment()

    # Sidebar
    with st.sidebar:
        st.image("https://i.imgur.com/vGV9N5k.png", width=200)
        st.markdown("### 🔧 Generation Settings")
        
        # Model Selection
        st.selectbox("🤖 AI Model", options=MODELS.keys(), key="selected_model")
        st.selectbox("🖼️ Image Model", options=IMAGE_MODELS.keys(), key="selected_image_model")
        
        # Explicit Controls
        explicit_controls()
        
        # Status
        st.markdown("---")
        if st.session_state.last_saved:
            st.caption(f"⏱️ Last saved: {time.strftime('%Y-%m-%d %H:%M', time.localtime(st.session_state.last_saved))}")
        
        # Save/Load
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 Save Session"):
                with open("session.json", "w") as f:
                    json.dump(st.session_state.book, f)
                st.session_state.last_saved = time.time()
                st.success("Session saved!")
        with col2:
            if st.button("📂 Load Session"):
                try:
                    with open("session.json") as f:
                        st.session_state.book = json.load(f)
                    st.success("Session loaded!")
                except Exception as e:
                    st.error(f"Load failed: {str(e)}")

    # Main Content
    st.title("📖 NarrativaX - AI-Powered Story Studio")
    
    # Genre/Tone Selection
    genre_selector()
    tone_selector()
    
    # Main Controls
    col1, col2 = st.columns([1, 2])
    with col1:
        chapters = st.slider("📑 Chapters", 3, 30, 10)
    with col2:
        prompt = st.text_input("✨ Your Story Seed", placeholder="A dystopian romance between an AI and a human rebel...")

    if st.button("🚀 Generate Book", use_container_width=True, type="primary"):
        if not st.session_state.selected_genre or not st.session_state.selected_tone:
            st.warning("Please select both a genre and tone!")
        else:
            st.session_state.gen_progress = {
                "prompt": prompt,
                "genre": st.session_state.selected_genre,
                "tone": st.session_state.selected_tone,
                "chapters": chapters,
                "model": MODELS[st.session_state.selected_model],
                "img_model": st.session_state.selected_image_model
            }
            generate_book_content()

    # Content Tabs
    if st.session_state.book:
        tabs = st.tabs(["📖 Chapters", "🎙️ Narration", "🖼️ Artwork", "📤 Export", "👥 Characters"])
        
        with tabs[0]:
            st.subheader("Chapter Management")
            reordered = sort_items(st.session_state.chapter_order)
            if reordered:
                st.session_state.chapter_order = reordered

            for title in st.session_state.chapter_order:
                with st.expander(title):
                    content = st.session_state.book[title]
                    st.markdown(f"```\n{content}\n```")
                    if st.button(f"🔄 Regenerate {title}", key=f"regen_{title}"):
                        st.session_state.book[title] = call_openrouter(
                            f"Rewrite this chapter: {content}",
                            st.session_state.gen_progress['model']
                        )
        
        with tabs[1]:
            st.subheader("Audio Narration")
            for title, content in st.session_state.book.items():
                with st.expander(f"🔊 {title}"):
                    with NamedTemporaryFile(suffix=".mp3") as fp:
                        tts = gTTS(text=content, lang='en')
                        tts.save(fp.name)
                        st.audio(fp.name)
        
        with tabs[2]:
            st.subheader("Generated Artwork")
            if st.session_state.cover:
                st.image(st.session_state.cover, caption="Book Cover", use_container_width=True)
            
            cols = st.columns(3)
            for idx, (section, image) in enumerate(st.session_state.image_cache.items()):
                with cols[idx % 3]:
                    st.image(image, caption=section.replace("_", " ").title())
        
        with tabs[3]:
            st.subheader("Export Options")
            if st.button("📦 Export Complete Package", use_container_width=True):
                with st.spinner("Packaging your masterpiece..."):
                    zip_path = create_export_zip()
                    st.download_button(
                        label="⬇️ Download ZIP",
                        data=open(zip_path, "rb").read(),
                        file_name="narrativax_book.zip",
                        mime="application/zip"
                    )
        
        with tabs[4]:
            st.subheader("Character Development")
            if st.button("➕ Generate New Characters", use_container_width=True):
                new_chars = call_openrouter(
                    f"Generate 3 characters for {st.session_state.gen_progress['prompt']}",
                    st.session_state.gen_progress['model']
                ).split("\n\n")
                st.session_state.characters.extend(new_chars)
            
            for idx, desc in enumerate(st.session_state.characters):
                with st.expander(f"🧑💼 Character #{idx+1}"):
                    cols = st.columns([3, 1])
                    with cols[0]:
                        new_desc = st.text_area(f"Description #{idx+1}", desc, height=150)
                    with cols[1]:
                        if st.button(f"🎨 Visualize #{idx+1}", key=f"visual_{idx}"):
                            img = generate_image(new_desc, st.session_state.selected_image_model, f"char_{idx}")
                            st.image(img)
                    if new_desc != desc:
                        st.session_state.characters[idx] = new_desc

if __name__ == "__main__":
    main_interface()
