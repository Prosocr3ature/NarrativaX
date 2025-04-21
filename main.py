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
from gtts import gTTS, gTTSError

import streamlit as st
from streamlit_sortables import sort_items

# ====================
# CONFIG & CONSTANTS
# ====================
MAX_TOKENS = 1800
IMAGE_SIZE = (768, 1024)
SAFE_LOADING_MESSAGES = [
    "📚 Plotting character arcs...", "🎨 Mixing narrative tones...",
    "💡 Crafting plot twists...", "🌌 Building worlds...",
    "🔥 Igniting conflicts...", "💔 Developing relationships..."
]

GENRES = {
    "📖 Literary":    ["Thoughtful", "Reflective", "Historical Fiction", "Experimental", "Magical Realism"],
    "💖 Romance":     ["Sensual", "Emotional", "Paranormal Romance", "Romantic Comedy", "Drama"],
    "🔞 Adult":       ["Erotic", "Softcore", "Hardcore", "BDSM", "Fetish"],
    "🚀 Sci‑Fi":      ["Space Opera", "Cyberpunk", "Dystopian", "Time Travel", "Military Sci‑Fi"],
    "🪄 Fantasy":     ["Epic", "Urban Fantasy", "Dark Fantasy", "Fairy Tale", "Steampunk"],
    "🔪 Thriller":    ["Suspense", "Psychological", "Crime", "Espionage", "Noir"],
    "🕵️ Mystery":    ["Detective", "Whodunit", "Cozy Mystery", "Forensic", "Locked‑Room"],
    "👻 Horror":      ["Supernatural", "Slasher", "Paranormal", "Gore", "Haunted House"],
    "🏰 Historical":  ["Period Drama", "Alternate History", "Medieval", "Victorian", "World War"],
    "💼 Business":    ["Entrepreneurship", "Leadership", "Finance", "Strategy", "Startups"],
    "🌱 Self‑Help":   ["Motivational", "Mindfulness", "Productivity", "Wellness", "Habits"],
    "👶 Children":    ["Bedtime Story", "Young Adult", "Middle Grade", "Picture Book", "Coming‑of‑Age"]
}

TONES = {
    "😊 Wholesome":     "Uplifting, positive, family‑friendly",
    "😈 Explicit":      "Graphic, raw, adult‑oriented",
    "🤔 Philosophical": "Contemplative, existential, deep",
    "😄 Humorous":      "Witty, lighthearted, satirical",
    "😱 Dark":          "Gritty, intense, disturbing",
    "💡 Educational":   "Informative, structured, factual",
    "💔 Melancholic":   "Sad, poignant, bittersweet",
    "🔮 Mystical":      "Ethereal, mysterious, dreamlike",
    "🔥 Passionate":    "Fervent, intense, ardent",
    "🦄 Quirky":        "Eccentric, whimsical, offbeat"
}

IMAGE_MODELS = {
    "🎨 Realistic Vision": "lucataco/realistic-vision-v5.1:2c8e954decbf70b7607a4414e5785ef9e4de4b8c51d50fb8b8b349160e0ef6bb",
    "🔥 Reliberate NSFW":  "asiryan/reliberate-v3:d70438fcb9bb7adb8d6e59cf236f754be0b77625e984b8595d1af02cdf034b29"
}

MODELS = {
    "🧠 MythoMax": "gryphe/mythomax-l2-13b",
    "🐬 Dolphin":  "cognitivecomputations/dolphin-mixtral",
    "🤖 OpenChat": "openchat/openchat-3.5-0106"
}

PRESETS = {
    "Vanilla":  0,
    "NSFW":    50,
    "Hardcore":100
}


