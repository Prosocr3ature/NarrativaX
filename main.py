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
    50%     { transform: translateY(-10px); }
  }
  .floating-img {
    display: block;
    margin: 0 auto;
    animation: float 4s ease-in-out infinite;
    max-width: 300px;
    border-radius: 15px;
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
DOLPHIN = "mikeei/dolphin-2.9-llama3-70b-gguf:7cd1882cb3ea90756d09decf4bc8a259353354703f8f385ce588b71f7946f0aa"
IMAGE_MODELS = {
    "Reliberate v3": {
        "id": "asiryan/reliberate-v3:d70438fcb9bb7adb8d6e59cf236f754be0b77625e984b8595d1af02cdf034b29",
        "w":768, "h":1152, "g":8.5
    },
    "Unlimited XL": {
        "id": "asiryan/unlimited-xl:1a98916be7897ab4d9fbc30d2b20d070c237674148b00d344cf03ff103eb7082",
        "w":768, "h":1152, "g":9.0
    },
    "Realism XL": {
        "id": "asiryan/realism-xl:ff26a1f71bc27f43de016f109135183e0e4902d7cdabbcbb177f4f8817112219",
        "w":1024,"h":1024,"g":8.0
    },
    "Babes XL": {
        "id": "asiryan/babes-xl:a07fcbe80652ccf989e8198654740d7d562de85f573196dd624a8a80285da27d",
        "w":1024,"h":1024,"g":9.0
    },
    "Deliberate V6": {
        "id": "asiryan/deliberate-v6:605a9ad23d7580b2762173afa6009b1a0cc00b7475998600ba2c39eda05f533e",
        "w":768,"h":1152,"g":9.0
    },
    "PonyNai3": {
        "id": "delta-lock/ponynai3:ea38949bfddea2db315b598620110edfa76ddaf6313a18e6cbc6a98f496a34e9",
        "w":768,"h":1152,"g":10.0
    },
}

# -------------------- UI Defaults --------------------
MOODS     = ["Flirty", "Loving", "Dominant", "Submissive", "Playful"]
MOTIONS   = ["Wink", "Hair Flip", "Lean In", "Smile", "Blush"]
POSITIONS = ["None", "Missionary", "Doggy", "Cowgirl", "69", "Standing"]
OUTFITS   = ["None", "Lingerie", "Latex", "Uniform", "Casual"]

if "history" not in st.session_state:
    st.session_state.history = []  # each item: {"user": str, "bot": str, "img": b64}
for k, v in {
    "mood": MOODS[0],
    "motion": MOTIONS[0],
    "position": POSITIONS[0],
    "outfit": OUTFITS[0],
    "nsfw": 3,
    "img_model": list(IMAGE_MODELS.keys())[0],
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# -------------------- Helpers --------------------
def generate_avatar(prompt: str) -> str:
    cfg = IMAGE_MODELS[st.session_state.img_model]
    try:
        out = client.run(
            cfg["id"],
            input={
                "prompt": prompt,
                "width": cfg["w"],
                "height": cfg["h"],
                "num_inference_steps": 30,   # speed up
                "guidance_scale": cfg["g"],
                "negative_prompt": "text, watermark, cartoon",
            },
        )
        url = out[0] if isinstance(out, list) else out
        img = Image.open(BytesIO(requests.get(url, timeout=15).content)).convert("RGB")
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=90)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        st.warning("⚠️ Avatar generation timed out or failed.")
        return ""

# -------------------- Layout --------------------
st.title("💖 CompanionX")
with st.sidebar:
    st.header("⚙️ Settings")
    st.session_state.mood     = st.selectbox("Mood", MOODS, index=MOODS.index(st.session_state.mood))
    st.session_state.motion   = st.selectbox("Gesture", MOTIONS, index=MOTIONS.index(st.session_state.motion))
    st.session_state.position = st.selectbox("Position", POSITIONS, index=POSITIONS.index(st.session_state.position))
    st.session_state.outfit   = st.selectbox("Outfit", OUTFITS, index=OUTFITS.index(st.session_state.outfit))
    st.session_state.nsfw     = st.slider("NSFW Level", 1, 5, st.session_state.nsfw)
    st.session_state.img_model= st.radio("Image Model", list(IMAGE_MODELS.keys()),
                                        index=list(IMAGE_MODELS.keys()).index(st.session_state.img_model))

# — Avatar‑only generator for one‑off descriptions —
st.subheader("🎨 Generate a Woman from Description")
desc = st.text_input("Describe your companion…")
if st.button("Generate Avatar"):
    with st.spinner("Rendering avatar…"):
        b64 = generate_avatar(f"{desc}, photorealistic, 8K, detailed portrait")
    if b64:
        st.markdown(
            f'<img class="floating-img" src="data:image/jpeg;base64,{b64}">',
            unsafe_allow_html=True
        )

st.markdown("---")

# — Chat history display —
for entry in st.session_state.history:
    with st.chat_message("user"):
        st.markdown(entry["user"])
    with st.chat_message("assistant"):
        if entry["img"]:
            st.markdown(
                f'<img class="floating-img" src="data:image/jpeg;base64,{entry["img"]}">',
                unsafe_allow_html=True
            )
        st.markdown(entry["bot"])

# — Chat input —
user_input = st.chat_input("Talk to your companion…")
if user_input:
    # append user side
    st.session_state.history.append({"user": user_input, "bot": "", "img": ""})

    # build system prompt
    sys_p = (
        f"You are an intimate companion. "
        f"Mood: {st.session_state.mood.lower()}. "
        f"Gesture: {st.session_state.motion.lower()}. "
        f"Position: {st.session_state.position.lower()}. "
        f"Outfit: {st.session_state.outfit.lower()}. "
        f"NSFW level: {st.session_state.nsfw}/5. "
        f"Reply explicitly, addressing the user's desires."
    )
    full_prompt = f"{sys_p}\nUser: {user_input}\nCompanion:"

    # stream the LLM reply
    bot_text = ""
    with st.chat_message("assistant"):
        placeholder = st.empty()
        try:
            for chunk in replicate.stream(DOLPHIN, input={"prompt": full_prompt}):
                bot_text += chunk
                placeholder.markdown(bot_text)
        except Exception:
            placeholder.markdown("⚠️ Chat generation timed out.")

        # instantly spin up a new image in a matching pose
        avatar_prompt = (
            f"{bot_text}, {st.session_state.outfit.lower()} outfit, "
            f"{st.session_state.position.lower()} position, photorealistic, 8K"
        )
        img_b64 = generate_avatar(avatar_prompt)
        if img_b64:
            st.markdown(
                f'<img class="floating-img" src="data:image/jpeg;base64,{img_b64}">',
                unsafe_allow_html=True
            )
        else:
            img_b64 = ""

    # update last history entry with bot side
    st.session_state.history[-1].update({"bot": bot_text, "img": img_b64})
