
import os
import json
import requests
import zipfile
import random
import replicate
import threading
import queue
import base64
import time
from html import escape
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from docx import Document
from docx.shared import Inches
from fpdf import FPDF
from tempfile import NamedTemporaryFile
from gtts import gTTS
from PIL import Image
from io import BytesIO
import streamlit as st
from streamlit.runtime.scriptrunner import add_script_run_ctx

# ========== INITIALIZATION ==========
st.set_page_config(
    page_title="NarrativaX",
    page_icon="🪶",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ========== CONSTANTS ==========
LOGO_PATH = "logo.png"  # Local logo file
MAX_TOKENS = 1800
IMAGE_SIZE = (768, 1024)
PROGRESS_QUEUE = queue.Queue()
TIMEOUT = 600  # 10 minutes for big books

SAFE_LOADING_MESSAGES = [
    "Sharpening quills...", "Mixing metaphorical ink...",
    "Convincing characters to behave...", "Battling clichés...",
    "Negotiating with plot holes...", "Summoning muses...",
    "Where we're going, we don't need chapters...",
    "Wordsmithing in progress...", "The pen is mightier... loading...",
    "Subverting expectations...", "Crushing doubt with discipline..."
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
    "Philosophical": "deep, reflective, thoughtful",
    "Motivational": "uplifting, driven, self-empowering",
    "Educational": "clear, structured, informative"
}

GENRES = [
    "Adventure", "Fantasy", "Dark Fantasy", "Romance", "Thriller",
    "Mystery", "Drama", "Sci-Fi", "Slice of Life", "Horror", "Crime",
    "LGBTQ+", "Action", "Psychological", "Historical Fiction",
    "Supernatural", "Steampunk", "Cyberpunk", "Post-Apocalyptic",
    "Surreal", "Noir", "Erotica", "NSFW", "Hardcore", "BDSM",
    "Futanari", "Incubus/Succubus", "Monster Romance",
    "Dubious Consent", "Voyeurism", "Yaoi", "Yuri", "Taboo Fantasy",
    "Personal Development", "Self-Help", "Mindset", "Productivity",
    "Leadership", "Sales", "Health & Fitness", "Finance", "Spirituality",
    "Psychology", "Startup & Business", "How-To", "Nonfiction"
]

IMAGE_MODELS = {
    "Realistic Vision v5.1": "lucataco/realistic-vision-v5.1:2c8e954decbf70b7607a4414e5785ef9e4de4b8c51d50fb8b8b349160e0ef6bb",
    "Reliberate V3 (NSFW)": "asiryan/reliberate-v3:d70438fcb9bb7adb8d6e59cf236f754be0b77625e984b8595d1af02cdf034b29"
}

# ========== SESSION STATE ==========
for key in ['book', 'outline', 'cover', 'characters', 'gen_progress']:
    st.session_state.setdefault(key, None)
st.session_state.setdefault('image_cache', {})
st.session_state.setdefault('library', {})  # For local saved projects

# ========== API CALL FUNCTIONS ==========
def call_openrouter(prompt: str, model: str) -> str:
    headers = {"Authorization": f"Bearer {st.secrets['OPENROUTER_API_KEY']}"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.95,
        "max_tokens": MAX_TOKENS
    }
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=90
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        PROGRESS_QUEUE.put(("ERROR", f"API Error: {str(e)}", 0, ""))
        raise

def generate_image(prompt: str, model_key: str, id_key: str) -> Image.Image:
    try:
        if id_key in st.session_state.image_cache:
            cached = st.session_state.image_cache[id_key]
            return base64_to_pil(cached) if isinstance(cached, str) else cached

        output = replicate.run(
            IMAGE_MODELS[model_key],
            input={
                "prompt": f"{escape(prompt[:250])} {random.choice(['intricate details', 'cinematic lighting', '8k resolution'])}",
                "negative_prompt": "text, watermark, deformed, blurry",
                "num_inference_steps": 35,
                "width": IMAGE_SIZE[0],
                "height": IMAGE_SIZE[1]
            }
        )

        if output and isinstance(output, list):
            response = requests.get(output[0], timeout=30)
            response.raise_for_status()
            image = Image.open(BytesIO(response.content)).convert("RGB")
            st.session_state.image_cache[id_key] = pil_to_base64(image)
            return image
    except Exception as e:
        PROGRESS_QUEUE.put(("ERROR", f"Image Error: {str(e)}", 0, ""))
    return None

def pil_to_base64(image: Image.Image) -> str:
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

def base64_to_pil(b64_str: str) -> Image.Image:
    return Image.open(BytesIO(base64.b64decode(b64_str)))

def background_generation_task():
    try:
        config = st.session_state.gen_progress
        total_steps = 4 + (config['chapters'] * 3)
        current_step = 0

        def heartbeat():
            while st.session_state.gen_progress:
                PROGRESS_QUEUE.put(("💓", "Processing...", current_step / total_steps, ""))
                time.sleep(10)

        heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
        add_script_run_ctx(heartbeat_thread)
        heartbeat_thread.start()

        # Phase 1: Concept Development
        PROGRESS_QUEUE.put(("🌌", "Developing concept...", current_step / total_steps, ""))
        prompt = escape(config['prompt'])
        genre = config['genre']
        tone = TONE_MAP.get(config['tone'], "neutral")
        model = config['model']

        if genre.lower() in ["personal development", "self-help", "nonfiction", "how-to", "business"]:
            concept_prompt = f"""Write a compelling and detailed book premise for a {genre} book based on this idea: {prompt}.
            Frame it as a personal growth or educational book. Include key takeaways and a central transformation theme."""
        else:
            concept_prompt = f"""Develop a {genre} story premise with a strong hook, characters and tone: {prompt}"""

        premise = call_openrouter(concept_prompt, model)
        current_step += 1

        # Phase 2: Outline
        PROGRESS_QUEUE.put(("📜", "Outlining chapters...", current_step / total_steps, premise[:200]))
        outline_prompt = f"""Create a full outline for a {tone} {genre} book with this concept: {premise}
        Include chapter breakdowns, progression, learning or plot arcs. Begin with a title and table of contents."""
        outline = call_openrouter(outline_prompt, model)
        st.session_state.outline = outline
        current_step += 1

        # Phase 3: Chapter Writing
        sections = ["Foreword"] + [f"Chapter {i+1}" for i in range(config['chapters'])] + ["Conclusion"]
        book = {}

        for sec in sections:
            PROGRESS_QUEUE.put(("✍️", f"Writing {sec}...", current_step / total_steps, sec))
            content_prompt = f"""Write the full {sec} for a {tone} {genre} book based on this outline:
            {outline}
            Keep it immersive and complete."""
            content = call_openrouter(content_prompt, model)
            book[sec] = content
            current_step += 1

            PROGRESS_QUEUE.put(("🎨", f"Illustrating {sec}...", current_step / total_steps, content[:100]))
            generate_image(f"{content[:150]} {tone} illustration", config['img_model'], sec)
            current_step += 1

        # Phase 4: Final assets
        PROGRESS_QUEUE.put(("🖼️", "Creating cover art...", current_step / total_steps, genre))
        st.session_state.cover = generate_image(
            f"Cover art for a {genre} book titled '{prompt[:40]}...'", config['img_model'], "cover"
        )
        current_step += 1

        PROGRESS_QUEUE.put(("👥", "Generating characters or concepts...", current_step / total_steps, ""))
        char_prompt = f"""Generate 4-8 unique characters or key personas (if nonfiction: make them use cases, speakers or case studies) based on this outline: {outline}.
        Format as a list of JSON with name, role, personality, appearance."""
        characters = json.loads(call_openrouter(char_prompt, model))
        st.session_state.characters = characters
        current_step += 1

        st.session_state.book = book
        PROGRESS_QUEUE.put(("✅", "Book complete!", 1.0, ""))
    except Exception as e:
        PROGRESS_QUEUE.put(("ERROR", f"Generation failed: {str(e)}", 0, ""))
        st.session_state.gen_progress = None

def background_generation_wrapper():
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(background_generation_task)
            future.result(timeout=TIMEOUT)
    except TimeoutError:
        PROGRESS_QUEUE.put(("ERROR", "Generation timed out after 10 minutes", 0, ""))
    finally:
        st.session_state.gen_progress = None

def dramatic_logo():
    safe_message = escape(random.choice(SAFE_LOADING_MESSAGES))
    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@500&display=swap');
        @keyframes float {{
            0% {{ transform: translate(-50%, -55%) rotate(-3deg); }}
            50% {{ transform: translate(-50%, -60%) rotate(3deg); }}
            100% {{ transform: translate(-50%, -55%) rotate(-3deg); }}
        }}
        .logo-overlay {{
            position: fixed;
            top: 0; left: 0;
            width: 100vw; height: 100vh;
            background: radial-gradient(ellipse at center, #0a0a0a 0%, #000000 100%);
            z-index: 1000;
        }}
        .logo-container {{
            position: fixed;
            top: 50%; left: 50%;
            transform: translate(-50%, -50%);
            text-align: center;
            z-index: 1001;
        }}
        .logo-img {{
            width: min(60vw, 300px);
            animation: float 4s ease-in-out infinite;
            filter: drop-shadow(0 0 15px #ff69b460);
        }}
        .loading-message {{
            font-family: 'Playfair Display', serif;
            font-size: clamp(1.5rem, 3vw, 2.5rem);
            margin-top: 1rem;
            color: #ff69b4;
            animation: pulse 1.5s infinite;
        }}
        @keyframes pulse {{
            0%, 100% {{ opacity: 0.6; text-shadow: 0 0 10px #ff69b4; }}
            50% {{ opacity: 1; text-shadow: 0 0 20px #ff1493; }}
        }}
        .progress-bar {{
            height: 12px !important;
            border-radius: 8px;
            background: #ffffff22;
            margin-top: 1.5rem;
        }}
        .progress-bar::-webkit-progress-value {{
            background: linear-gradient(90deg, #ff69b4, #ff1493);
            border-radius: 8px;
        }}
    </style>
    <div class="logo-overlay"></div>
    <div class="logo-container">
        <img class="logo-img" src="logo.png">
        <div class="loading-message">{safe_message}</div>
    </div>
    """, unsafe_allow_html=True)

def progress_animation():
    try:
        if not PROGRESS_QUEUE.empty():
            status = PROGRESS_QUEUE.get()
            with st.empty() as container:
                while True:
                    if status[0] == "COMPLETE":
                        st.balloons()
                        break
                    elif status[0] == "ERROR":
                        st.error(f"❌ {escape(str(status[1]))}")
                        break
                    else:
                        emoji, msg, prog, preview = status
                        safe_preview = escape(str(preview))[:150] + "..." if preview else ""
                        container.markdown(f"""
                        <div style="text-align:center; padding: 1rem">
                            <div style="font-size:2rem; animation: pulse 1.5s infinite">{emoji}</div>
                            <h4>{escape(msg)}</h4>
                            <progress class="progress-bar" value="{prog}" max="1"></progress>
                            {f'<div style="color:#bbb;margin-top:1rem">{safe_preview}</div>' if preview else ''}
                        </div>
                        """, unsafe_allow_html=True)
                    try:
                        status = PROGRESS_QUEUE.get(timeout=0.3)
                    except queue.Empty:
                        break
    except Exception as e:
        st.error(f"Progress error: {escape(str(e))[:200]}...")

def show_start_ui():
    st.markdown("""
        <style>
            @media (max-width: 768px) {
                .stTextArea textarea, .stSelectbox select, .stSlider input, .stButton button {
                    font-size: 16px !important;
                }
                .element-container { padding: 0 5px !important; }
            }
            .stProgress > div > div > div {
                background-color: #ff69b4 !important;
            }
        </style>
    """, unsafe_allow_html=True)

    st.image("logo.png", width=180)
    st.title("NarrativaX — Ultimate AI Book Creator")

    prompt = st.text_area("✍️ What should your book be about?", height=120, placeholder="Ex: How to break free from self-doubt...")

    col1, col2, col3 = st.columns(3)
    genre = col1.selectbox("Genre", GENRES)
    tone = col2.selectbox("Tone", list(TONE_MAP))
    chapters = col3.slider("Number of chapters", 4, 30, 10)

    model = col1.selectbox("AI Model", ["nothingiisreal/mn-celeste-12b", "gryphe/mythomax-l2-13b"])
    img_model = col2.selectbox("Image Model", list(IMAGE_MODELS))

    if st.button("🚀 Generate Full Book", type="primary"):
        st.session_state.image_cache.clear()
        st.session_state.cover = None
        st.session_state.book = None
        st.session_state.outline = None
        st.session_state.characters = None
        st.session_state.gen_progress = {
            "prompt": prompt, "genre": genre, "tone": tone,
            "chapters": chapters, "model": model, "img_model": img_model
        }
        gen_thread = threading.Thread(target=background_generation_wrapper, daemon=True)
        add_script_run_ctx(gen_thread)
        gen_thread.start()
        st.rerun()

def display_generated_book():
    if not st.session_state.book:
        st.warning("No book has been generated yet.")
        return

    st.header("📚 Your AI-Generated Book")

    if st.session_state.cover:
        st.image(st.session_state.cover, caption="Cover", use_container_width=True)

    with st.expander("📑 Book Outline", expanded=False):
        st.markdown(f"```markdown\n{st.session_state.outline}\n```")

    with st.expander("🧬 Characters"):
        if st.session_state.characters:
            char_table = []
            for i, char in enumerate(st.session_state.characters):
                with st.container():
                    cols = st.columns([1, 2, 1])
                    cols[0].markdown(f"**{char.get('name', f'Character {i+1}')}**")
                    cols[1].markdown(f"""
                    - Role: {char.get('role', 'N/A')}
                    - Personality: {char.get('personality', 'N/A')}
                    - Appearance: {char.get('appearance', 'N/A')}
                    """)
                    with cols[2]:
                        if st.button(f"❌ Remove", key=f"del_char_{i}"):
                            del st.session_state.characters[i]
                            st.rerun()
                        if st.button(f"🔄 Regenerate", key=f"regen_char_{i}"):
                            regen_prompt = f"""Regenerate a single character in JSON format with similar context:
                            Outline: {st.session_state.outline}
                            Tone: {TONE_MAP[st.session_state.gen_progress['tone']]}
                            Genre: {st.session_state.gen_progress['genre']}
                            Output format: [{{"name":"","role":"","personality":"","appearance":""}}]"""
                            try:
                                result = json.loads(call_openrouter(regen_prompt, st.session_state.gen_progress['model']))
                                st.session_state.characters[i] = result[0]
                                st.success("Character regenerated!")
                            except Exception as e:
                                st.error(f"Failed to regenerate: {str(e)}")
                            st.rerun()
        else:
            st.warning("No characters were generated.")

    for i, (section, content) in enumerate(st.session_state.book.items()):
        with st.expander(f"📖 {section}", expanded=(i == 0)):
            col1, col2 = st.columns([3, 2])
            with col1:
                st.markdown(f"```text\n{content}\n```")
                with NamedTemporaryFile(suffix=".mp3", delete=False) as tf:
                    try:
                        gTTS(text=content, lang='en').save(tf.name)
                        st.audio(tf.name, format="audio/mp3")
                    except Exception as e:
                        st.warning(f"Audio error: {str(e)}")
            with col2:
                img = st.session_state.image_cache.get(section)
                if img:
                    if isinstance(img, str):
                        img = base64_to_pil(img)
                    st.image(img, use_container_width=True)
                else:
                    st.info("No illustration available for this section.")

def save_current_project():
    try:
        save_data = {
            "book": st.session_state.book,
            "outline": st.session_state.outline,
            "characters": st.session_state.characters,
            "image_cache": st.session_state.image_cache,
            "cover": pil_to_base64(st.session_state.cover) if st.session_state.cover else None,
        }
        with open("project.narrx", "w") as f:
            json.dump(save_data, f)
        st.success("✅ Project saved successfully.")
    except Exception as e:
        st.error(f"Save error: {str(e)}")

def load_existing_project():
    try:
        with open("project.narrx", "r") as f:
            data = json.load(f)

        st.session_state.book = data.get("book", {})
        st.session_state.outline = data.get("outline", "")
        st.session_state.characters = data.get("characters", [])
        st.session_state.image_cache = {
            k: base64_to_pil(v) if isinstance(v, str) else v
            for k, v in data.get("image_cache", {}).items()
        }
        if data.get("cover"):
            st.session_state.cover = base64_to_pil(data["cover"])
        st.success("✅ Project loaded successfully.")
    except Exception as e:
        st.error(f"Load error: {str(e)}")

def export_all_as_zip():
    try:
        with NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
            with zipfile.ZipFile(tmp.name, "w") as zipf:
                # DOCX Export
                doc = Document()
                for sec, content in st.session_state.book.items():
                    doc.add_heading(sec, level=1)
                    doc.add_paragraph(content)
                    if sec in st.session_state.image_cache:
                        img = st.session_state.image_cache[sec]
                        if isinstance(img, str):
                            img = base64_to_pil(img)
                        img_io = BytesIO()
                        img.save(img_io, format="PNG")
                        img_io.seek(0)
                        doc.add_picture(img_io, width=Inches(5))
                doc_path = "book.docx"
                doc.save(doc_path)
                zipf.write(doc_path)
                os.remove(doc_path)

                # PDF Export
                pdf = FPDF()
                pdf.set_auto_page_break(auto=True, margin=15)
                pdf.add_page()
                pdf.set_font("Arial", size=12)
                for sec, content in st.session_state.book.items():
                    pdf.set_font("Arial", 'B', 14)
                    pdf.cell(0, 10, sec, ln=True)
                    pdf.set_font("Arial", size=12)
                    pdf.multi_cell(0, 10, content)
                    pdf.ln()
                pdf_path = "book.pdf"
                pdf.output(pdf_path)
                zipf.write(pdf_path)
                os.remove(pdf_path)

                # MP3 Audio
                for i, (sec, content) in enumerate(st.session_state.book.items()):
                    with NamedTemporaryFile(delete=False, suffix=".mp3") as audio_tmp:
                        try:
                            tts = gTTS(text=content, lang='en')
                            tts.save(audio_tmp.name)
                            zipf.write(audio_tmp.name, f"{sec}.mp3")
                            os.remove(audio_tmp.name)
                        except Exception:
                            pass

            with open(tmp.name, "rb") as f:
                st.download_button("⬇️ Download Your Book ZIP", f.read(), "narrativax_project.zip")
            os.remove(tmp.name)
    except Exception as e:
        st.error(f"Export error: {str(e)}")

def render_project_buttons():
    with st.sidebar:
        st.markdown(f'<img src="logo.png" width="180" style="margin-bottom:20px;">', unsafe_allow_html=True)

        if st.button("💾 Save Project"):
            save_current_project()

        if st.button("📂 Load Project"):
            load_existing_project()

        if st.session_state.book:
            st.markdown("---")
            if st.button("📦 Export Everything"):
                export_all_as_zip()

def render_book_content():
    if not st.session_state.book:
        st.info("No book generated yet.")
        return

    st.header("📚 Your Complete Book")
    
    with st.expander("📔 Book Cover", expanded=True):
        if st.session_state.cover:
            st.image(st.session_state.cover, use_container_width=True)
        else:
            st.warning("No cover image available.")

    with st.expander("📝 Outline"):
        st.code(st.session_state.outline)

    with st.expander("👤 Character Bios"):
        for i, char in enumerate(st.session_state.characters):
            st.markdown(f"### {char.get('name', f'Character {i+1}')}")
            st.markdown(f"""
            **Role:** {char.get('role', 'Unknown')}  
            **Personality:** {char.get('personality', 'N/A')}  
            **Appearance:** {char.get('appearance', 'N/A')}
            """)
            col1, col2 = st.columns(2)
            with col1:
                if st.button(f"❌ Remove", key=f"remove_char_{i}"):
                    del st.session_state.characters[i]
                    st.rerun()
            with col2:
                if st.button(f"🔁 Regenerate", key=f"regen_char_{i}"):
                    prompt = f"Regenerate a new character to replace {char['name']} in a {st.session_state.gen_progress['genre']} book."
                    new_char_json = call_openrouter(
                        f"Generate one character in JSON: {prompt}", 
                        st.session_state.gen_progress['model']
                    )
                    try:
                        new_char = json.loads(new_char_json)[0]
                        st.session_state.characters[i] = new_char
                        st.rerun()
                    except Exception as e:
                        st.warning("Could not parse regenerated character.")

    for sec, content in st.session_state.book.items():
        with st.expander(f"📄 {sec}"):
            col1, col2 = st.columns([3, 2])
            with col1:
                st.markdown(content)
                try:
                    with NamedTemporaryFile(suffix=".mp3") as tf:
                        tts = gTTS(text=content, lang='en')
                        tts.save(tf.name)
                        st.audio(tf.name, format="audio/mp3")
                except Exception:
                    st.warning("Audio failed.")
            with col2:
                img = st.session_state.image_cache.get(sec)
                if img:
                    if isinstance(img, str):
                        img = base64_to_pil(img)
                    st.image(img, use_container_width=True)

def get_all_genres():
    return GENRES + [
        "Business", "Entrepreneurship", "Health", "Fitness",
        "Spirituality", "Productivity", "Finance", "Self-Esteem",
        "Mindset", "Leadership", "Coaching", "Sales", "Marketing",
        "Personal Growth", "Communication", "Habits", "Motivation",
        "Parenting", "Creativity", "Expert Guide", "Public Speaking",
        "Time Management", "Mental Health", "Emotional Intelligence"
    ]

def get_extended_tones():
    return list(TONE_MAP.keys()) + [
        "Motivational", "Instructive", "Insightful", "Witty",
        "Academic", "Journalistic", "Pragmatic", "Conversational"
    ]

def main():
    st.set_page_config(
        page_title="NarrativaX — AI Book Forge",
        page_icon="🪶",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    if st.session_state.get("gen_progress"):
        dramatic_logo()
        progress_animation()
        st.stop()

    st.markdown(f'<img src="logo.png" width="140" style="float:right; margin-top:-60px">', unsafe_allow_html=True)
    st.title("NarrativaX — Immersive AI Book Creator")

    with st.form("book_gen_form"):
        prompt = st.text_area("🖋️ What should your book be about?", height=100, placeholder="e.g. How to build unstoppable discipline in 30 days")
        genre = st.selectbox("📖 Genre", get_all_genres(), index=0)
        tone = st.selectbox("🎨 Writing Tone", get_extended_tones(), index=0)
        chapters = st.slider("📚 Number of Chapters", 3, 30, 10)
        model = st.selectbox("🤖 Language Model", ["nothingiisreal/mn-celeste-12b", "gryphe/mythomax-l2-13b"])
        img_model = st.selectbox("🖼️ Image Model", list(IMAGE_MODELS.keys()))
        submitted = st.form_submit_button("🚀 Forge Book")

    if submitted and prompt:
        st.session_state.gen_progress = {
            "prompt": prompt, "genre": genre, "tone": tone,
            "chapters": chapters, "model": model, "img_model": img_model
        }
        st.session_state.cover = None
        st.session_state.outline = None
        st.session_state.book = None
        st.session_state.characters = None
        st.session_state.image_cache = {}

        gen_thread = threading.Thread(target=background_generation_wrapper, daemon=True)
        add_script_run_ctx(gen_thread)
        gen_thread.start()
        st.rerun()

    render_book_content()
    render_project_buttons()

    # Style
    st.markdown("""
    <style>
        @media (max-width: 768px) {
            .stTextInput > div > input, .stTextArea textarea {
                font-size: 16px !important;
            }
            .block-container {
                padding: 1rem 1rem !important;
            }
        }
        .stProgress > div > div > div {
            background-color: #ff69b4 !important;
        }
        button[kind="primary"] {
            background: linear-gradient(to right, #ff69b4, #ff1493);
            color: white;
        }
    </style>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