# ====================
# STATE INITIALIZATION
# ====================
def initialize_state():
    defaults = {
        "last_saved":            None,
        "book":                  {},
        "chapter_order":         [],
        "outline":               "",
        "cover":                 None,
        "image_cache":           {},
        "characters":            [],
        "character_suggestions": {},
        "chapter_suggestions":   {},
        "gen_progress":          {},
        "selected_genre":        None,
        "selected_subgenres":    [],
        "selected_tone":         None,
        "selected_model":        list(MODELS.keys())[0],
        "selected_image_model":  list(IMAGE_MODELS.keys())[0],
        "content_preset":        "Vanilla",
        "explicit_level":        PRESETS["Vanilla"],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ====================
# ENVIRONMENT CHECK
# ====================
def validate_environment():
    missing = [k for k in ("OPENROUTER_API_KEY", "REPLICATE_API_TOKEN") if k not in st.secrets]
    if missing:
        st.error(f"Missing API keys: {', '.join(missing)}")
        st.stop()
    try:
        replicate.Client(api_token=st.secrets["REPLICATE_API_TOKEN"])
    except Exception as e:
        st.error(f"Replicate auth failed: {e}")
        st.stop()


# ====================
# ZIP EXPORT
# ====================
def create_export_zip():
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        doc = Document()
        for title in st.session_state.chapter_order:
            doc.add_heading(title, level=1)
            doc.add_paragraph(st.session_state.book[title])
        with NamedTemporaryFile(suffix=".docx") as tmp:
            doc.save(tmp.name)
            z.write(tmp.name, "book.docx")
        for sec, img in st.session_state.image_cache.items():
            with NamedTemporaryFile(suffix=".jpg") as tmp:
                img.save(tmp.name)
                z.write(tmp.name, f"images/{sec}.jpg")
    buf.seek(0)
    return buf


# ====================
# AI / IMAGE CALLS
# ====================
def call_openrouter(prompt, model_key):
    headers = {
        "Authorization": f"Bearer {st.secrets['OPENROUTER_API_KEY']}",
        "Content-Type":  "application/json"
    }
    explicit = f"[Explicit Level: {st.session_state.explicit_level}/100] "
    payload = {
        "model":       MODELS[model_key],
        "messages":    [{"role": "user", "content": explicit + prompt}],
        "max_tokens":  MAX_TOKENS,
        "temperature": 0.7 + st.session_state.explicit_level * 0.002
    }
    try:
        r = requests.post("https://openrouter.ai/api/v1/chat/completions",
                          headers=headers, json=payload, timeout=30)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        st.error(f"API Error: {e}")
        return ""


def generate_image(prompt, model_key, section):
    version = IMAGE_MODELS[model_key]
    neg     = "text, watermark" if "NSFW" in model_key else ""
    add     = f", explicit {st.session_state.explicit_level}/100" if st.session_state.explicit_level > 0 else ""
    try:
        out = replicate.run(version, input={
            "prompt":          prompt + add,
            "width":           IMAGE_SIZE[0],
            "height":          IMAGE_SIZE[1],
            "negative_prompt": neg
        })
        url  = out[0] if isinstance(out, list) else out
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        img = Image.open(BytesIO(resp.content))
        st.session_state.image_cache[section] = img
        return img
    except Exception as e:
        st.error(f"Image generation failed: {e}")
        return None


# ====================
# REAL‑TIME CONTENT GENERATION
# ====================
def generate_book_content():
    with st.spinner("📖 Crafting Your Masterpiece..."):
        gp = st.session_state.gen_progress
        # 1) Characters + portraits + suggestions
        char_prompt = f"Generate 3 characters (name + 1‑sentence description) for: {gp['prompt']}"
        raw_chars   = call_openrouter(char_prompt, gp["model"])
        chars       = [c.strip() for c in raw_chars.split("\n") if c.strip()]
        st.session_state.characters = chars
        for idx, desc in enumerate(chars):
            generate_image(desc, gp["img_model"], f"char_{idx}_portrait")
            sugg_text = call_openrouter(f"Give me 3 improvement suggestions for this character: {desc}", gp["model"])
            suggs     = [ln.strip("- ").strip() for ln in sugg_text.split("\n") if ln.strip()]
            st.session_state.character_suggestions[idx] = suggs

        # 2) Cover art
        cover_desc = f"Cover art for: {gp['prompt']}"
        st.session_state.cover = generate_image(cover_desc, gp["img_model"], "cover")

        # 3) Chapter 1 + suggestions
        title = "Chapter 1"
        content = call_openrouter(f"Write {title}: {gp['prompt']}", gp["model"])
        st.session_state.book = {title: content}
        st.session_state.chapter_order = [title]
        chap_sugg_text = call_openrouter(f"Give me 3 improvement suggestions for this chapter: {content}", gp["model"])
        chap_suggs      = [ln.strip("- ").strip() for ln in chap_sugg_text.split("\n") if ln.strip()]
        st.session_state.chapter_suggestions = {title: chap_suggs}


# ====================
# MAIN UI
# ====================
def main_interface():
    st.set_page_config(page_title="NarrativaX", page_icon="📚", layout="wide")
    initialize_state()
    validate_environment()

    st.markdown("""
    <style>
      .block-container { padding: 8px 16px; }
      .logo-container  { text-align: center; margin: 12px 0; }
      .stHeader, .stSubheader { margin: 4px 0 !important; }
      .stButton > button { margin: 4px !important; }
    </style>
    """, unsafe_allow_html=True)

    # Sidebar: Save / Load / New
    with st.sidebar:
        st.markdown("### 🔧 Session")
        if st.session_state.last_saved:
            st.caption(f"⏱️ Last saved: {time.strftime('%Y-%m-%d %H:%M', time.localtime(st.session_state.last_saved))}")
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("💾 Save"):
                with open("session.json", "w") as f:
                    json.dump({
                        "book":     st.session_state.book,
                        "chapters": st.session_state.chapter_order,
                        "chars":    st.session_state.characters
                    }, f)
                st.session_state.last_saved = time.time()
                st.success("Saved!")
        with c2:
            if st.button("📂 Load"):
                try:
                    d = json.load(open("session.json"))
                    st.session_state.book            = d["book"]
                    st.session_state.chapter_order    = d["chapters"]
                    st.session_state.characters       = d.get("chars", [])
                    st.success("Loaded!")
                except Exception as e:
                    st.error(f"Load failed: {e}")
        with c3:
            if st.button("🆕 New"):
                for k in ("book","chapter_order","outline","cover","image_cache","characters",
                          "character_suggestions","chapter_suggestions","gen_progress"):
                    st.session_state[k] = {} if isinstance(st.session_state[k], dict) else []
                st.session_state.selected_genre      = None
                st.session_state.selected_subgenres  = []
                st.session_state.selected_tone       = None
                st.session_state.last_saved          = None
                st.experimental_rerun()

    # Logo
    logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
    if os.path.exists(logo_path):
        st.markdown('<div class="logo-container">', unsafe_allow_html=True)
        st.image(logo_path, width=240, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.title("📖 NarrativaX – AI‑Powered Story Studio")

    # Model & Presets
    st.subheader("🤖 AI Model")
    st.session_state.selected_model = st.radio(
        "", list(MODELS.keys()),
        index=list(MODELS.keys()).index(st.session_state.selected_model),
        horizontal=True, label_visibility="collapsed"
    )
    st.subheader("🖼️ Image Model")
    st.session_state.selected_image_model = st.radio(
        "", list(IMAGE_MODELS.keys()),
        index=list(IMAGE_MODELS.keys()).index(st.session_state.selected_image_model),
        horizontal=True, label_visibility="collapsed"
    )
    st.subheader("🔞 Content Intensity")
    preset = st.radio(
        "", list(PRESETS.keys()),
        index=list(PRESETS.keys()).index(st.session_state.content_preset),
        horizontal=True, label_visibility="collapsed"
    )
    st.session_state.content_preset = preset
    st.session_state.explicit_level = PRESETS[preset]

    # Genre & Subgenres
    st.subheader("🎭 Genre & Sub‑Genres")
    genre = st.selectbox("Main Genre", ["-- choose --"] + list(GENRES.keys()))
    if genre in GENRES:
        st.session_state.selected_genre     = genre
        subs = st.multiselect("Pick sub‑genres", options=GENRES[genre],
                              default=st.session_state.selected_subgenres)
        st.session_state.selected_subgenres = subs

    # Tone
    st.subheader("🎨 Tone")
    tone = st.selectbox("Narrative Tone", ["-- choose --"] + list(TONES.keys()))
    if tone in TONES:
        st.session_state.selected_tone = tone

    # Chapters & Seed
    st.subheader("📑 Chapters & Seed")
    c1, c2 = st.columns([1, 3])
    with c1:
        chapters = st.slider("", 3, 30, 10, label_visibility="collapsed")
    with c2:
        prompt = st.text_input("", placeholder="A dystopian romance between an AI and human rebel…",
                                label_visibility="collapsed")

    if st.button("🚀 Generate Story", use_container_width=True, type="primary"):
        if not (st.session_state.selected_genre and st.session_state.selected_tone and prompt.strip()):
            st.warning("Please choose genre, tone, and enter a seed.")
        else:
            st.session_state.gen_progress = {
                "prompt":    prompt.strip(),
                "genre":     st.session_state.selected_genre,
                "subgenres": st.session_state.selected_subgenres,
                "tone":      st.session_state.selected_tone,
                "chapters":  chapters,
                "model":     st.session_state.selected_model,
                "img_model": st.session_state.selected_image_model
            }
            generate_book_content()

    # Content Tabs
    if st.session_state.chapter_order:
        tabs = st.tabs(["📖 Chapters","🎙️ Narration","🖼️ Artwork","📤 Export","👥 Characters"])

        # Chapters
        with tabs[0]:
            st.subheader("Chapter Manager")
            new_order = sort_items(st.session_state.chapter_order)
            if new_order:
                st.session_state.chapter_order = new_order

            for title in st.session_state.chapter_order:
                with st.expander(title):
                    content = st.session_state.book[title]
                    st.write(content)

                    # suggestions
                    for i, sugg in enumerate(st.session_state.chapter_suggestions.get(title, [])):
                        if st.button(f"💡 {sugg}", key=f"chap_sugg_{title}_{i}"):
                            new_content = call_openrouter(
                                f"Rewrite {title} applying suggestion: {sugg}. Original content: {content}",
                                st.session_state.selected_model
                            )
                            st.session_state.book[title] = new_content
                            st.session_state.chapter_suggestions[title] = [
                                ln.strip("- ").strip()
                                for ln in call_openrouter(
                                    f"Give me 3 improvement suggestions for this chapter: {new_content}",
                                    st.session_state.selected_model
                                ).split("\n") if ln.strip()
                            ]
                            # drop subsequent chapters
                            idx = st.session_state.chapter_order.index(title)
                            for drop in st.session_state.chapter_order[idx+1:]:
                                st.session_state.book.pop(drop, None)
                                st.session_state.chapter_suggestions.pop(drop, None)
                            st.session_state.chapter_order = st.session_state.chapter_order[:idx+1]
                            st.experimental_rerun()

                    c1, c2, c3 = st.columns(3)
                    with c1:
                        # Continue only on last chapter
                        if title == st.session_state.chapter_order[-1]:
                            if st.button("➡️ Continue", key=f"cont_{title}"):
                                chap_num = len(st.session_state.chapter_order) + 1
                                next_title = f"Chapter {chap_num}"
                                next_content = call_openrouter(
                                    f"Write {next_title} continuing from: {content}",
                                    st.session_state.selected_model
                                )
                                st.session_state.book[next_title] = next_content
                                st.session_state.chapter_order.append(next_title)
                                st.session_state.chapter_suggestions[next_title] = [
                                    ln.strip("- ").strip()
                                    for ln in call_openrouter(
                                        f"Give me 3 improvement suggestions for this chapter: {next_content}",
                                        st.session_state.selected_model
                                    ).split("\n") if ln.strip()
                                ]
                                st.experimental_rerun()
                    with c2:
                        if st.button("✏️ Edit", key=f"edit_{title}"):
                            new_txt = st.text_area("Edit content", content, height=300)
                            st.session_state.book[title] = new_txt
                            st.success("Updated.")
                    with c3:
                        if st.button("🗑️ Delete", key=f"del_{title}"):
                            idx = st.session_state.chapter_order.index(title)
                            for drop in st.session_state.chapter_order[idx:]:
                                st.session_state.book.pop(drop, None)
                                st.session_state.chapter_suggestions.pop(drop, None)
                            st.session_state.chapter_order = st.session_state.chapter_order[:idx]
                            st.experimental_rerun()

        # Narration
        with tabs[1]:
            st.subheader("Audio Narration")
            for title in st.session_state.chapter_order:
                with st.expander(f"🔊 {title}"):
                    txt = st.session_state.book[title]
                    try:
                        tts = gTTS(text=txt, lang="en")
                        with NamedTemporaryFile(suffix=".mp3") as fp:
                            tts.save(fp.name)
                            st.audio(fp.name)
                    except gTTSError:
                        st.error("TTS failed.")

        # Artwork
        with tabs[2]:
            st.subheader("Generated Artwork")
            if st.session_state.cover:
                st.image(st.session_state.cover, caption="Cover", use_container_width=True)
            cols = st.columns(3)
            for i, (sec, img) in enumerate(st.session_state.image_cache.items()):
                if sec.startswith("char_") and sec.endswith("_portrait"):
                    idx = int(sec.split("_")[1])
                    with cols[idx % 3]:
                        st.image(img, caption=f"Character {idx+1}", use_container_width=True)

        # Export
        with tabs[3]:
            st.subheader("Export")
            if st.button("📦 Download ZIP", use_container_width=True):
                buf = create_export_zip()
                st.download_button(
                    "⬇️ Download ZIP",
                    data=buf.getvalue(),
                    file_name="narrativax_book.zip",
                    mime="application/zip"
                )

        # Characters
        with tabs[4]:
            st.subheader("Character Development")
            for idx, desc in enumerate(st.session_state.characters):
                with st.expander(f"🧑 Char #{idx+1}"):
                    cols = st.columns([3, 1])
                    with cols[0]:
                        st.write(desc)
                        for j, sugg in enumerate(st.session_state.character_suggestions.get(idx, [])):
                            if st.button(f"💡 {sugg}", key=f"char_sugg_{idx}_{j}"):
                                new_desc = call_openrouter(
                                    f"Revise this character applying suggestion: {sugg}. Original: {desc}",
                                    st.session_state.selected_model
                                )
                                st.session_state.characters[idx] = new_desc
                                st.session_state.character_suggestions[idx] = [
                                    ln.strip("- ").strip()
                                    for ln in call_openrouter(
                                        f"Give me 3 improvement suggestions for this character: {new_desc}",
                                        st.session_state.selected_model
                                    ).split("\n") if ln.strip()
                                ]
                                generate_image(new_desc, st.session_state.selected_image_model, f"char_{idx}_portrait")
                                st.experimental_rerun()
                    with cols[1]:
                        img = st.session_state.image_cache.get(f"char_{idx}_portrait")
                        if img:
                            st.image(img, use_container_width=True)


if __name__ == "__main__":
    main_interface()
