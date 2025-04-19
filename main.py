import streamlit as st
import requests
import os
from gtts import gTTS
from fpdf import FPDF
import docx  # python-docx
import base64

# --- Page Config ---
LOGO_IMAGE_URL = None  # Set to an external or local image path if available
st.set_page_config(page_title="NarrativaX", page_icon="📖", layout="wide")

# Optional: If a logo image file is in the app directory, you can load it:
try:
    if LOGO_IMAGE_URL is None:
        # Try local logo file
        LOGO_IMAGE_URL = "logo.png"
        # Ensure it exists
        with open(LOGO_IMAGE_URL, "rb") as f:
            pass
except Exception:
    # Fallback to a placeholder or skip
    LOGO_IMAGE_URL = None

# --- UI Header (Logo and Title) ---
if LOGO_IMAGE_URL:
    st.image(LOGO_IMAGE_URL, width=200)
st.title("NarrativaX")
st.markdown("_Unleash your narrative imagination - create stories and books with AI_")

# --- Initialize session state ---
if "step" not in st.session_state:
    st.session_state.step = 1
if "generated" not in st.session_state:
    st.session_state.generated = False
    st.session_state.outline = []
    st.session_state.chapters = []
    st.session_state.chapter_titles = []
    st.session_state.cover_url = ""
    st.session_state.audio_bytes = []

# --- Define genre and tone options ---
FICTION_GENRES = [
    "Fantasy", "Science Fiction", "Mystery", "Thriller", "Romance",
    "Horror", "Historical Fiction", "Adventure", "Drama", "Comedy"
]
NONFICTION_CATEGORIES = [
    "Personal Development", "Self-Help", "Biography", "History", "Science",
    "Technology", "Health & Wellness", "Business/Finance", "Travel", "Philosophy"
]
TONE_OPTIONS = {
    "Default": "a balanced, narrative style",
    "Professional": "a formal, professional tone",
    "Conversational": "a friendly, conversational tone",
    "Humorous": "a light-hearted, humorous tone",
    "Inspirational": "an inspiring, motivational tone",
    "Dramatic": "an emotional, dramatic tone",
    "Whimsical": "a whimsical, imaginative tone",
    "Serious/Academic": "a serious, academic tone",
    "Informative/Technical": "an informative, technical tone",
    "Poetic": "a poetic, lyrical style"
}

# --- Sidebar (optional navigation or info) ---
st.sidebar.title("NarrativaX")
st.sidebar.markdown("Create fictional stories or non-fiction books with AI.")
st.sidebar.markdown("Select **Classic** for one-page input or **Wizard** for step-by-step.")

# --- Mode Selection ---
mode = st.radio("Mode", ["Classic", "Wizard"], index=0, horizontal=True)
if "last_mode" in st.session_state and st.session_state.last_mode != mode:
    # Mode changed, reset relevant state
    st.session_state.step = 1
    st.session_state.generated = False
    st.session_state.outline = []
    st.session_state.chapters = []
    st.session_state.chapter_titles = []
    st.session_state.cover_url = ""
    st.session_state.audio_bytes = []
    # clear any inputs if needed (handled via new widgets on mode switch)
st.session_state.last_mode = mode

