import os, json, requests, base64, zipfile
import streamlit as st
from docx import Document
from docx.shared import Inches
from fpdf import FPDF
from tempfile import NamedTemporaryFile
from gtts import gTTS
from PIL import Image
import matplotlib.pyplot as plt
from io import BytesIO
import replicate
import pandas as pd

# Streamlit settings
st.set_page_config(page_title="NarrativaX", page_icon="🪶", layout="wide")

# Environment variables
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN

# Tone and genre mappings
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

GENRES_NORMAL = ["Adventure", "Fantasy", "Dark Fantasy", "Romance", "Thriller", "Mystery", "Drama", "Sci-Fi", "Slice of Life", "Horror", "Crime", "LGBTQ+", "Action", "Psychological", "Historical Fiction", "Supernatural", "Steampunk", "Cyberpunk", "Post-Apocalyptic", "Surreal", "Noir"]
GENRES_ADULT = ["Erotica", "NSFW", "Hardcore", "BDSM", "Futanari", "Incubus/Succubus", "Monster Romance", "Dubious Consent", "Voyeurism", "Yaoi", "Yuri", "Taboo Fantasy"]

GENRES = GENRES_NORMAL + GENRES_ADULT

MODELS = [
    "nothingiisreal/mn-celeste-12b",
    "openchat/openchat-3.5-0106",
    "gryphe/mythomax-l2-13b"
]

IMAGE_MODELS = {
    "Realistic Vision v5.1": "lucataco/realistic-vision-v5.1:2c8e954decbf70b7607a4414e5785ef9e4de4b8c51d50fb8b8b349160e0ef6bb",
    "Reliberate V3 (NSFW)": "asiryan/reliberate-v3:d70438fcb9bb7adb8d6e59cf236f754be0b77625e984b8595d1af02cdf034b29"
}

# Initialize session state
for key in ["image_cache", "audio_cache", "book", "outline", "cover", "characters"]:
    if key not in st.session_state:
        st.session_state[key] = {}

# Core functions
def call_openrouter(prompt, model, max_tokens=1800):
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}"}
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.95, "max_tokens": max_tokens}
    response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()

# Fix 1: Update image handling and column references
def generate_image(prompt, model_key, id_key):
    if id_key in st.session_state.image_cache:
        return st.session_state.image_cache[id_key]
    
    args = {"prompt": prompt[:300], "num_inference_steps": 30, 
            "guidance_scale": 7.5, "width": 768, "height": 1024}
    try:
        output = replicate.run(IMAGE_MODELS[model_key], input=args)
        if output and isinstance(output, list):
            image_url = output[0]
            response = requests.get(image_url)
            response.raise_for_status()
            image = Image.open(BytesIO(response.content))
            st.session_state.image_cache[id_key] = image
            return image
    except Exception as e:
        st.error(f"Image generation failed: {str(e)}")
    return None

# Fix 2: Update deprecated parameter in image display
with st.expander("📔 Book Cover"):
    if st.session_state.get('cover'):
        try:
            st.image(st.session_state.cover, use_container_width=True)  # Changed parameter
        except Exception as e:
            st.error(f"Error displaying cover: {str(e)}")
            st.session_state.cover = None
    else:
        st.warning("No cover generated yet")

# Fix 3: Properly scope column references in chapter display
if "book" in st.session_state:
    for section, content in st.session_state.book.items():
        with st.expander(f"📜 {section}"):
            col1, col2 = st.columns([3, 2])  # Define columns inside the loop
            with col1:
                st.write(content)
                with NamedTemporaryFile(suffix=".mp3") as tf:
                    text_to_speech(content, tf.name)
                    audio_bytes = open(tf.name, "rb").read()
                    st.audio(audio_bytes, format="audio/mp3")
            with col2:
                if st.session_state.image_cache.get(section):
                    try:
                        st.image(st.session_state.image_cache[section], 
                               use_container_width=True)  # Changed parameter
                    except Exception as e:
                        st.error(f"Error displaying image: {str(e)}")
                        st.session_state.image_cache[section] = None
                else:
                    st.warning("No image generated for this section")

def generate_characters(outline, genre, tone, model):
    prompt = f"Create vivid, immersive characters for a {tone} {genre} novel in JSON format (name, role, personality, appearance):\n{outline}"
    try:
        return json.loads(call_openrouter(prompt, model))
    except:
        return [{"name": "Unnamed", "role": "Unknown", "personality": "N/A", "appearance": ""}]

# Export functions
def create_docx(book_data, images, characters, output_path):
    doc = Document()
    doc.add_heading('Book Content', 0)
    
    for section, content in book_data.items():
        doc.add_heading(section, level=1)
        doc.add_paragraph(content)
        if images.get(section):
            try:
                response = requests.get(images[section])
                img = BytesIO(response.content)
                doc.add_picture(img, width=Inches(5))
            except Exception as e:
                st.error(f"Error adding image: {e}")
    
    doc.add_heading('Character Bios', level=1)
    for char in characters:
        doc.add_heading(char['name'], level=2)
        doc.add_paragraph(f"Role: {char['role']}\nPersonality: {char['personality']}\nAppearance: {char['appearance']}")
    
    doc.save(output_path)

