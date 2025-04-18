import os
import json
import requests
import zipfile
import random
import replicate
from docx import Document
from docx.shared import Inches
from fpdf import FPDF
from tempfile import NamedTemporaryFile
from gtts import gTTS
from PIL import Image
from io import BytesIO
import streamlit as st

# ========== CONSTANTS ==========
LOGO_URL = "https://raw.githubusercontent.com/Prosocr3ature/NarrativaX/main/logo.png"
MAX_TOKENS = 1800
IMAGE_SIZE = (768, 1024)
LOADING_MESSAGES = [
    "Sharpening quills...", "Mixing metaphorical ink...",
    "Convincing characters to behave...", "Battling clichés...",
    "Negotiating with plot holes...", "Summoning muses...",
    "Where we're going, we don't need chapters...",
    "Wordsmithing in progress...", "The pen is mightier... loading...",
    "Subverting expectations..."
]
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
    "Adventure", "Fantasy", "Dark Fantasy", "Romance", "Thriller",
    "Mystery", "Drama", "Sci-Fi", "Slice of Life", "Horror", "Crime",
    "LGBTQ+", "Action", "Psychological", "Historical Fiction",
    "Supernatural", "Steampunk", "Cyberpunk", "Post-Apocalyptic",
    "Surreal", "Noir", "Erotica", "NSFW", "Hardcore", "BDSM",
    "Futanari", "Incubus/Succubus", "Monster Romance",
    "Dubious Consent", "Voyeurism", "Yaoi", "Yuri", "Taboo Fantasy"
]
IMAGE_MODELS = {
    "Realistic Vision v5.1": "lucataco/realistic-vision-v5.1:2c8e954decbf70b7607a4414e5785ef9e4de4b8c51d50fb8b8b349160e0ef6bb",
    "Reliberate V3 (NSFW)": "asiryan/reliberate-v3:d70438fcb9bb7adb8d6e59cf236f754be0b77625e984b8595d1af02cdf034b29"
}

# ========== INITIALIZATION ==========
st.set_page_config(page_title="NarrativaX", page_icon="🪶", layout="wide")

if 'image_cache' not in st.session_state:
    st.session_state.image_cache = {}
for key in ['book', 'outline', 'cover', 'characters', 'gen_progress']:
    st.session_state.setdefault(key, None)

# ========== CORE FUNCTIONS ==========
def call_openrouter(prompt: str, model: str) -> str:
    headers = {"Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}"}
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
        st.error(f"🖼️ Image generation failed: {str(e)}")
    return None