# --- Input Widgets for Classic mode ---
if mode == "Classic":
    # Fiction or Non-fiction
    book_type = st.selectbox("Type of Book", ["Fiction", "Non-fiction"])
    if book_type == "Fiction":
        genre = st.selectbox("Genre", FICTION_GENRES)
    else:
        genre = st.selectbox("Category", NONFICTION_CATEGORIES)
    tone = st.selectbox("Writing Style/Tone", list(TONE_OPTIONS.keys()))
    title_input = st.text_input("Book Title or Main Idea", placeholder="e.g. The Enchanted Forest")
    desc_input = st.text_area("Brief Description or Story Idea", placeholder="A young princess ventures into a forbidden forest to find a magical cure for her kingdom...")
    chapters_num = st.slider("Number of Chapters", 3, 20, 10)
    generate_btn = st.button("Generate Book")
    if generate_btn:
        # Prepare prompt details
        book_type_label = "fictional story" if book_type == "Fiction" else "non-fiction book"
        full_description = desc_input if desc_input.strip() else title_input
        # Build outline prompt for OpenRouter
        outline_prompt = (f"Generate an outline for a {book_type_label} titled '{title_input}' in the genre/category of {genre}. "
                          f"The {book_type_label} is about {full_description}. "
                          f"It should have {chapters_num} chapters. Provide a numbered list of chapter titles for the {book_type_label}.")
        # Include tone in outline prompt if not default
        if tone != "Default":
            outline_prompt += f" Write it in {TONE_OPTIONS[tone]}."
        # Call OpenRouter API for outline
        try:
            OR_API_KEY = st.secrets["OPENROUTER_API_KEY"]
        except Exception:
            OR_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
        headers = {
            "Authorization": f"Bearer {OR_API_KEY}",
            "Content-Type": "application/json"
        }
        api_url = "https://openrouter.ai/api/v1/chat/completions"
        outline_messages = [
            {"role": "user", "content": outline_prompt}
        ]
        with st.spinner("Creating book outline..."):
            response = requests.post(api_url, headers=headers, json={
                "model": "openai/gpt-4",
                "messages": outline_messages
            })
        if response.status_code != 200:
            st.error("Error from OpenRouter API: " + response.text)
        else:
            data = response.json()
            outline_text = data["choices"][0]["message"]["content"].strip()
            # Parse outline into list of chapter titles
            chapter_titles = []
            for line in outline_text.splitlines():
                # Look for lines starting with a number or bullet
                line = line.strip()
                if not line:
                    continue
                if line[0].isdigit():
                    # Split by first dot if numbered like "1. Chapter"
                    parts = line.split('.', 1)
                    title_part = parts[1] if len(parts) > 1 else parts[0]
                    # Clean up the title part
                    title = title_part.lstrip(":-) ").strip()
                    chapter_titles.append(title)
                else:
                    # If the outline isn't numbered, treat the whole line as a title
                    chapter_titles.append(line)
            # Ensure we only have the desired number of chapters
            if len(chapter_titles) > chapters_num:
                chapter_titles = chapter_titles[:chapters_num]
            # Generate each chapter content
            chapters = []
            audio_bytes_list = []
            progress_text = st.empty()
            progress_bar = st.progress(0)
            system_msg = {"role": "system", "content": "You are a creative and articulate writer."}
            for i, ch_title in enumerate(chapter_titles):
                progress_text.text(f"Generating Chapter {i+1}/{len(chapter_titles)}: {ch_title}")
                chapter_prompt = (f"Write the full text of Chapter {i+1} titled '{ch_title}' for the {book_type_label} '{title_input}'. "
                                  f"Make sure it fits in the {genre} genre. ")
                if desc_input:
                    chapter_prompt += f"The book is about {full_description}. "
                if tone != "Default":
                    chapter_prompt += f"Write in {TONE_OPTIONS[tone]}. "
                else:
                    chapter_prompt += "Write in a clear and engaging tone. "
                chapter_messages = [
                    system_msg,
                    {"role": "user", "content": chapter_prompt}
                ]
                try:
                    chapter_response = requests.post(api_url, headers=headers, json={
                        "model": "openai/gpt-4",
                        "messages": chapter_messages
                    })
                except Exception as e:
                    st.error(f"Error connecting to OpenRouter: {e}")
                    break
                if chapter_response.status_code != 200:
                    st.error("Error from OpenRouter API: " + chapter_response.text)
                    break
                chapter_data = chapter_response.json()
                chapter_text = chapter_data["choices"][0]["message"]["content"].strip()
                chapters.append(chapter_text)
                # Generate audio for this chapter
                try:
                    tts = gTTS(chapter_text, lang='en')
                    audio_file = f"chapter_{i+1}.mp3"
                    tts.save(audio_file)
                    with open(audio_file, "rb") as af:
                        audio_bytes = af.read()
                    audio_bytes_list.append(audio_bytes)
                except Exception as e:
                    audio_bytes_list.append(None)
                    st.warning(f"Could not generate audio for Chapter {i+1}: {e}")
                progress_bar.progress((i+1)/len(chapter_titles))
            progress_text.text("Story generation complete!")
            # Generate cover image using Replicate
            cover_url = ""
            try:
                REPLICATE_API_TOKEN = st.secrets["REPLICATE_API_TOKEN"]
            except Exception:
                REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "")
            if REPLICATE_API_TOKEN:
                os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN
            try:
                import replicate
                cover_prompt = f"Book cover art for a {genre} { 'story' if book_type=='Fiction' else 'book'}"
                if title_input:
                    cover_prompt += f" titled '{title_input}'"
                if desc_input:
                    short_desc = desc_input.split('.')[0][:100]
                    cover_prompt += f", about {short_desc}"
                cover_prompt += ". High quality, illustration."
                cover_image = replicate.run(
                    "stability-ai/stable-diffusion:ac732df8",
                    input={"prompt": cover_prompt, "width": 512, "height": 768}
                )
                if isinstance(cover_image, list):
                    cover_url = cover_image[0]
                elif isinstance(cover_image, str):
                    cover_url = cover_image
            except Exception as e:
                st.warning(f"Cover image generation failed: {e}")
                cover_url = ""
            # Save results in session state for display
            st.session_state.generated = True
            st.session_state.chapter_titles = chapter_titles
            st.session_state.chapters = chapters
            st.session_state.audio_bytes = audio_bytes_list
            st.session_state.cover_url = cover_url
            st.session_state.book_title = title_input if title_input else "Untitled"
            st.session_state.book_type = book_type
            st.session_state.genre = genre
            st.session_state.tone = tone

