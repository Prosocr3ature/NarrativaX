import os, json, requests
import streamlit as st
from docx import Document
from fpdf import FPDF
from tempfile import NamedTemporaryFile
from gtts import gTTS
from PIL import Image
import matplotlib.pyplot as plt
from io import BytesIO
import replicate
import pandas as pd
from docx.shared import Inches

st.set_page_config(page_title="NarrativaX", page_icon="🪶", layout="wide")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
replicate_client = replicate.Client(api_token=REPLICATE_API_TOKEN)

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

GENRES_NORMAL = [
    "Adventure", "Fantasy", "Dark Fantasy", "Romance", "Thriller", "Mystery",
    "Drama", "Sci-Fi", "Slice of Life", "Horror", "Crime", "LGBTQ+", "Action",
    "Psychological", "Historical Fiction", "Supernatural", "Steampunk",
    "Cyberpunk", "Post-Apocalyptic", "Surreal", "Noir"
]

GENRES_ADULT = [
    "Erotica", "NSFW", "Hardcore", "BDSM", "Futanari", "Incubus/Succubus",
    "Monster Romance", "Dubious Consent", "Voyeurism", "Yaoi", "Yuri", "Taboo Fantasy"
]

GENRES = GENRES_NORMAL + GENRES_ADULT
VOICES = {"Rachel": "default", "Bella": "default", "Antoni": "default", "Elli": "default", "Josh": "default"}

MODELS = [
    "nothingiisreal/mn-celeste-12b",
    "openchat/openchat-3.5-0106",
    "gryphe/mythomax-l2-13b"
]

IMAGE_MODELS = {
    "Realistic Vision v5.1": "lucataco/realistic-vision-v5.1:2c8e954decbf70b7607a4414e5785ef9e4de4b8c51d50fb8b8b349160e0ef6bb",
    "Reliberate V3 (NSFW)": "asiryan/reliberate-v3:d70438fcb9bb7adb8d6e59cf236f754be0b77625e984b8595d1af02cdf034b29"
}

SAFE_IMAGE_MODELS = {k: v for k, v in IMAGE_MODELS.items() if "NSFW" not in k}

def init_state():
    defaults = {
        "book": {}, "outline": "", "characters": [], "prompt": "",
        "genre": "", "tone": "", "chapter_order": [], "image_cache": {}, "audio_cache": {},
        "img_model": "", "book_title": "", "custom_title": "", "tagline": "",
        "cover_image": None, "regenerate_mode": "Preview", "want_to_generate": False
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
init_state()

def call_openrouter(prompt, model, max_tokens=1800):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://narrativax.app",
        "X-Title": "NarrativaX"
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.95,
        "max_tokens": max_tokens
    }
    r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()

def generate_outline(prompt, genre, tone, chapters, model):
    return call_openrouter(f"You are a ghostwriter. Create an outline for a {tone} {genre} novel with {chapters} chapters. Include: Title, Foreword, Introduction, Chapters, Final Words. Concept:\\n{prompt}", model)

def generate_section(title, outline, model):
    return call_openrouter(f"Write the full content for section '{title}' using this outline:\\n{outline}", model)

def generate_characters(outline, genre, tone, model):
    prompt = f"""Create characters for a {tone} {genre} novel based on this outline.
Return a JSON list like:
[{{"name": "X", "role": "Y", "personality": "...", "appearance": "..."}}]
Outline: {outline}"""
    try:
        return json.loads(call_openrouter(prompt, model))
    except:
        return [{"name": "Unnamed", "role": "Unknown", "personality": "N/A", "appearance": ""}]

def generate_image(prompt, model_key, id_key):
    if id_key in st.session_state.image_cache:
        return st.session_state.image_cache[id_key]
    model = IMAGE_MODELS[model_key]
    args = {
        "prompt": prompt[:300],
        "num_inference_steps": 30,
        "guidance_scale": 7.5,
        "width": 768,
        "height": 1024
    }
    output = replicate_client.run(model, input=args)
    if isinstance(output, str) and output.startswith("http"):
        image_result = output
    elif hasattr(output, "read"):
        image_data = output.read()
        image_result = Image.open(BytesIO(image_data))
    else:
        st.error("Image generation failed: unknown output type.")
        return None
    st.session_state.image_cache[id_key] = image_result
    return image_result

