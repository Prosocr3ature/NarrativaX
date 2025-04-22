import os
import streamlit as st
import replicate
import base64
from io import BytesIO
from PIL import Image
import requests

# ——— Configuration —————————————————————————————————————————————
st.set_page_config(
    page_title="AI Companion",
    page_icon="💋",
    layout="wide",
    initial_sidebar_state="collapsed",
)
# Hide Streamlit footer/menu
st.markdown(
    "<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;}</style>",
    unsafe_allow_html=True,
)

# Ensure your Replicate API token is set
REPLICATE_TOKEN = os.getenv("REPLICATE_API_TOKEN")
if not REPLICATE_TOKEN:
    st.error("⚠️ Please set REPLICATE_API_TOKEN in your environment.")
    st.stop()
replicate.Client(api_token=REPLICATE_TOKEN)

# Models on Replicate
LLM_MODEL    = "gryphe/mythomax-l2-13b"
IMAGE_MODELS = {
    "Realistic":  "lucataco/realistic-vision-v5.1",
    "Reliberate": "asiryan/reliberate-v3",
}

MOODS = ["Flirty", "Loving", "Dominant", "Submissive", "Playful"]

# ——— Session State Initialization ————————————————————————————————
if "history" not in st.session_state:
    st.session_state.history = []   # each entry: dict(speaker, text, img_b64)

if "image_style" not in st.session_state:
    st.session_state.image_style = "Realistic"

# ——— Helpers ——————————————————————————————————————————————————————
def chat_with_mythomax(prompt: str) -> str:
    """Get a reply from Mythomax-L2-13B via Replicate."""
    try:
        output = replicate.run(
            LLM_MODEL,
            input={
                "prompt": prompt,
                "max_length": 300,
                "temperature": 0.8,
            },
        )
        return output.strip()
    except Exception as e:
        st.error(f"LLM error: {e}")
        return "🤖 [Error]"

def generate_avatar(prompt: str) -> str:
    """Generate a single avatar image and return its base64 string."""
    model = IMAGE_MODELS[st.session_state.image_style]
    try:
        urls = replicate.run(
            model,
            input={
                "prompt": prompt + ", photorealistic, 8k, detailed portrait",
                "width": 768,
                "height": 1024,
                "num_outputs": 1,
            },
        )
        url = urls[0] if isinstance(urls, list) else urls
        img = Image.open(BytesIO(requests.get(url).content))
        buf = BytesIO()
        img.save(buf, format="JPEG")
        return base64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        st.error(f"Image error: {e}")
        return ""

# ——— UI —————————————————————————————————————————————————————————
st.title("💋 AI Companion Chat")
st.markdown("A live, photo‑realistic avatar powered by MythoMax & Stable Diffusion.")

# Controls: Mood & Image Style
col1, col2 = st.columns([1,1])
with col1:
    mood = st.selectbox("Mood", MOODS, key="mood_control")
with col2:
    st.radio(
        "Image Style",
        list(IMAGE_MODELS.keys()),
        key="image_style",
        horizontal=True
    )

# Display existing conversation
for msg in st.session_state.history:
    if msg["speaker"] == "User":
        with st.chat_message("user"):
            st.markdown(msg["text"])
    else:
        with st.chat_message("assistant"):
            if msg["img_b64"]:
                st.image(
                    "data:image/jpeg;base64," + msg["img_b64"],
                    use_column_width=True,
                    caption="Companion"
                )
            st.markdown(msg["text"])

# Chat input area
user_input = st.chat_input("Say something to your companion…")
if user_input:
    # 1) Append user message
    st.session_state.history.append({
        "speaker": "User",
        "text": user_input,
        "img_b64": ""
    })

    # 2) Build prompt
    recent = "\n".join(
        f"{h['speaker']}: {h['text']}"
        for h in st.session_state.history[-6:]
    )
    system_prompt = f"You are a sultry virtual companion. Mood: {mood.lower()}."
    full_prompt = f"{system_prompt}\nConversation so far:\n{recent}\nCompanion:"

    # 3) Generate companion reply
    with st.spinner("Companion is typing…"):
        reply = chat_with_mythomax(full_prompt)

    # 4) Generate companion avatar
    avatar_prompt = (
        f"virtual companion, mood {mood.lower()}, "
        f"reacting to '{user_input}', portrait"
    )
    with st.spinner("Generating avatar…"):
        img_b64 = generate_avatar(avatar_prompt)

    # 5) Append assistant message
    st.session_state.history.append({
        "speaker": "Companion",
        "text": reply,
        "img_b64": img_b64
    })

    # 6) Streamlit will automatically rerun and show updated history
