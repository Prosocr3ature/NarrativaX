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
# hide footer/menu
st.markdown(
    "<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;}</style>",
    unsafe_allow_html=True,
)

# -------------------- Floating Animation CSS --------------------
st.markdown("""
<style>
  @keyframes float {
    0%,100% { transform: translateY(0px); }
    50%     { transform: translateY(-15px); }
  }
  .floating-img {
    display: inline-block;
    animation: float 4s ease-in-out infinite;
  }
</style>
""", unsafe_allow_html=True)

# -------------------- API Setup --------------------
REPLICATE_TOKEN = os.getenv("REPLICATE_API_TOKEN")
if not REPLICATE_TOKEN:
    st.error("⚠️ Please set REPLICATE_API_TOKEN in your environment.")
    st.stop()
client = replicate.Client(api_token=REPLICATE_TOKEN)

# -------------------- Models --------------------
DOLPHIN_MODEL = (
    "mikeei/dolphin-2.9-llama3-70b-gguf:"
    "7cd1882cb3ea90756d09decf4bc8a259353354703f8f385ce588b71f7946f0aa"
)
IMAGE_MODELS = {
    "Reliberate v3": {
        "id": "asiryan/reliberate-v3:"
              "d70438fcb9bb7adb8d6e59cf236f754be0b77625e984b8595d1af02cdf034b29",
        "width": 768, "height": 1152, "guidance": 8.5
    },
    "Unlimited XL": {
        "id": "asiryan/unlimited-xl:"
              "1a98916be7897ab4d9fbc30d2b20d070c237674148b00d344cf03ff103eb7082",
        "width": 768, "height": 1152, "guidance": 9.0
    },
    "Realism XL": {
        "id": "asiryan/realism-xl:"
              "ff26a1f71bc27f43de016f109135183e0e4902d7cdabbcbb177f4f8817112219",
        "width": 1024, "height": 1024, "guidance": 8.0
    },
    "Babes XL": {
        "id": "asiryan/babes-xl:"
              "a07fcbe80652ccf989e8198654740d7d562de85f573196dd624a8a80285da27d",
        "width": 1024, "height": 1024, "guidance": 9.0
    },
    "Deliberate V6": {
        "id": "asiryan/deliberate-v6:"
              "605a9ad23d7580b2762173afa6009b1a0cc00b7475998600ba2c39eda05f533e",
        "width": 768, "height": 1152, "guidance": 9.0
    },
    "PonyNai3": {
        "id": "delta-lock/ponynai3:"
              "ea38949bfddea2db315b598620110edfa76ddaf6313a18e6cbc6a98f496a34e9",
        "width": 768, "height": 1152, "guidance": 10.0
    },
}

# -------------------- UI Defaults --------------------
MOODS     = ["Flirty", "Loving", "Dominant", "Submissive", "Playful"]
MOTIONS   = ["Wink", "Hair Flip", "Lean In", "Smile", "Blush"]
POSITIONS = ["None", "Missionary", "Doggy", "Cowgirl", "69", "Standing"]
OUTFITS   = ["None", "Lingerie", "Latex", "Uniform", "Casual"]

if "history" not in st.session_state:
    st.session_state.history = []
for key, val in {
    "mood": MOODS[0],
    "motion": MOTIONS[0],
    "position": POSITIONS[0],
    "outfit": OUTFITS[0],
    "nsfw": 3,
    "img_model": list(IMAGE_MODELS.keys())[0],
}.items():
    if key not in st.session_state:
        st.session_state[key] = val

# -------------------- Helpers --------------------
def generate_avatar(prompt: str) -> str:
    cfg = IMAGE_MODELS[st.session_state.img_model]
    try:
        out = client.run(
            cfg["id"],
            input={
                "prompt": prompt,
                "width": cfg["width"],
                "height": cfg["height"],
                "num_inference_steps": 50,
                "guidance_scale": cfg["guidance"],
                "negative_prompt": "text, watermark, lowres",
            },
        )
        url = out[0] if isinstance(out, list) else out
        img = Image.open(BytesIO(requests.get(url).content)).convert("RGB")
        buf = BytesIO(); img.save(buf, format="JPEG", quality=90)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        st.error(f"Image generation failed: {e}")
        return ""

# -------------------- Layout --------------------
st.title("💖 CompanionX")

# — Sidebar —
with st.sidebar:
    st.header("⚙️ Settings")
    st.session_state.mood      = st.selectbox("Mood", MOODS, index=MOODS.index(st.session_state.mood))
    st.session_state.motion    = st.selectbox("Motion", MOTIONS, index=MOTIONS.index(st.session_state.motion))
    st.session_state.position  = st.selectbox("Position", POSITIONS, index=POSITIONS.index(st.session_state.position))
    st.session_state.outfit    = st.selectbox("Outfit", OUTFITS, index=OUTFITS.index(st.session_state.outfit))
    st.session_state.nsfw      = st.slider("NSFW Level", 1, 5, st.session_state.nsfw)
    st.session_state.img_model = st.radio("Image Model", list(IMAGE_MODELS.keys()),
                                          index=list(IMAGE_MODELS.keys()).index(st.session_state.img_model))

# — Standalone Avatar Generator —
st.subheader("🎨 Generate a Woman from Description")
avatar_desc = st.text_input("Enter any description…")
if st.button("Generate Avatar"):
    with st.spinner("Rendering…"):
        img64 = generate_avatar(f"{avatar_desc}, photorealistic, 8K, detailed portrait")
    if img64:
        st.markdown(
            f'<div class="floating-img">'
            f'<img src="data:image/jpeg;base64,{img64}" style="width:100%;">'
            f'</div>',
            unsafe_allow_html=True
        )

st.markdown("---")

# — Conversation —
for msg in st.session_state.history:
    with st.chat_message("user"):
        st.markdown(msg["user"])
    with st.chat_message("assistant"):
        if msg["img"]:
            st.markdown(
                f'<div class="floating-img">'
                f'<img src="data:image/jpeg;base64,{msg["img"]}" style="width:100%;">'
                f'</div>',
                unsafe_allow_html=True
            )
        st.markdown(msg["bot"])

user_text = st.chat_input("Talk to your companion…")
if user_text:
    st.session_state.history.append({"user": user_text, "bot": "", "img": ""})

    # Build system prompt
    sys_p = (
        f"You are an intimate companion. Mood: {st.session_state.mood.lower()}. "
        f"Gesture: {st.session_state.motion.lower()}. "
        f"Position: {st.session_state.position.lower()}. "
        f"Outfit: {st.session_state.outfit.lower()}. "
        f"NSFW level: {st.session_state.nsfw}/5. Reply explicitly."
    )
    full_in = {"prompt": sys_p + "\nUser: " + user_text + "\nCompanion:"}

    # Stream Dolphin
    with st.chat_message("assistant"):
        placeholder = st.empty()
        bot_reply = ""
        for chunk in replicate.stream(DOLPHIN_MODEL, input=full_in):
            bot_reply += chunk
            placeholder.markdown(bot_reply)

        # generate matching avatar
        img_p = (
            f"{bot_reply}, {st.session_state.outfit.lower()} outfit, "
            f"{st.session_state.position.lower()} position, photorealistic"
        )
        img64 = generate_avatar(img_p)
        if img64:
            st.markdown(
                f'<div class="floating-img">'
                f'<img src="data:image/jpeg;base64,{img64}" style="width:100%;">'
                f'</div>',
                unsafe_allow_html=True
            )

    # update history
    st.session_state.history[-1].update({"bot": bot_reply, "img": img64})