def narrate(text, id_key):
    if id_key in st.session_state.audio_cache:
        return st.session_state.audio_cache[id_key]
    filename = f"{id_key}.mp3"
    gTTS(text.replace("\\n", " ")).save(filename)
    st.session_state.audio_cache[id_key] = filename
    return filename

# --- SIDEBAR ---
with st.sidebar:
    st.image("https://narrativax.onrender.com/icon-192.png", width=180)
    st.markdown("### NarrativaX PWA")
    st.info("Safari → Dela → Lägg till på hemskärmen för att spara som app.")

    if st.button("Save Project"):
        json.dump(st.session_state.book, open("session.json", "w"))
        st.success("Project saved.")
    if st.button("Load Project"):
        try:
            st.session_state.book = json.load(open("session.json"))
            st.session_state.chapter_order = list(st.session_state.book.keys())
            st.success("Project loaded.")
        except Exception as e:
            st.error(f"Load failed: {e}")

# --- MAIN UI ---
st.title("NarrativaX — AI Book Studio")

cover_url = st.session_state.cover_image
if cover_url and isinstance(cover_url, str) and cover_url.startswith("http"):
    try:
        st.image(cover_url, caption=f"**{st.session_state.book_title}**\\n{st.session_state.tagline}", use_container_width=True)
    except:
        st.warning("Could not display cover image.")
elif isinstance(cover_url, Image.Image):
    st.image(cover_url, caption="NarrativaX", use_container_width=True)
else:
    st.image("https://narrativax.onrender.com/icon-512.png", caption="NarrativaX", use_container_width=True)

# --- SETTINGS ---
with st.expander("Book Settings", expanded=True):
    st.session_state.prompt = st.text_area("Book Idea / Prompt", height=150, key="prompt_input")
    genre_type = st.radio("Content Type", ["Normal", "Adult"], horizontal=True)
    genre_list = GENRES_ADULT if genre_type == "Adult" else GENRES_NORMAL
    st.session_state.genre = st.selectbox("Genre", genre_list)
    st.session_state.tone = st.selectbox("Tone", list(TONE_MAP))
    chapters = st.slider("Chapters", 4, 20, 10)
    model = st.selectbox("Model", MODELS)
    voice = st.selectbox("Voice", list(VOICES))
    st.session_state.img_model = st.selectbox("Image Model", list(IMAGE_MODELS))
    st.session_state.custom_title = st.text_input("Custom Title (optional)", "")
    st.session_state.tagline = st.text_input("Tagline (optional)", "")
    st.session_state.regenerate_mode = st.radio("Regenerate Mode", ["Preview", "Instant"], horizontal=True)

# --- CREATE FULL BOOK ---
if st.button("Create Full Book"):
    st.session_state.want_to_generate = False
    st.session_state.book = {}

    with st.spinner("Creating outline and characters..."):
        st.session_state.outline = generate_outline(
            st.session_state.prompt,
            st.session_state.genre,
            TONE_MAP[st.session_state.tone],
            chapters, model
        )
        st.session_state.characters = generate_characters(
            st.session_state.outline,
            st.session_state.genre,
            TONE_MAP[st.session_state.tone],
            model
        )
        title_line = next((line for line in st.session_state.outline.splitlines() if "Title:" in line), None)
        raw_title = title_line.replace("Title:", "").strip() if title_line else "Untitled"
        st.session_state.book_title = st.session_state.custom_title or raw_title
        cover_prompt = f"{st.session_state.book_title}, {st.session_state.genre}, {st.session_state.tone}, book cover, centered, cinematic, ultra detailed"
        st.session_state.cover_image = generate_image(cover_prompt, st.session_state.img_model, "cover")

    with st.spinner("Writing full book..."):
        book = {}
        sections = ["Foreword", "Introduction"] + [f"Chapter {i+1}" for i in range(chapters)] + ["Final Words"]
        st.session_state.chapter_order = sections
        for section in sections:
            st.info(f"Writing {section}...")
            book[section] = generate_section(section, st.session_state.outline, model)
        st.session_state.book = book
        st.success("Book created!")

