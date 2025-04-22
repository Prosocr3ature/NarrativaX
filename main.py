import os
import time
import base64
import streamlit as st
import replicate
import requests
from io import BytesIO
from PIL import Image

# -------------------- Configuration --------------------
st.set_page_config(
    page_title="CompanionX",
    page_icon="💖",
    layout="wide",
    initial_sidebar_state="expanded",
)
# Hide Streamlit footer
st.markdown(
    "<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;}</style>",
    unsafe_allow_html=True,
)

# -------------------- API Setup --------------------
REPLICATE_TOKEN = os.getenv("REPLICATE_API_TOKEN")
if not REPLICATE_TOKEN:
    st.error("⚠️ Please set REPLICATE_API_TOKEN in your environment.")
    st.stop()
client = replicate.Client(api_token=REPLICATE_TOKEN)

# -------------------- Models --------------------
LLM_MODEL = "gryphe/mythomax-l2-13b"

IMAGE_MODELS = {
    "Reliberate v3": {
        "id": "asiryan/reliberate-v3:d70438fcb9bb7adb8d6e59cf236f754be0b77625e984b8595d1af02cdf034b29",
        "width": 768, "height": 1152, "guidance_scale": 8.5
    },
    "Unlimited XL": {
        "id": "asiryan/unlimited-xl:1a98916be7897ab4d9fbc30d2b20d070c237674148b00d344cf03ff103eb7082",
        "width": 768, "height": 1152, "guidance_scale": 9.0
    },
    "Realism XL": {
        "id": "asiryan/realism-xl:ff26a1f71bc27f43de016f109135183e0e4902d7cdabbcbb177f4f8817112219",
        "width": 1024, "height": 1024, "guidance_scale": 8.0
    },
    "Babes XL": {
        "id": "asiryan/babes-xl:a07fcbe80652ccf989e8198654740d7d562de85f573196dd624a8a80285da27d",
        "width": 1024, "height": 1024, "guidance_scale": 9.0
    },
    "Deliberate V6": {
        "id": "asiryan/deliberate-v6:605a9ad23d7580b2762173afa6009b1a0cc00b7475998600ba2c39eda05f533e",
        "width": 768, "height": 1152, "guidance_scale": 9.0
    },
    "PonyNai3": {
        "id": "delta-lock/ponynai3:ea38949bfddea2db315b598620110edfa76ddaf6313a18e6cbc6a98f496a34e9",
        "width": 768, "height": 1152, "guidance_scale": 10.0
    },
}

MOODS     = ["Flirty", "Loving", "Dominant", "Submissive", "Playful"]
MOTIONS   = ["Wink", "Hair Flip", "Lean In", "Smile", "Blush"]
POSITIONS = ["None", "Missionary", "Doggy", "Cowgirl", "69", "Standing"]
OUTFITS   = ["None", "Lingerie", "Latex", "Uniform", "Casual"]

# -------------------- Session State --------------------
if "history" not in st.session_state:
    st.session_state.history = []
for key, default in {
    "mood": MOODS[0],
    "motion": MOTIONS[0],
    "position": POSITIONS[0],
    "outfit": OUTFITS[0],
    "nsfw_level": 3,
    "image_model": list(IMAGE_MODELS.keys())[0],
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# -------------------- Helpers --------------------
def chat_with_mythomax(prompt: str) -> str:
    try:
        out = client.run(
            LLM_MODEL,
            input={
                "prompt": prompt,
                "temperature": 0.9,
                "max_new_tokens": 300,
                "top_p": 0.95,
                "repetition_penalty": 1.1
            }
        )
        return out.strip().replace("<s>", "").replace("</s>", "")
    except Exception as e:
        return f"[LLM Error: {e}]"

def generate_avatar(prompt: str) -> str:
    cfg = IMAGE_MODELS[st.session_state.image_model]
    try:
        urls = client.run(
            cfg["id"],
            input={
                "prompt": prompt,
                "width": cfg["width"],
                "height": cfg["height"],
                "num_inference_steps": 50,
                "guidance_scale": cfg["guidance_scale"],
                "negative_prompt": "text, watermark, lowres"
            }
        )
        url = urls[0] if isinstance(urls, list) else urls
        img = Image.open(BytesIO(requests.get(url).content)).convert("RGB")
        buf = BytesIO(); img.save(buf, format="JPEG", quality=90)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ""

# -------------------- UI --------------------
st.title("💖 CompanionX")

with st.sidebar:
    st.header("🔧 Settings")
    st.session_state.mood        = st.selectbox("Mood", MOODS, index=MOODS.index(st.session_state.mood))
    st.session_state.motion      = st.selectbox("Motion", MOTIONS, index=MOTIONS.index(st.session_state.motion))
    st.session_state.position    = st.selectbox("Position", POSITIONS, index=POSITIONS.index(st.session_state.position))
    st.session_state.outfit      = st.selectbox("Outfit", OUTFITS, index=OUTFITS.index(st.session_state.outfit))
    st.session_state.nsfw_level  = st.slider("NSFW Level", 1, 5, st.session_state.nsfw_level)
    st.session_state.image_model = st.radio("Image Model", list(IMAGE_MODELS.keys()),
                                           index=list(IMAGE_MODELS.keys()).index(st.session_state.image_model))

# Display chat history
for entry in st.session_state.history:
    with st.chat_message("user"):
        st.markdown(entry["user"])
    with st.chat_message("assistant"):
        if entry["img"]:
            st.image(f"data:image/jpeg;base64,{entry['img']}", use_container_width=True, caption="Companion")
        st.markdown(entry["bot"])

# New user message
user_text = st.chat_input("Talk to your companion…")
if user_text:
    # Record user message
    st.session_state.history.append({"user": user_text, "bot": "", "img": ""})

    # Build prompt
    sys_p = (
        f"You are an intimate companion. Mood: {st.session_state.mood.lower()}. "
        f"Gesture: {st.session_state.motion.lower()}. Position: {st.session_state.position.lower()}. "
        f"Outfit: {st.session_state.outfit.lower()}. NSFW level: {st.session_state.nsfw_level}/5. "
        "Reply explicitly."
    )
    convo = sys_p + "\nUser: " + user_text + "\nCompanion:"

    # Generate reply
    with st.spinner("Companion is thinking…"):
        bot_reply = chat_with_mythomax(convo)

    # Generate avatar
    img_prompt = (
        f"{bot_reply}, {st.session_state.mood.lower()} mood, "
        f"{st.session_state.motion.lower()}, {st.session_state.position.lower()} position, "
        f"{st.session_state.outfit.lower()}, photorealistic"
    )
    with st.spinner("Generating avatar…"):
        img_b64 = generate_avatar(img_prompt)

    # Update last history entry
    st.session_state.history[-1].update({"bot": bot_reply, "img": img_b64})

# Streamlit auto‑reruns and shows the updated chat