def generate_book_components():
    config = st.session_state.gen_progress
    progress_bar = st.progress(0)
    status_container = st.empty()
    preview_column = st.columns(1)[0]
    
    sections_count = config['chapters'] + 2
    total_steps = 3 + (sections_count * 2)
    current_step = 0
    book = {}

    try:
        # Generate Outline
        with status_container.status("🔮 Crafting story structure...", expanded=True) as status:
            outline = call_openrouter(
                f"Create detailed outline for {TONE_MAP[config['tone']]} {config['genre']} novel: {config['prompt']}", 
                config['model']
            )
            current_step += 1
            progress_bar.progress(current_step/total_steps)
            status.update(label="📜 Outline complete!", state="complete")
            preview_column.markdown(f"**Outline Preview:**\n```\n{outline[:200]}...\n```")

        # Generate Chapters
        sections = ["Foreword"] + [f"Chapter {i+1}" for i in range(config['chapters'])] + ["Epilogue"]
        for sec in sections:
            # Text Generation
            with status_container.status(f"📖 Writing {sec}...", expanded=True) as status:
                book[sec] = call_openrouter(
                    f"Write immersive '{sec}' content: {outline}",
                    config['model']
                )
                current_step += 1
                progress_bar.progress(current_step/total_steps)
                status.update(label=f"✅ {sec} text complete!", state="complete")
                preview_column.markdown(f"**{sec} Preview:**\n{book[sec][:150]}...")

            # Image Generation
            with status_container.status(f"🎨 Painting visual for {sec}...", expanded=True) as status:
                generate_image(book[sec], config['img_model'], sec)
                current_step += 1
                progress_bar.progress(current_step/total_steps)
                status.update(label=f"🖼️ {sec} image complete!", state="complete")
                if st.session_state.image_cache.get(sec):
                    preview_column.image(
                        st.session_state.image_cache[sec], 
                        use_container_width=True,
                        caption=f"Visual for {sec}"
                    )

        # Generate Cover
        with status_container.status("🖼️ Crafting masterpiece cover...", expanded=True) as status:
            st.session_state.cover = generate_image(
                f"Cinematic cover: {config['prompt']}, {config['genre']}, {config['tone']}", 
                config['img_model'], 
                "cover"
            )
            current_step += 1
            progress_bar.progress(current_step/total_steps)
            status.update(label="🎉 Cover art complete!", state="complete")
            if st.session_state.cover:
                preview_column.image(st.session_state.cover, use_container_width=True)

        # Generate Characters
        with status_container.status("👥 Bringing characters to life...", expanded=True) as status:
            st.session_state.characters = json.loads(call_openrouter(
                f"""Create vivid characters for {config['genre']} novel in JSON format:
                {outline}
                Format: [{{"name":"","role":"","personality":"","appearance":""}}]""",
                config['model']
            ))
            current_step += 1
            progress_bar.progress(current_step/total_steps)
            status.update(label="🤩 Characters ready!", state="complete")
            preview_column.markdown("**Main Characters:**\n" + "\n".join(
                [f"- {char['name']} ({char['role']})" for char in st.session_state.characters[:3]]
            ))

        st.session_state.book = book
        st.balloons()
        st.success("📖 Your Immersive Book is Ready!")
        st.session_state.gen_progress = None

    except Exception as e:
        st.error(f"🚨 Generation Interrupted: {str(e)}")
        st.session_state.gen_progress = None