# --- DISPLAY BOOK TABS ---
if st.session_state.book:
    tabs = st.tabs(st.session_state.chapter_order + ["Characters"])

    for i, title in enumerate(st.session_state.chapter_order):
        with tabs[i]:
            st.subheader(title)
            st.markdown(st.session_state.book[title])

            img_url = st.session_state.image_cache.get(title)
            if img_url:
                try:
                    st.image(img_url, caption=f"{title} Illustration", use_container_width=True)
                except:
                    st.warning("Could not display illustration.")
            else:
                if st.button(f"Generate Illustration for {title}", key=f"img_gen_{title}"):
                    prompt = f"Illustration for section '{title}': {st.session_state.book[title][:300]}"
                    img_url = generate_image(prompt, st.session_state.img_model, title)
                    st.image(img_url, caption=f"{title} Illustration", use_container_width=True)

            if st.button(f"Read Aloud: {title}", key=f"tts_{title}"):
                audio = narrate(st.session_state.book[title], title)
                st.audio(audio)

            if st.button(f"Regenerate: {title}", key=f"regen_{title}"):
                new_text = generate_section(title, st.session_state.outline, model)
                if st.session_state.regenerate_mode == "Preview":
                    with st.expander("Preview New Version", expanded=True):
                        st.markdown("### New Version")
                        st.text_area("Preview", value=new_text, height=300, key=f"preview_{title}")
                        col1, col2 = st.columns(2)
                        if col1.button("Replace with New", key=f"confirm_{title}"):
                            st.session_state.book[title] = new_text
                            st.success(f"{title} updated.")
                        if col2.button("Cancel", key=f"cancel_{title}"):
                            st.info("No changes made.")
                else:
                    st.session_state.book[title] = new_text
                    st.success(f"{title} regenerated.")

# --- CHARACTERS TAB ---
with tabs[-1]:
    st.subheader("Characters & Portraits")

    if st.button("➕ Add New Character"):
        st.session_state.characters.append({
            "name": "New",
            "role": "Unknown",
            "personality": "",
            "appearance": "",
            "type": "Supporting",
            "relations": ""
        })

    st.markdown("### Character Editor")
    updated = []
    for idx, char in enumerate(st.session_state.characters):
        with st.expander(f"{char['name']} — {char['role']}", expanded=False):
            col1, col2 = st.columns([2, 1])

            with col1:
                name = st.text_input("Name", char.get("name", ""), key=f"name_{idx}")
                role = st.text_input("Role", char.get("role", ""), key=f"role_{idx}")
                personality = st.text_area("Personality", char.get("personality", ""), key=f"pers_{idx}")
                appearance = st.text_area("Appearance", char.get("appearance", ""), key=f"app_{idx}")
            with col2:
                portrait_key = f"char_{idx}"
                portrait_url = st.session_state.image_cache.get(portrait_key)
                if portrait_url:
                    st.image(portrait_url, caption=char['name'], use_container_width=True)
                if st.button("Regenerate Portrait", key=f"regenportrait_{idx}"):
                    url = generate_image(appearance, st.session_state.img_model, portrait_key)
                    st.session_state.image_cache[portrait_key] = url
                    st.success("Portrait updated!")
                if st.button("❌ Remove", key=f"remove_char_{idx}"):
                    continue  # skip adding to updated list
            updated.append({
                "name": name,
                "role": role,
                "personality": personality,
                "appearance": appearance,
                "type": char.get("type", "Supporting"),
                "relations": char.get("relations", "")
            })

    st.session_state.characters = updated

    st.markdown("### Export Characters")
    col1, col2 = st.columns(2)

    with col1:
        st.download_button("Download JSON", json.dumps(st.session_state.characters), file_name="characters.json")

    with col2:
        try:
            df = pd.DataFrame(st.session_state.characters)
            buf = BytesIO()
            fig, ax = plt.subplots(figsize=(10, len(df)*0.5))
            ax.axis('off')
            tbl = ax.table(cellText=df.values, colLabels=df.columns, loc='center')
            plt.savefig(buf, format='png', bbox_inches='tight')
            buf.seek(0)
            st.download_button("Download Table as PNG", buf, file_name="character_table.png", mime="image/png")
        except:
            st.warning("Failed to export PNG.")
    
# --- FOOTER ---
st.markdown("---")
st.caption("© 2025 NarrativaX | Built with AI and imagination.")
