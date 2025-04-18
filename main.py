import os
import json
import requests
import zipfile
import base64
import replicate
from docx import Document
from docx.shared import Inches
from fpdf import FPDF
from tempfile import NamedTemporaryFile
from gtts import gTTS
from PIL import Image
from io import BytesIO
import streamlit as st

# --- Constants and Configurations ---
LOGO_URL = "https://raw.githubusercontent.com/Prosocr3ature/NarrativaX/main/logo.png"
MAX_TOKENS = 1800
IMAGE_SIZE = (768, 1024)

st.set_page_config(page_title="NarrativaX", page_icon="🪶", layout="wide")

# --- Environment Setup ---
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN

# --- Genre/Tone Configuration ---
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

GENRES = [
    "Adventure", "Fantasy", "Dark Fantasy", "Romance", "Thriller", "Mystery",
    "Drama", "Sci-Fi", "Slice of Life", "Horror", "Crime", "LGBTQ+", "Action",
    "Psychological", "Historical Fiction", "Supernatural", "Steampunk",
    "Cyberpunk", "Post-Apocalyptic", "Surreal", "Noir", "Erotica", "NSFW",
    "Hardcore", "BDSM", "Futanari", "Incubus/Succubus", "Monster Romance",
    "Dubious Consent", "Voyeurism", "Yaoi", "Yuri", "Taboo Fantasy"
]

IMAGE_MODELS = {
    "Realistic Vision v5.1": "lucataco/realistic-vision-v5.1:2c8e954decbf70b7607a4414e5785ef9e4de4b8c51d50fb8b8b349160e0ef6bb",
    "Reliberate V3 (NSFW)": "asiryan/reliberate-v3:d70438fcb9bb7adb8d6e59cf236f754be0b77625e984b8595d1af02cdf034b29"
}

# --- Session State Initialization ---
if 'image_cache' not in st.session_state:
    st.session_state.image_cache = {}
for key in ['book', 'outline', 'cover', 'characters']:
    st.session_state.setdefault(key, None)

# --- Core Functions ---
def call_openrouter(prompt: str, model: str) -> str:
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.95,
        "max_tokens": MAX_TOKENS
    }
    response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()

def generate_image(prompt: str, model_key: str, id_key: str) -> Image.Image:
    if id_key in st.session_state.image_cache:
        return st.session_state.image_cache[id_key]
    
    try:
        output = replicate.run(
            IMAGE_MODELS[model_key],
            input={
                "prompt": prompt[:300],
                "num_inference_steps": 30,
                "guidance_scale": 7.5,
                "width": IMAGE_SIZE[0],
                "height": IMAGE_SIZE[1]
            }
        )
        
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

def generate_characters(outline: str, genre: str, tone: str, model: str) -> list:
    prompt = f"""Create vivid characters for a {tone} {genre} novel in JSON format.
    Outline: {outline}
    Format: [{{"name": "", "role": "", "personality": "", "appearance": ""}}]"""
    
    try:
        return json.loads(call_openrouter(prompt, model))
    except json.JSONDecodeError:
        return [{"name": "Unnamed", "role": "Unknown", "personality": "N/A", "appearance": ""}]

# --- Document Generation Functions ---
def create_docx(book_data: dict, images: dict, characters: list, output_path: str):
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

def create_pdf(book_data: dict, images: dict, characters: list, output_path: str):
    pdf = FPDF()
    pdf.set_auto_page_break(True, margin=15)
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

# --- UI Components ---
def render_sidebar():
    with st.sidebar:
        st.markdown(f'<img src="{LOGO_URL}" width="180" style="margin-bottom:20px">', unsafe_allow_html=True)
        
        # Project Management
        if st.button("💾 Save Project"):
            try:
                with open("session.json", "w") as f:
                    json.dump({
                        'book': st.session_state.book,
                        'outline': st.session_state.outline,
                        'cover': st.session_state.cover,
                        'characters': st.session_state.characters,
                        'image_cache': st.session_state.image_cache
                    }, f)
                st.success("Project saved successfully!")
            except Exception as e:
                st.error(f"Save failed: {str(e)}")

        if st.button("📂 Load Project"):
            try:
                with open("session.json", "r") as f:
                    data = json.load(f)
                    st.session_state.update(data)
                st.success("Project loaded successfully!")
            except Exception as e:
                st.error(f"Load failed: {str(e)}")

        # Export System
        st.subheader("Export Options")
        if st.button("📦 Export Full Package"):
            with st.spinner("Preparing export package..."):
                try:
                    with NamedTemporaryFile(delete=False, suffix=".zip") as tmpfile:
                        with zipfile.ZipFile(tmpfile.name, 'w') as zipf:
                            # Generate and add documents
                            create_docx(st.session_state.book, st.session_state.image_cache, 
                                      st.session_state.characters, "book.docx")
                            create_pdf(st.session_state.book, st.session_state.image_cache,
                                     st.session_state.characters, "book.pdf")
                            zipf.write("book.docx")
                            zipf.write("book.pdf")
                            
                            # Add audio files
                            for i, (sec, content) in enumerate(st.session_state.book.items()):
                                audio_path = f"chapter_{i+1}.mp3"
                                text_to_speech(content, audio_path)
                                zipf.write(audio_path)
                                os.remove(audio_path)
                            
                            os.remove("book.docx")
                            os.remove("book.pdf")
                        
                        with open(tmpfile.name, "rb") as f:
                            st.download_button(
                                "⬇️ Download ZIP",
                                f.read(),
                                file_name="book_package.zip",
                                mime="application/zip"
                            )
                        os.remove(tmpfile.name)
                except Exception as e:
                    st.error(f"Export failed: {str(e)}")