def create_pdf(book_data, images, characters, output_path):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    for section, content in book_data.items():
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(200, 10, txt=section, ln=True)
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, txt=content)
        if images.get(section):
            try:
                response = requests.get(images[section])
                img = BytesIO(response.content)
                temp_img = "temp.jpg"
                with open(temp_img, "wb") as f:
                    f.write(img.getbuffer())
                pdf.image(temp_img, w=150)
                os.remove(temp_img)
            except Exception as e:
                st.error(f"Error adding image: {e}")
    
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="Character Bios", ln=True)
    for char in characters:
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(200, 10, txt=char['name'], ln=True)
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, txt=f"Role: {char['role']}\nPersonality: {char['personality']}\nAppearance: {char['appearance']}")
    
    pdf.output(output_path)

def text_to_speech(text, filename):
    tts = gTTS(text=text, lang='en', slow=False)
    tts.save(filename)

# UI Components
def render_sidebar():
    with st.sidebar:
        st.image("logo.png", width=180)
        st.subheader("Project Management")
        if st.button("💾 Save Project"):
            json.dump(st.session_state, open("session.json", "w"))
            st.success("Project saved successfully!")
        if st.button("📂 Load Project"):
            try:
                st.session_state.update(json.load(open("session.json")))
                st.success("Project loaded successfully!")
            except Exception as e:
                st.error(f"Failed to load: {e}")
        
        st.subheader("Export Options")
        export_format = st.selectbox("Format", ["DOCX", "PDF", "Audiobook"])
        if st.button("📦 Export Full Package"):
            with NamedTemporaryFile(delete=False, suffix=".zip") as tmpfile:
                with zipfile.ZipFile(tmpfile.name, 'w') as zipf:
                    # Add documents
                    docx_path = "book.docx"
                    pdf_path = "book.pdf"
                    create_docx(st.session_state.book, st.session_state.image_cache, st.session_state.characters, docx_path)
                    create_pdf(st.session_state.book, st.session_state.image_cache, st.session_state.characters, pdf_path)
                    zipf.write(docx_path)
                    zipf.write(pdf_path)
                    
                    # Add audio files
                    for i, (sec, content) in enumerate(st.session_state.book.items()):
                        audio_path = f"chapter_{i+1}.mp3"
                        text_to_speech(content, audio_path)
                        zipf.write(audio_path)
                        os.remove(audio_path)
                    
                    os.remove(docx_path)
                    os.remove(pdf_path)
                
                with open(tmpfile.name, "rb") as f:
                    st.download_button("⬇️ Download ZIP", f.read(), file_name="book_package.zip", mime="application/zip")
                os.remove(tmpfile.name)

# Main Interface
st.markdown(f"<img src='logo.png' width='60' style='float:right'>", unsafe_allow_html=True)
st.title("NarrativaX — Immersive AI Book Creator")

with st.container():
    prompt = st.text_area("🖋️ Describe your story concept", height=120)
    col1, col2, col3 = st.columns(3)
    genre = col1.selectbox("📖 Genre", GENRES)
    tone = col2.selectbox("🎨 Tone", list(TONE_MAP))
    chapters = col3.slider("📚 Number of Chapters", 4, 30, 10)
    model = st.selectbox("🤖 AI Model", MODELS)
    img_model = st.selectbox("🖼️ Image Model", list(IMAGE_MODELS))

if st.button("🚀 Generate Your Book"):
    with st.spinner("✨ Crafting your immersive book..."):
        outline = call_openrouter(f"Create a detailed outline for a {TONE_MAP[tone]} {genre} novel: {prompt}", model)
        sections = ["Foreword", "Introduction"] + [f"Chapter {i+1}" for i in range(chapters)] + ["Final Words"]
        book = {}
        for sec in sections:
            book[sec] = call_openrouter(f"Write immersive content for '{sec}': {outline}", model)
            generate_image(book[sec], img_model, sec)
        cover = generate_image(f"Cinematic book cover: {prompt}, {genre}, {tone}", img_model, "cover")
        characters = generate_characters(outline, genre, TONE_MAP[tone], model)
        st.session_state.update({"book": book, "outline": outline, "cover": cover, "characters": characters})
        st.success("📖 Your book is ready!")

# Display generated content
if "book" in st.session_state:
    st.header("Your Generated Book")
    
    with st.expander("📔 Book Cover"):
        if st.session_state.cover:
            st.image(st.session_state.cover, use_column_width=True)
        else:
            st.warning("No cover generated yet")
    
    with st.expander("📝 Full Outline"):
        st.markdown(f"```\n{st.session_state.outline}\n```")
    
    with st.expander("👥 Character Bios"):
        for char in st.session_state.characters:
            with st.container():
                cols = st.columns([1,3])
                cols[0].subheader(char['name'])
                cols[1].write(f"**Role:** {char['role']}  \n**Personality:** {char['personality']}  \n**Appearance:** {char['appearance']}")
    
    for section, content in st.session_state.book.items():
        with st.expander(f"📜 {section}"):
            col1, col2 = st.columns([3,2])
            with col1:
                st.write(content)
                with NamedTemporaryFile(suffix=".mp3") as tf:
                    text_to_speech(content, tf.name)
                    audio_bytes = open(tf.name, "rb").read()
                    st.audio(audio_bytes, format="audio/mp3")
            with col2:
                if st.session_state.image_cache.get(section):
                    st.image(st.session_state.image_cache[section])
                else:
                    st.warning("No image generated for this section")

render_sidebar()
