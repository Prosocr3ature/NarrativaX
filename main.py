import os
import streamlit as st
import replicate
import base64
from io import BytesIO
from PIL import Image
import requests

# ——— Page Config & Styles —————————————————————————————
st.set_page_config(
    page_title="💋 AI Companion Chat",
    page_icon="💋",
    layout="wide",
    initial_sidebar_state="collapsed",
)
st.markdown(
    """
    <style>
      #MainMenu {visibility: hidden;}
      footer {visibility: hidden;}
      .chat-avatar {border-radius: 12px; margin-bottom: 8px;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ——— API Initialization ————————————————————————————————
REPLICATE_TOKEN = os.getenv("REPLICATE_API_TOKEN")
if not REPLICATE_TOKEN:
    st.error("⚠️ Please set the REPLICATE_API_TOKEN environment variable.")
    st.stop()
replicate.Client(api_token=REPLICATE_TOKEN)

# ——— Models & Constants ————————————————————————————————
LLM_MODEL = "gryphe/mythomax-l2-13b"

IMAGE_MODELS = {
    "🎨 Realistic Vision": {
        "id": "lucataco/realistic-vision-v5.1",
        "width": 768, "height": 1024,
        "num_outputs": 1,
        "guidance_scale": 7,
        "num_inference_steps": 50
    },
    "🔥 NSFW Reliberate": {
        "id": "asiryan/reliberate-v3:d70438fcb9bb7adb8d6e59cf236f754be0b77625e984b8595d1af02cdf034b29",
        "width": 512, "height": 512,
        "num_outputs": 1,
        "guidance_scale": 8,
        "num_inference_steps": 60
    },
    "🌌 Unlimited XL": {
        "id": "asiryan/unlimited-xl:1a98916be7897ab4d9fbc30d2b20d070c237674148b00d344cf03ff103eb7082",
        "width": 1024, "height": 1024,
        "num_outputs": 1,
        "guidance_scale": 6,
        "num_inference_steps": 40
    },
    "🔮 Realism XL": {
        "id": "asiryan/realism-xl:ff26a1f71bc27f43de016f109135183e0e4902d7cdabbcbb177f4f8817112219",
        "width": 1024, "height": 1024,
        "num_outputs": 1,
        "guidance_scale": 7,
        "num_inference_steps": 50
    },
    "👙 Babes XL": {
        "id": "asiryan/babes-xl:a07fcbe80652ccf989e8198654740d7d562de85f573196dd624a8a80285da27d",
        "width": 1024, "height": 1024,
        "num_outputs": 1,
        "guidance_scale": 8,
        "num_inference_steps": 60
    },
    "⚡ Deliberate V6": {
        "id": "asiryan/deliberate-v6:605a9ad23d7580b2762173afa6009b1a0cc00b7475998600ba2c39eda05f533e",
        "width": 768, "height": 1024,
        "num_outputs": 1,
        "guidance_scale": 9,
        "num_inference_steps": 70
    },
    "🦄 PonyNai 3": {
        "id": "delta-lock/ponynai3:ea38949bfddea2db315b598620110edfa76ddaf6313a18e6cbc6a98f496a34e9",
        "width": 768, "height": 1024,
        "num_outputs": 1,
        "guidance_scale": 7,
        "num_inference_steps": 50
    },
}

MOODS = ["Flirty", "Loving", "Dominant", "Submissive", "Playful"]

# ——— Session State ————————————————————————————————
if "history" not in st.session_state:
    st.session_state.history = []  # list of dict: {"speaker","text","img_b64"}
if "image_style" not in st.session_state:
    st.session_state.image_style = list(IMAGE_MODELS.keys())[0]
if "mood" not in st.session_state:
    st.session_state.mood = MOODS[0]

# ——— Helpers —————————————————————————————————————————
def chat_with_mythomax(prompt: str) -> str:
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

def generate_avatar_b64(prompt: str) -> str:
    cfg = IMAGE_MODELS[st.session_state.image_style]
    try:
        out = replicate.run(
            cfg["id"],
            input={
                "prompt": prompt + ", photorealistic, ultra HD",
                "width": cfg["width"],
                "height": cfg["height"],
                "num_outputs": cfg["num_outputs"],
                "guidance_scale": cfg["guidance_scale"],
                "num_inference_steps": cfg["num_inference_steps"],
            },
        )
        url = out[0] if isinstance(out, list) else out
        resp = requests.get(url, timeout=20)
        img = Image.open(BytesIO(resp.content)).convert("RGB")
        buf = BytesIO()
        img.save(buf, format="JPEG")
        return base64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        st.error(f"Image error: {e}")
        return ""

# ——— UI —————————————————————————————————————————————————
st.title("💋 AI Companion Chat")
st.markdown("Live, photo‑realistic avatar powered by Mythomax & Stable Diffusion.")

# Controls
col1, col2 = st.columns([1,1])
with col1:
    st.session_state.mood = st.selectbox("Mood", MOODS, index=MOODS.index(st.session_state.mood))
with col2:
    st.session_state.image_style = st.radio(
        "Image Style", list(IMAGE_MODELS.keys()),
        index=list(IMAGE_MODELS.keys()).index(st.session_state.image_style),
        horizontal=True
    )

# Display conversation
for msg in st.session_state.history:
    role = "user" if msg["speaker"]=="User" else "assistant"
    with st.chat_message(role):
        if msg["speaker"]=="Companion" and msg["img_b64"]:
            st.image("data:image/jpeg;base64," + msg["img_b64"],
                     use_column_width=True,
                     caption="Companion")
        st.markdown(msg["text"])

# Chat input
user_input = st.chat_input("Say something to your companion…")
if user_input:
    # record user
    st.session_state.history.append({
        "speaker": "User",
        "text": user_input,
        "img_b64": ""
    })

    # build prompt
    recent = "\n".join(
        f"{h['speaker']}: {h['text']}"
        for h in st.session_state.history[-6:]
    )
    system = f"You are a sultry virtual companion. Mood: {st.session_state.mood.lower()}."
    prompt = f"{system}\nConversation so far:\n{recent}\nCompanion:"

    # generate reply
    with st.spinner("Companion is typing…"):
        reply = chat_with_mythomax(prompt)

    # generate avatar
    avatar_prompt = (
        f"virtual companion, mood {st.session_state.mood.lower()}, "
        f"reacting to '{user_input}', detailed portrait"
    )
    with st.spinner("Generating avatar…"):
        img_b64 = generate_avatar_b64(avatar_prompt)

    # record companion
    st.session_state.history.append({
        "speaker": "Companion",
        "text": reply,
        "img_b64": img_b64
    })
