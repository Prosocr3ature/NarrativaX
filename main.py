
# main.py — NarrativaX Final Version

import os
import json
import time
import random
import requests
import base64
import zipfile
from io import BytesIO
from html import escape
from tempfile import NamedTemporaryFile

import replicate
import streamlit as st
from gtts import gTTS
from PIL import Image
from docx import Document
from fpdf import FPDF
from fpdf.enums import XPos, YPos

# === CONFIG ===
FONT_PATHS = {
    "regular": "fonts/NotoSans-Regular.ttf",
    "bold": "fonts/NotoSans-Bold.ttf"
}
IMAGE_SIZE = (768, 1024)
MAX_TOKENS = 1800

TONE_MAP = {
    "Romantic": "sensual, romantic, literary",
    "NSFW": "explicit, erotic, adult",
    "Wholesome": "uplifting, warm, feel-good",
    "Suspenseful": "tense, thrilling, page-turning",
    "Philosophical": "deep, reflective, thoughtful",
    "Motivational": "inspirational, personal growth, powerful",
    "Educational": "insightful, informative, structured",
    "Satirical": "humorous, ironic, critical",
    "Professional": "formal, business-like, articulate",
    "Instructive": "clear, structured, motivational",
    "Authoritative": "firm, knowledgeable, professional",
    "Conversational": "relatable, friendly, informal",
    "Reflective": "thoughtful, introspective, wise"
}

GENRES = [
    "Personal Development", "Business", "Memoir", "Self-Help", "Productivity",
    "Adventure", "Romance", "Sci-Fi", "Mystery", "Fantasy", "Horror",
    "NSFW", "Erotica", "Historical Fiction", "Philosophy", "Psychology",
    "Self-Discipline", "Time Management", "Wealth Building", "Confidence",
    "Mindfulness", "Goal Setting", "Stoicism", "Creativity",
    "Fitness & Health", "Habits", "Social Skills", "Leadership", "Focus",
    "Decision-Making", "Public Speaking", "Mental Clarity"
]

IMAGE_MODELS = {
    "Realistic Vision v5.1": "lucataco/realistic-vision-v5.1:latest",
    "Reliberate V3 (NSFW)": "asiryan/reliberate-v3:latest"
}

LLM_MODELS = {
    "nothingisreal/mn-celeste-12b": {
        "label": "MN Celeste 12B (balanced, good storytelling)",
        "nsfw": True,
        "strengths": "creative, consistent, smooth prose"
    },
    "nousresearch/nous-hermes-2-mixtral": {
        "label": "Nous Hermes 2 (Mixtral, uncensored)",
        "nsfw": True,
        "strengths": "dialogue, NSFW, character depth"
    },
    "gryphe/mythomax-l2-13b": {
        "label": "MythoMax L2 13B (NSFW, RP-heavy)",
        "nsfw": True,
        "strengths": "romance, fantasy, internal monologue"
    },
    "togethercomputer/llama-3-70b-chat": {
        "label": "LLaMA 3 70B (Powerful, less filtered)",
        "nsfw": True,
        "strengths": "context retention, logic, large worlds"
    },
    "openai/gpt-4": {
        "label": "OpenAI GPT-4 (filtered, polished)",
        "nsfw": False,
        "strengths": "non-fiction, safe content, structure"
    }
}

CHARACTER_TEMPLATE = {
    "name": "", "role": "", "description": "",
    "personality": "", "evolution": ""
}

# === SESSION DEFAULTS ===
for key in ['book', 'outline', 'cover', 'characters', 'gen_progress',
            'image_cache', 'story_context', 'book_structure']:
    st.session_state.setdefault(key, {} if key == 'image_cache' else None)

# === LOGO ===
def load_logo():
    try:
        with open("logo.png", "rb") as f:
            return base64.b64encode(f.read()).decode()
    except:
        return None

logo = load_logo()
if logo:
    st.markdown(f'<div style="text-align:center;"><img src="data:image/png;base64,{logo}" width="250"></div>', unsafe_allow_html=True)

# === FONT & PDF ===
class PDFStyler(FPDF):
    def __init__(self):
        super().__init__()
        self.font_configured = False

    def header(self):
        if self.font_configured:
            self.set_font('NotoSans', 'B', 12)
            self.cell(0, 10, 'NarrativaX Book', 0, 1, 'C')

    def footer(self):
        if self.font_configured:
            self.set_y(-15)
            self.set_font('NotoSans', '', 8)
            self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def verify_fonts():
    for name, path in FONT_PATHS.items():
        if not os.path.exists(path):
            raise FileNotFoundError(f"Missing font: {path}")