# --- Main Interface ---
st.markdown(f'<img src="{LOGO_URL}" width="60" style="float:right">', unsafe_allow_html=True)
st.title("NarrativaX — Immersive AI Book Creator")

# --- Input Section ---
with st.container():
    prompt = st.text_area("🖋️ Describe your story concept", height=120, 
                        placeholder="A young wizard discovers a hidden power...")
    col1, col2, col3 = st.columns(3)
    genre = col1.selectbox("📖 Genre", GENRES)
    tone = col2.selectbox("🎨 Tone", list(TONE_MAP))
    chapters = col3.slider("📚 Number of Chapters", 4, 30, 10)
    model = st.selectbox("🤖 AI Model", [
        "nothingiisreal/mn-celeste-12b",
        "openchat/openchat-3.5-0106",
        "gryphe/mythomax-l2-13b"
    ])
    img_model = st.selectbox("🖼️ Image Model", list(IMAGE_MODELS))

# --- Generation Flow ---
if st.button("🚀 Generate Your Book"):
    with st.spinner("✨ Crafting your immersive book..."):
        try:
            # Generate core content
            outline = call_openrouter(
                f"Create detailed outline for a {TONE_MAP[tone]} {genre} novel: {prompt}", 
                model
            )
            sections = ["Foreword"] + [f"Chapter {i+1}" for i in range(chapters)] + ["Epilogue"]
            
            # Generate chapters and images
            book = {}
            for sec in sections:
                book[sec] = call_openrouter(f"Write immersive '{sec}' content: {outline}", model)
                generate_image(book[sec], img_model, sec)
            
            # Generate additional assets
            st.session_state.cover = generate_image(
                f"Cinematic book cover: {prompt}, {genre}, {tone}", 
                img_model, 
                "cover"
            )
            st.session_state.characters = generate_characters(outline, genre, TONE_MAP[tone], model)
            
            # Update session state
            st.session_state.update({
                "book": book,
                "outline": outline
            })
            st.success("📖 Your book is ready!")
            
        except Exception as e:
            st.error(f"Generation failed: {str(e)}")

# --- Display Generated Content ---
if st.session_state.book:
    st.header("Your Generated Book")
    
    # Book Cover Section
    with st.expander("📔 Book Cover", expanded=True):
        if st.session_state.cover:
            try:
                st.image(st.session_state.cover, use_container_width=True)
            except Exception as e:
                st.error(f"Error displaying cover: {str(e)}")
                st.session_state.cover = None
        else:
            st.warning("No cover generated yet")
    
    # Outline Section
    with st.expander("📝 Full Outline"):
        st.markdown(f"```\n{st.session_state.outline}\n```")
    
    # Character Bios
    with st.expander("👥 Character Bios"):
        for char in st.session_state.characters:
            with st.container():
                cols = st.columns([1, 3])
                cols[0].subheader(char['name'])
                cols[1].write(f"""
                **Role:** {char['role']}  
                **Personality:** {char['personality']}  
                **Appearance:** {char['appearance']}
                """)

    # Chapter Content
    for section, content in st.session_state.book.items():
        with st.expander(f"📜 {section}"):
            col1, col2 = st.columns([3, 2])
            
            with col1:
                st.write(content)
                with NamedTemporaryFile(suffix=".mp3") as tf:
                    text_to_speech(content, tf.name)
                    audio_bytes = open(tf.name, "rb").read()
                    st.audio(audio_bytes, format="audio/mp3")
            
            with col2:
                if st.session_state.image_cache.get(section):
                    try:
                        st.image(
                            st.session_state.image_cache[section],
                            use_container_width=True
                        )
                    except Exception as e:
                        st.error(f"Image error: {str(e)}")
                        st.session_state.image_cache[section] = None
                else:
                    st.warning("No image generated for this section")

# --- Render Sidebar ---
render_sidebar()