# --- Input Widgets for Wizard mode ---
if mode == "Wizard":
    step = st.session_state.step
    if step == 1:
        st.subheader("Step 1: Choose Book Type")
        st.session_state.book_type = st.radio("Is your book Fiction or Non-fiction?", ["Fiction", "Non-fiction"], index=0, key="book_type_choice")
        if st.button("Next"):
            st.session_state.step = 2
    elif step == 2:
        st.subheader("Step 2: Select Genre/Category and Tone")
        if st.session_state.book_type == "Fiction":
            st.session_state.genre = st.selectbox("Genre", FICTION_GENRES, key="genre_choice")
        else:
            st.session_state.genre = st.selectbox("Category", NONFICTION_CATEGORIES, key="genre_choice")
        st.session_state.tone = st.selectbox("Writing Style/Tone", list(TONE_OPTIONS.keys()), key="tone_choice")
        cols = st.columns([1,1])
        if cols[0].button("Back"):
            st.session_state.step = 1
        if cols[1].button("Next"):
            st.session_state.step = 3
    elif step == 3:
        st.subheader("Step 3: Provide Title and Description")
        st.session_state.book_title = st.text_input("Book Title (optional)", key="title_input", placeholder="e.g. The Enchanted Forest")
        st.session_state.book_desc = st.text_area("Brief Description or Idea", key="desc_input", placeholder="A young princess ventures into a forbidden forest...")
        cols = st.columns([1,1])
        if cols[0].button("Back"):
            st.session_state.step = 2
        if cols[1].button("Next"):
            st.session_state.step = 4
    elif step == 4:
        st.subheader("Step 4: Chapters and Generate")
        st.session_state.chapters_num = st.slider("Number of Chapters", 3, 20, 10, key="chapters_slider")
        st.write("Everything is set! Click **Generate Book** to create your story.")
        cols = st.columns([1,1])
        if cols[0].button("Back"):
            st.session_state.step = 3
        generate_wizard_btn = cols[1].button("Generate Book")
        if generate_wizard_btn:
            # Gather inputs from session_state
            book_type = st.session_state.book_type
            genre = st.session_state.genre
            tone = st.session_state.tone
            title_input = st.session_state.book_title
            desc_input = st.session_state.book_desc
            chapters_num = st.session_state.chapters_num
            book_type_label = "fictional story" if book_type == "Fiction" else "non-fiction book"
            full_description = desc_input if desc_input.strip() else title_input
            outline_prompt = (f"Generate an outline for a {book_type_label} titled '{title_input}' in the genre/category of {genre}. "
                              f"The {book_type_label} is about {full_description}. "
                              f"It should have {chapters_num} chapters. Provide a numbered list of chapter titles.")
            if tone != "Default":
                outline_prompt += f" Write it in {TONE_OPTIONS[tone]}."
            try:
                OR_API_KEY = st.secrets["OPENROUTER_API_KEY"]
            except Exception:
                OR_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
            headers = {
                "Authorization": f"Bearer {OR_API_KEY}",
                "Content-Type": "application/json"
            }
            api_url = "https://openrouter.ai/api/v1/chat/completions"
            outline_messages = [{"role": "user", "content": outline_prompt}]
            with st.spinner("Creating book outline..."):
                response = requests.post(api_url, headers=headers, json={"model": "openai/gpt-4", "messages": outline_messages})
            if response.status_code != 200:
                st.error("Error from OpenRouter API: " + response.text)
            else:
                outline_text = response.json()["choices"][0]["message"]["content"].strip()
                chapter_titles = []
                for line in outline_text.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    if line[0].isdigit():
                        parts = line.split('.', 1)
                        title_part = parts[1] if len(parts)>1 else parts[0]
                        title = title_part.lstrip(":-) ").strip()
                        chapter_titles.append(title)
                    else:
                        chapter_titles.append(line)
                if len(chapter_titles) > chapters_num:
                    chapter_titles = chapter_titles[:chapters_num]
                chapters = []
                audio_bytes_list = []
                progress_text = st.empty()
                progress_bar = st.progress(0)
                system_msg = {"role": "system", "content": "You are a creative and articulate writer."}
                for i, ch_title in enumerate(chapter_titles):
                    progress_text.text(f"Generating Chapter {i+1}/{len(chapter_titles)}: {ch_title}")
                    chapter_prompt = (f"Write the full text of Chapter {i+1} titled '{ch_title}' for the {book_type_label} '{title_input}'. "
                                      f"Make sure it fits in the {genre} genre. ")
                    if desc_input:
                        chapter_prompt += f"The book is about {full_description}. "
                    if tone != "Default":
                        chapter_prompt += f"Write in {TONE_OPTIONS[tone]}. "
                    else:
                        chapter_prompt += "Write in a clear and engaging tone. "
                    chapter_messages = [system_msg, {"role": "user", "content": chapter_prompt}]
                    try:
                        chapter_response = requests.post(api_url, headers=headers, json={"model": "openai/gpt-4", "messages": chapter_messages})
                    except Exception as e:
                        st.error(f"Error connecting to OpenRouter: {e}")
                        break
                    if chapter_response.status_code != 200:
                        st.error("Error from OpenRouter API: " + chapter_response.text)
                        break
                    chapter_text = chapter_response.json()["choices"][0]["message"]["content"].strip()
                    chapters.append(chapter_text)
                    try:
                        tts = gTTS(chapter_text, lang='en')
                        audio_file = f"chapter_{i+1}.mp3"
                        tts.save(audio_file)
                        with open(audio_file, "rb") as af:
                            audio_bytes = af.read()
                        audio_bytes_list.append(audio_bytes)
                    except Exception as e:
                        audio_bytes_list.append(None)
                        st.warning(f"Could not generate audio for Chapter {i+1}: {e}")
                    progress_bar.progress((i+1)/len(chapter_titles))
                progress_text.text("Story generation complete!")
                cover_url = ""
                try:
                    REPLICATE_API_TOKEN = st.secrets["REPLICATE_API_TOKEN"]
                except Exception:
                    REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "")
                if REPLICATE_API_TOKEN:
                    os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN
                try:
                    import replicate
                    cover_prompt = f"Book cover art for a {genre} { 'story' if book_type=='Fiction' else 'book'}"
                    if title_input:
                        cover_prompt += f" titled '{title_input}'"
                    if desc_input:
                        short_desc = desc_input.split('.')[0][:100]
                        cover_prompt += f", about {short_desc}"
                    cover_prompt += ". High quality, illustration."
                    cover_image = replicate.run("stability-ai/stable-diffusion:ac732df8", input={"prompt": cover_prompt, "width": 512, "height": 768})
                    if isinstance(cover_image, list):
                        cover_url = cover_image[0]
                    elif isinstance(cover_image, str):
                        cover_url = cover_image
                except Exception as e:
                    st.warning(f"Cover image generation failed: {e}")
                    cover_url = ""
                st.session_state.generated = True
                st.session_state.chapter_titles = chapter_titles
                st.session_state.chapters = chapters
                st.session_state.audio_bytes = audio_bytes_list
                st.session_state.cover_url = cover_url
                st.session_state.book_title = title_input if title_input else "Untitled"
                st.session_state.book_type = book_type
                st.session_state.genre = genre
                st.session_state.tone = tone
                # Move to result display step
                st.session_state.step = 5
    elif step == 5:
        # Step 5: Display results (handled after this block)
        pass