# ========== UI COMPONENTS ==========
def dramatic_logo():
    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@500&family=Cinzel:wght@500&display=swap');
        @keyframes float {{
            0% {{ transform: translate(-50%, -55%) rotate(-5deg); }}
            50% {{ transform: translate(-50%, -60%) rotate(5deg); }}
            100% {{ transform: translate(-50%, -55%) rotate(-5deg); }}
        }}
        .logo-overlay {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.9);
            z-index: 9998;
        }}
        .logo-container {{
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            text-align: center;
            z-index: 9999;
        }}
        .logo-img {{
            width: min(80vw, 600px);
            animation: float 3s ease-in-out infinite;
            filter: drop-shadow(0 0 20px #ff69b480);
        }}
        .loading-message {{
            font-family: 'Playfair Display', serif;
            font-size: clamp(1.5rem, 4vw, 2.5rem);
            margin-top: 2rem;
            color: #ff69b4;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }}
        .quote {{
            font-family: 'Cinzel', serif;
            font-size: clamp(1rem, 2.5vw, 1.4rem);
            color: #fff;
            margin-top: 1.5rem;
            letter-spacing: 0.1em;
            opacity: 0.8;
        }}
    </style>
    <div class="logo-overlay"></div>
    <div class="logo-container">
        <img class="logo-img" src="{LOGO_URL}">
        <div class="loading-message">{random.choice(LOADING_MESSAGES)}</div>
        <div class="quote">"Where ink meets imagination"</div>
    </div>
    """, unsafe_allow_html=True)

def main_interface():
    if st.session_state.get('gen_progress'):
        dramatic_logo()
        generate_book_components()
    else:
        st.markdown(f'<img src="{LOGO_URL}" width="300" style="float:right; margin:-50px -20px 0 0">', unsafe_allow_html=True)
        st.title("NarrativaX — Immersive AI Book Creator")
        
        with st.container():
            prompt = st.text_area("🖋️ Your Story Concept", height=120,
                                placeholder="A forbidden romance between...")
            col1, col2, col3 = st.columns(3)
            genre = col1.selectbox("📖 Genre", GENRES)
            tone = col2.selectbox("🎨 Tone", list(TONE_MAP))
            chapters = col3.slider("📚 Chapters", 4, 30, 10)
            model = col1.selectbox("🤖 AI Model", ["nothingiisreal/mn-celeste-12b", "gryphe/mythomax-l2-13b"])
            img_model = col2.selectbox("🖼️ Image Model", list(IMAGE_MODELS))

            if st.button("🚀 Create Book", use_container_width=True):
                st.session_state.gen_progress = {
                    "prompt": prompt, "genre": genre, "tone": tone,
                    "chapters": chapters, "model": model, "img_model": img_model
                }
                st.rerun()

def render_sidebar():
    with st.sidebar:
        st.markdown(f'<img src="{LOGO_URL}" width="200" style="margin-bottom:20px">', unsafe_allow_html=True)
        
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
                st.success("Project saved!")
            except Exception as e:
                st.error(f"Save failed: {str(e)}")

        if st.button("📂 Load Project"):
            try:
                with open("session.json", "r") as f:
                    st.session_state.update(json.load(f))
                st.success("Project loaded!")
            except Exception as e:
                st.error(f"Load failed: {str(e)}")

        # Export
        if st.session_state.book and st.button("📦 Export Book"):
            with st.spinner("Packaging..."):
                try:
                    with NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
                        with zipfile.ZipFile(tmp.name, 'w') as zipf:
                            # Add DOCX
                            doc = Document()
                            for sec, content in st.session_state.book.items():
                                doc.add_heading(sec, level=1)
                                doc.add_paragraph(content)
                                if st.session_state.image_cache.get(sec):
                                    try:
                                        img = st.session_state.image_cache[sec]
                                        img_io = BytesIO()
                                        img.save(img_io, format='PNG')
                                        doc.add_picture(img_io, width=Inches(5))
                                    except Exception as e:
                                        st.error(f"Error adding image: {e}")
                            doc.save("book.docx")
                            zipf.write("book.docx")
                            os.remove("book.docx")

                            # Add PDF
                            pdf = FPDF()
                            pdf.add_page()
                            pdf.set_font("Arial", size=12)
                            for sec, content in st.session_state.book.items():
                                pdf.set_font("Arial", 'B', 16)
                                pdf.cell(200, 10, txt=sec, ln=True)
                                pdf.set_font("Arial", size=12)
                                pdf.multi_cell(0, 10, txt=content)
                            pdf.output("book.pdf")
                            zipf.write("book.pdf")
                            os.remove("book.pdf")

                            # Add Audio
                            for i, (sec, content) in enumerate(st.session_state.book.items()):
                                audio_path = f"chapter_{i+1}.mp3"
                                tts = gTTS(text=content, lang='en')
                                tts.save(audio_path)
                                zipf.write(audio_path)
                                os.remove(audio_path)

                        with open(tmp.name, "rb") as f:
                            st.download_button("⬇️ Download", f.read(), "book.zip")
                        os.remove(tmp.name)
                except Exception as e:
                    st.error(f"Export failed: {str(e)}")

def display_content():
    if st.session_state.book:
        st.header("Your Generated Book")
        
        with st.expander("📔 Book Cover", expanded=True):
            if st.session_state.cover:
                try:
                    st.image(st.session_state.cover, use_container_width=True)
                except Exception as e:
                    st.error(f"Error displaying cover: {str(e)}")
            else:
                st.warning("No cover generated yet")
        
        with st.expander("📝 Full Outline"):
            st.markdown(f"```\n{st.session_state.outline}\n```")
        
        with st.expander("👥 Character Bios"):
            for char in st.session_state.characters:
                with st.container():
                    cols = st.columns([1, 3])
                    cols[0].subheader(char.get('name', 'Unnamed'))
                    cols[1].write(f"""
                    **Role:** {char.get('role', 'Unknown')}  
                    **Personality:** {char.get('personality', 'N/A')}  
                    **Appearance:** {char.get('appearance', 'Not specified')}
                    """)

        for section, content in st.session_state.book.items():
            with st.expander(f"📜 {section}"):
                col1, col2 = st.columns([3, 2])
                with col1:
                    st.write(content)
                    with NamedTemporaryFile(suffix=".mp3") as tf:
                        tts = gTTS(text=content, lang='en')
                        tts.save(tf.name)
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
                    else:
                        st.warning("No image for this section")

# ========== RUN APPLICATION ==========
if __name__ == "__main__":
    main_interface()
    render_sidebar()
    display_content()
