import os
import json
import requests
import zipfile
import random
import replicate
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
        self.add_font('NotoSans', style='', fname=FONT_PATHS["regular"])
        self.add_font('NotoSans', style='B', fname=FONT_PATHS["bold"])
    
    def header(self):
        self.set_font('NotoSans', 'B', 12)
        self.cell(0, 10, 'NarrativaX Generated Book', new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
        self.ln(10)
    
    def footer(self):
        self.set_y(-15)
        self.set_font('NotoSans', '', 8)
        self.cell(0, 10, f'Page {self.page_no()}', new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')

def initialize_state():
    defaults = {
        "last_saved": None,
        "characters": [],
        "chapter_order": [],
        "book": {},
        "outline": "",
        "cover": None,
        "gen_progress": {},
        "image_cache": {},
        "explicit_level": 0,
        "content_preset": "Vanilla",
        "selected_genre": None,
        "selected_tone": None
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val
    # Ensure explicit_level matches content_preset
    presets = {"Vanilla": 0, "NSFW": 50, "Hardcore": 100}
    st.session_state.explicit_level = presets[st.session_state.content_preset]

def validate_environment():
    required_keys = ['OPENROUTER_API_KEY', 'REPLICATE_API_TOKEN']
    missing = [k for k in required_keys if k not in st.secrets]
    if missing:
        st.error(f"Missing API keys: {', '.join(missing)}")
        st.stop()
    try:
        replicate.Client(api_token=st.secrets["REPLICATE_API_TOKEN"])
    except Exception as e:
        st.error(f"Replicate authentication failed: {e}")
        st.stop()

def create_export_zip():
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        doc = Document()
        for title, content in st.session_state.book.items():
            doc.add_heading(title, level=1)
            doc.add_paragraph(content)
        with NamedTemporaryFile(suffix=".docx") as tmp:
            doc.save(tmp.name)
            z.write(tmp.name, "book.docx")
        for section, img in st.session_state.image_cache.items():
            with NamedTemporaryFile(suffix=".jpg") as img_tmp:
                img.save(img_tmp.name)
                z.write(img_tmp.name, f"images/{section}.jpg")
    buf.seek(0)
    return buf

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
    explicit = f"[Explicit Level: {st.session_state.explicit_level}/100] "
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": explicit + prompt}],
        "max_tokens": MAX_TOKENS,
        "temperature": 0.7 + st.session_state.explicit_level * 0.002
    }
    try:
        r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=30)
        r.raise_for_status()
        return r.json()['choices'][0]['message']['content']
    except Exception as e:
        st.error(f"API Error: {e}")
        return ""

def generate_image(prompt, model_name, section):
    version = IMAGE_MODELS[model_name]
    neg = "text, watermark" if "NSFW" in model_name else ""
    add = f", explicit level {st.session_state.explicit_level}/100" if st.session_state.explicit_level > 0 else ""
    try:
        out = replicate.run(version, input={
            "prompt": f"{prompt}{add}",
            "width": IMAGE_SIZE[0],
            "height": IMAGE_SIZE[1],
            "negative_prompt": neg
        })
        url = out[0] if isinstance(out, list) else out
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        img = Image.open(BytesIO(resp.content))
        st.session_state.image_cache[section] = img
        return img
    except Exception as e:
        st.error(f"Image Generation Failed: {e}")
        return None

def generate_book_content():
    with st.status("📖 Crafting Your Masterpiece...", expanded=True) as status:
        try:
            st.write(random.choice(SAFE_LOADING_MESSAGES))
            gp = st.session_state.gen_progress
            outline_prompt = (
                f"Create a {gp['chapters']}-chapter outline for a "
                f"{gp['genre']} story with {gp['tone']} tone. Seed: {gp['prompt']}"
            )
            outline = call_openrouter(outline_prompt, gp['model'])
            st.session_state.outline = outline
            chapters = [line.strip() for line in outline.split("\n") if line.strip()][2:]
            for chap in chapters:
                st.write(f"📝 Writing {chap}...")
                content = call_openrouter(f"Expand this chapter in detail: {chap}", gp['model'])
                st.session_state.book[chap] = content
                st.session_state.chapter_order.append(chap)
            st.write("🎨 Painting the cover...")
            cover = generate_image(
                f"Book cover for {gp['prompt']}, {gp['genre']}, {gp['tone']} style",
                gp['img_model'], "cover"
            )
            st.session_state.cover = cover
            status.update(label="✅ Book Generation Complete!", state="complete")
        except Exception as e:
            status.update(label="❌ Generation Failed", state="error")
            st.error(f"Generation failed: {e}")

# ====================
# UI COMPONENTS
# ====================
def genre_selector():
    st.subheader("🎭 Choose Your Genre")
    cols = st.columns(4)
    for i, (g, tags) in enumerate(GENRES.items()):
        col = cols[i % 4]
        sel = st.session_state.selected_genre == g
        label = g + (" ✅" if sel else "")
        if col.button(label, key=f"genre_{i}", use_container_width=True, help=", ".join(tags)):
            st.session_state.selected_genre = g
            st.session_state.gen_progress['genre'] = g

def tone_selector():
    st.subheader("🎨 Select Narrative Tone")
    cols = st.columns(3)
    for i, (t, desc) in enumerate(TONES.items()):
        col = cols[i % 3]
        sel = st.session_state.selected_tone == t
        label = t + (" ✅" if sel else "")
        if col.button(label, key=f"tone_{i}", use_container_width=True, help=desc):
            st.session_state.selected_tone = t
            st.session_state.gen_progress['tone'] = t

def main_interface():
    st.set_page_config(page_title="NarrativaX Studio", page_icon="📚", layout="wide")
    st.markdown("""
    <style>
    [data-testid="stAppViewContainer"] { background: linear-gradient(135deg, #1a1a2e, #16213e); color: #fff; }
    .stButton>button { background: #2a2a4a; color: #fff; border-radius: 10px; padding: 10px 24px; transition: .3s; }
    .stButton>button:hover { background: #3a3a5a; transform: scale(1.05); }
    </style>
    """, unsafe_allow_html=True)

    initialize_state()
    validate_environment()

    # Sidebar: Save/Load session
    with st.sidebar:
        st.markdown("### 🔧 Session Controls")
        if st.session_state.last_saved:
            st.caption(f"⏱️ Last saved: {time.strftime('%Y-%m-%d %H:%M', time.localtime(st.session_state.last_saved))}")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("💾 Save Session"):
                with open("session.json", "w") as f:
                    json.dump(st.session_state.book, f)
                st.session_state.last_saved = time.time()
                st.success("Session saved!")
        with c2:
            if st.button("📂 Load Session"):
                try:
                    with open("session.json") as f:
                        st.session_state.book = json.load(f)
                    st.success("Session loaded!")
                except Exception as e:
                    st.error(f"Load failed: {e}")

    # Logo centered
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        st.image("logo.png", width=200)

    st.title("📖 NarrativaX - AI-Powered Story Studio")

    # Frontpage model selectors
    m1, m2 = st.columns(2)
    with m1:
        st.selectbox("🤖 AI Model", options=list(MODELS.keys()), key="selected_model")
    with m2:
        st.selectbox("🖼️ Image Model", options=list(IMAGE_MODELS.keys()), key="selected_image_model")

    # Explicit content presets as buttons
    st.subheader("🔞 Content Intensity")
    presets = {"Vanilla": 0, "NSFW": 50, "Hardcore": 100}
    pcols = st.columns(3)
    for idx, name in enumerate(presets):
        col = pcols[idx]
        sel = (st.session_state.content_preset == name)
        lbl = name + (" ✅" if sel else "")
        if col.button(lbl, key=f"preset_{name}", use_container_width=True):
            st.session_state.content_preset = name
            st.session_state.explicit_level = presets[name]

    # Genre & Tone
    genre_selector()
    tone_selector()

    # Chapters & Seed input
    c1, c2 = st.columns([1, 2])
    with c1:
        chapters = st.slider("📑 Chapters", 3, 30, 10)
    with c2:
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

        # Chapters Tab
        with tabs[0]:
            st.subheader("Chapter Management")
            reordered = sort_items(st.session_state.chapter_order)
            if reordered:
                st.session_state.chapter_order = reordered
            for title in st.session_state.chapter_order:
                with st.expander(title):
                    content = st.session_state.book[title]
                    st.text_area("", content, height=300, disabled=True, key=f"text_{title}")
                    if st.button(f"🔄 Regenerate", key=f"regen_{title}", use_container_width=True):
                        st.session_state.book[title] = call_openrouter(f"Rewrite this chapter: {content}", st.session_state.gen_progress['model'])

        # Narration Tab
        with tabs[1]:
            st.subheader("Audio Narration")
            for title, content in st.session_state.book.items():
                with st.expander(f"🔊 {title}"):
                    with NamedTemporaryFile(suffix=".mp3") as fp:
                        tts = gTTS(text=content, lang='en')
                        tts.save(fp.name)
                        st.audio(fp.name)

        # Artwork Tab
        with tabs[2]:
            st.subheader("Generated Artwork")
            if st.session_state.cover:
                st.image(st.session_state.cover, caption="Book Cover", use_column_width=True)
            art_cols = st.columns(3)
            for i, (sec, img) in enumerate(st.session_state.image_cache.items()):
                with art_cols[i % 3]:
                    st.image(img, caption=sec.replace("_", " ").title(), use_column_width=True)

        # Export Tab
        with tabs[3]:
            st.subheader("Export Options")
            if st.button("📦 Export Complete Package", use_container_width=True):
                with st.spinner("Packaging your masterpiece..."):
                    zip_buf = create_export_zip()
                    st.download_button("⬇️ Download ZIP", data=zip_buf.getvalue(), file_name="narrativax_book.zip", mime="application/zip")

        # Characters Tab
        with tabs[4]:
            st.subheader("Character Development")
            if st.button("➕ Generate New Characters", use_container_width=True):
                chars = call_openrouter(f"Generate 3 characters for {st.session_state.gen_progress['prompt']}", st.session_state.gen_progress['model']).split("\n\n")
                st.session_state.characters.extend(chars)
            for idx, desc in enumerate(st.session_state.characters):
                with st.expander(f"🧑💼 Character #{idx+1}"):
                    cc1, cc2 = st.columns([3, 1])
                    with cc1:
                        new_desc = st.text_area(f"Description #{idx+1}", desc, height=150, key=f"char_desc_{idx}")
                    with cc2:
                        if st.button(f"🎨 Visualize", key=f"visual_{idx}", use_container_width=True):
                            img = generate_image(new_desc, st.session_state.selected_image_model, f"char_{idx}")
                            if img:
                                st.image(img)

if __name__ == "__main__":
    main_interface()