# --- Display Generated Story ---
if st.session_state.generated:
    # Show cover and title
    if st.session_state.cover_url:
        st.image(st.session_state.cover_url, caption="Book Cover", use_column_width=True)
    st.header(st.session_state.book_title if st.session_state.book_title else "Your Book")
    st.subheader(f"{st.session_state.book_type} - {st.session_state.genre} ({st.session_state.tone} tone)")
    # Show chapters in expanders
    for idx, (ch_title, ch_text) in enumerate(zip(st.session_state.chapter_titles, st.session_state.chapters)):
        chapter_no = idx + 1
        exp = st.expander(f"Chapter {chapter_no}: {ch_title}", expanded=(idx==0))
        with exp:
            st.write(ch_text)
            if idx < len(st.session_state.audio_bytes) and st.session_state.audio_bytes[idx]:
                st.audio(st.session_state.audio_bytes[idx], format="audio/mp3")
    # Offer download options (PDF, DOCX)
    # Generate PDF in memory
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, txt=st.session_state.book_title, ln=1, align='C')
    pdf.set_font("Arial", 'I', 12)
    subtitle = f"{st.session_state.book_type} - {st.session_state.genre} ({st.session_state.tone} tone})"
    pdf.cell(0, 10, txt=subtitle, ln=1, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", size=12)
    for idx, (ch_title, ch_text) in enumerate(zip(st.session_state.chapter_titles, st.session_state.chapters)):
        pdf.set_font("Arial", 'B', 14)
        pdf.multi_cell(0, 10, txt=f"Chapter {idx+1}: {ch_title}")
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, txt=ch_text)
        if idx < len(st.session_state.chapter_titles) - 1:
            pdf.add_page()
    pdf_output = pdf.output(dest='S').encode('latin1')
    st.download_button("Download PDF", data=pdf_output, file_name="NarrativaX_Book.pdf", mime="application/pdf")
    # Generate DOCX in memory
    doc = docx.Document()
    doc.add_heading(st.session_state.book_title, 0)
    doc.add_paragraph(f"{st.session_state.book_type} - {st.session_state.genre} ({st.session_state.tone} tone})")
    for idx, (ch_title, ch_text) in enumerate(zip(st.session_state.chapter_titles, st.session_state.chapters)):
        doc.add_heading(f"Chapter {idx+1}: {ch_title}", level=1)
        doc.add_paragraph(ch_text)
    docx_path = "NarrativaX_Book.docx"
    doc.save(docx_path)
    with open(docx_path, "rb") as docf:
        docx_bytes = docf.read()
    st.download_button("Download DOCX", data=docx_bytes, file_name="NarrativaX_Book.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