# === API VALIDATION ===
def validate_api_keys():
    required_keys = ['OPENROUTER_API_KEY', 'REPLICATE_API_TOKEN']
    missing = [key for key in required_keys if key not in st.secrets]
    if missing:
        st.error(f"Missing API keys: {', '.join(missing)}")
        st.stop()

validate_api_keys()
os.environ["REPLICATE_API_TOKEN"] = st.secrets["REPLICATE_API_TOKEN"]

# === LLM CALL ===
def call_openrouter(prompt, model):
    headers = {
        "Authorization": f"Bearer {st.secrets['OPENROUTER_API_KEY']}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://narrativax.com",
        "X-Title": "NarrativaX Generator"
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": MAX_TOKENS,
        "temperature": 0.7
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
        st.error(f"OpenRouter API error: {str(e)}")
        return None

# === IMAGE GENERATION ===
def generate_image(prompt, model_name, section):
    try:
        model_version = IMAGE_MODELS[model_name]
        cfg = st.session_state.gen_progress
        enhanced_prompt = (
            f"{prompt[:200]}. Style: {cfg['scene_type']}, Lighting: {cfg['lighting']}, "
            f"Tone: {TONE_MAP[cfg['tone']]}, Nudity: {cfg['nudity']}/10"
        )
        output = replicate.run(model_version, input={
            "prompt": enhanced_prompt,
            "width": IMAGE_SIZE[0],
            "height": IMAGE_SIZE[1],
            "negative_prompt": "text, watermark"
        })
        if not output:
            raise Exception("Empty image output")
        image_url = output[0] if isinstance(output, list) else output
        response = requests.get(image_url, timeout=15)
        img = Image.open(BytesIO(response.content))
        st.session_state.image_cache[section] = img
        return img
    except Exception as e:
        st.error(f"Image generation failed: {str(e)}")
        return None

# === CHARACTER CONTEXT ===
def build_character_context():
    if not st.session_state.characters:
        return ""
    ctx = "Characters:\n"
    for c in st.session_state.characters:
        ctx += f"- {c['name']} ({c['role']}): {c['description']} | Personality: {c['personality']} | Arc: {c['evolution']}\n"
    return ctx.strip()

# === BOOK GENERATION ENGINE ===
def generate_book_content():
    cfg = st.session_state.gen_progress
    genre = cfg["genre"]
    tone = TONE_MAP[cfg["tone"]]
    model = cfg["model"]
    chapters_total = cfg["chapters"]

    story = {
        "title": cfg["prompt"],
        "meta_outline": "",
        "arcs": []
    }
    st.session_state.book_structure = story
    char_context = build_character_context()

    progress_bar = st.progress(0, text="Initializing...")
    step = 0
    total_steps = chapters_total * 2 + 3

    try:
        # Step 1: Meta-outline
        step += 1
        progress_bar.progress(step / total_steps, text="🧠 Building meta-outline...")
        meta_outline = call_openrouter(
            f"Create a 2-3 act meta-outline for a {tone} {genre} novel titled '{cfg['prompt']}'",
            model
        )
        story["meta_outline"] = meta_outline

        # Step 2: Arcs
        step += 1
        progress_bar.progress(step / total_steps, text="🎯 Creating arcs...")
        arc_prompt = f"Generate 2-3 arcs from this outline:\n\n{meta_outline}"
        arc_summaries = call_openrouter(arc_prompt, model)
        arc_titles = [f"Arc {i+1}" for i in range(2)]
        for i, arc_title in enumerate(arc_titles):
            story["arcs"].append({
                "arc_title": arc_title,
                "arc_summary": f"Arc Summary {i+1}: {arc_summaries.splitlines()[i] if arc_summaries else ''}",
                "chapters": []
            })

        # Step 3–4: Chapters + Scenes
        story_so_far = ""
        chapter_count = 1

        for arc in story["arcs"]:
            for _ in range(chapters_total // len(story["arcs"])):
                step += 1
                progress_bar.progress(step / total_steps, text=f"📘 Outlining Chapter {chapter_count}...")
                outline_prompt = (
                    f"Write a chapter outline based on this arc:\n{arc['arc_summary']}\n\n"
                    f"Story so far:\n{story_so_far}\n\n"
                    f"{char_context}"
                )
                chapter_outline = call_openrouter(outline_prompt, model)
                chapter = {
                    "title": f"Chapter {chapter_count}",
                    "outline": chapter_outline,
                    "scenes": []
                }

                step += 1
                progress_bar.progress(step / total_steps, text=f"✍️ Writing scenes for Chapter {chapter_count}...")
                scene_prompt = (
                    f"Turn this outline into 2 scenes:\n{chapter_outline}\n\n"
                    f"Story so far:\n{story_so_far}\n\n"
                    f"{char_context}"
                )
                scenes_text = call_openrouter(scene_prompt, model)
                scenes = scenes_text.split("\n\n") if scenes_text else [scenes_text]

                for idx, scene in enumerate(scenes):
                    chapter["scenes"].append({
                        "title": f"Scene {idx+1}",
                        "content": scene.strip()
                    })

                arc["chapters"].append(chapter)
                story_so_far += f"\n\nChapter {chapter_count} Summary: {chapter_outline}"
                chapter_count += 1

        # Step 5: Cover image
        progress_bar.progress(1.0, text="🎨 Generating cover...")
        st.session_state.cover = generate_image(
            f"Cover for book: {cfg['prompt']}. Genre: {genre}, Tone: {tone}",
            cfg["img_model"],
            "cover"
        )

        st.success("✅ Book generation complete!")
        time.sleep(1)

    except Exception as e:
        st.error(f"Book generation failed: {str(e)}")
    finally:
        progress_bar.empty()

# === STREAMLIT MAIN UI ===
def main_interface():
    try:
        verify_fonts()
    except FileNotFoundError as e:
        st.error(f"Font error: {str(e)}")
        st.stop()

    st.title("NarrativaX — AI Book Generator")

    with st.form("book_form"):
        prompt = st.text_area("🖋️ Your Book Idea", height=120)
        col1, col2 = st.columns(2)
        genre = col1.selectbox("📚 Genre", sorted(GENRES))
        tone = col2.selectbox("🎭 Tone", list(TONE_MAP.keys()))
        chapters = st.slider("📖 Chapters", 3, 30, 10)

        col3, col4 = st.columns(2)
        model_keys = list(LLM_MODELS.keys())
        model_labels = [LLM_MODELS[m]["label"] for m in model_keys]
        model_index = col3.selectbox("🤖 LLM", range(len(model_keys)), format_func=lambda i: model_labels[i])
        model = model_keys[model_index]
        img_model = col4.selectbox("🖼️ Image Model", list(IMAGE_MODELS.keys()))

        col5, col6 = st.columns(2)
        scene_type = col5.selectbox("📸 Scene Type", ["Soft", "Suggestive", "Nude", "Explicit"])
        lighting = col6.selectbox("💡 Lighting", ["Natural", "Studio", "Moody", "Backlit"])
        nudity = st.slider("🔞 Nudity Level", 0, 10, 3)

        if st.form_submit_button("🚀 Create Book"):
            if not prompt.strip():
                st.warning("Please enter a prompt.")
            else:
                st.session_state.image_cache.clear()
                st.session_state.gen_progress = {
                    "prompt": prompt, "genre": genre, "tone": tone,
                    "chapters": chapters, "model": model,
                    "img_model": img_model, "scene_type": scene_type,
                    "lighting": lighting, "nudity": nudity
                }
                generate_book_content()

    tabs = st.tabs(["Chapters", "Outline", "Export", "Characters", "Structure"])

    # Chapters Tab
    with tabs[0]:
        book = st.session_state.get("book_structure")
        if not book:
            st.info("No book generated yet.")
        else:
            for arc in book["arcs"]:
                for ch in arc["chapters"]:
                    with st.expander(ch["title"]):
                        col1, col2 = st.columns([3, 2])
                        text = "\n\n".join([s["content"] for s in ch["scenes"]])
                        with col1:
                            st.write(text)
                        with col2:
                            img_key = f"chapter_{ch['title'].split()[-1]}"
                            if img_key in st.session_state.image_cache:
                                st.image(st.session_state.image_cache[img_key])

    # Outline Tab
    with tabs[1]:
        if st.session_state.book_structure:
            st.markdown("### Meta Outline")
            st.code(st.session_state.book_structure["meta_outline"])

    # Export Tab
    with tabs[2]:
        if st.button("📦 Download Book ZIP"):
            zip_path = create_export_zip()
            st.download_button("Download", data=open(zip_path, "rb"), file_name="narrativax_book.zip", mime="application/zip")

    # Characters Tab
    with tabs[3]:
        st.markdown("### Characters")
        if not st.session_state.characters:
            st.session_state.characters = []

        if st.button("➕ Add Character"):
            st.session_state.characters.append(CHARACTER_TEMPLATE.copy())

        for idx, char in enumerate(st.session_state.characters):
            with st.expander(f"Character {idx + 1}: {char['name'] or 'Unnamed'}"):
                for field in CHARACTER_TEMPLATE:
                    st.session_state.characters[idx][field] = st.text_area(field.capitalize(), char[field], key=f"{field}_{idx}")

    # Structure Tab
    with tabs[4]:
        structure = st.session_state.get("book_structure")
        if not structure:
            st.info("No structure available yet.")
        else:
            st.markdown(f"**Title:** {structure['title']}")
            st.code(structure["meta_outline"])
            for arc in structure["arcs"]:
                with st.expander(arc["arc_title"]):
                    st.write(arc["arc_summary"])
                    for ch in arc["chapters"]:
                        with st.expander(ch["title"]):
                            st.code(ch["outline"])
                            for scene in ch["scenes"]:
                                st.subheader(scene["title"])
                                st.write(scene["content"])

# === EXPORT SYSTEM ===
def create_export_zip():
    try:
        verify_fonts()
        book = st.session_state.book_structure
        with NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
            with zipfile.ZipFile(tmp.name, 'w') as zipf:
                # === PDF ===
                pdf = PDFStyler()
                pdf.add_page()

                pdf.add_font('NotoSans', '', FONT_PATHS["regular"])
                pdf.add_font('NotoSans', 'B', FONT_PATHS["bold"])
                pdf.font_configured = True

                pdf.set_font("NotoSans", "B", 16)
                pdf.cell(200, 10, text=book.get("title", "Untitled"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.ln(10)

                pdf.set_font("NotoSans", "", 12)
                pdf.multi_cell(pdf.epw, 10, "Meta Outline:")
                pdf.set_font("NotoSans", "", 10)
                pdf.multi_cell(pdf.epw, 10, book["meta_outline"])
                pdf.ln(10)

                for arc in book["arcs"]:
                    pdf.set_font("NotoSans", "B", 14)
                    pdf.multi_cell(pdf.epw, 10, arc["arc_title"])
                    pdf.set_font("NotoSans", "", 11)
                    pdf.multi_cell(pdf.epw, 10, arc["arc_summary"])
                    pdf.ln(4)
                    for ch in arc["chapters"]:
                        pdf.set_font("NotoSans", "B", 13)
                        pdf.multi_cell(pdf.epw, 10, ch["title"])
                        pdf.set_font("NotoSans", "", 11)
                        pdf.multi_cell(pdf.epw, 10, ch["outline"])
                        for scene in ch["scenes"]:
                            pdf.set_font("NotoSans", "B", 11)
                            pdf.multi_cell(pdf.epw, 10, scene["title"])
                            pdf.set_font("NotoSans", "", 10)
                            pdf.multi_cell(pdf.epw, 10, scene["content"])
                        pdf.ln(6)

                pdf_path = "book.pdf"
                pdf.output(pdf_path)
                zipf.write(pdf_path)
                os.remove(pdf_path)

                # === DOCX ===
                doc = Document()
                doc.add_heading(book.get("title", "Untitled"), 0)
                doc.add_paragraph("Meta Outline:")
                doc.add_paragraph(book["meta_outline"])
                for arc in book["arcs"]:
                    doc.add_heading(arc["arc_title"], level=1)
                    doc.add_paragraph(arc["arc_summary"])
                    for ch in arc["chapters"]:
                        doc.add_heading(ch["title"], level=2)
                        doc.add_paragraph(ch["outline"])
                        for scene in ch["scenes"]:
                            doc.add_heading(scene["title"], level=3)
                            doc.add_paragraph(scene["content"])
                docx_path = "book.docx"
                doc.save(docx_path)
                zipf.write(docx_path)
                os.remove(docx_path)

                # === MP3 ===
                idx = 1
                for arc in book["arcs"]:
                    for ch in arc["chapters"]:
                        audio_text = "\n\n".join(s["content"] for s in ch["scenes"])
                        tts = gTTS(text=audio_text, lang='en')
                        mp3_path = f"chapter_{idx}.mp3"
                        tts.save(mp3_path)
                        zipf.write(mp3_path)
                        os.remove(mp3_path)
                        idx += 1

            return tmp.name

    except Exception as e:
        st.error(f"Export failed: {str(e)}")
        raise

# === RUN ===
if __name__ == "__main__":
    main_interface()
