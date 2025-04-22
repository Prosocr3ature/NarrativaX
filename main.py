import os
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
    margin: 10px auto;
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
DOLPHIN_MODEL = (
    "mikeei/dolphin-2.9-llama3-70b-gguf:"
    "7cd1882cb3ea90756d09decf4bc8a259353354703f8f385ce588b71f7946f0aa"
)
IMAGE_MODELS = {
    "Reliberate v3": {
        "id": "asiryan/reliberate-v3:d70438fcb9bb7adb8d6e59cf236f754be0b77625e984b8595d1af02cdf034b29",
        "w":768, "h":1152, "g":8.5
    },
    "Unlimited XL": {
        "id": "asiryan/unlimited-xl:1a98916be7897ab4d9fbc30d2b20d070c237674148b00d344cf03ff103eb7082",
        "w":768, "h":1152, "g":9.0
    },
    # … add the rest …
}

# -------------------- UI Defaults --------------------
MOODS     = ["Flirty", "Loving", "Dominant", "Submissive", "Playful"]
MOTIONS   = ["Wink", "Hair Flip", "Lean In", "Smile", "Blush"]
POSITIONS = ["None", "Missionary", "Doggy", "Cowgirl", "69", "Standing"]
OUTFITS   = ["None", "Lingerie", "Latex", "Uniform", "Casual"]

# initialize session state
if "history" not in st.session_state:
    st.session_state.history = []  # list of {"user", "bot", "img_b64"}
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
                "num_inference_steps": 30,
                "guidance_scale": cfg["g"],
                "negative_prompt": "text, watermark, cartoon",
            },
        )
        url = out[0] if isinstance(out, list) else out
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        img = Image.open(BytesIO(resp.content)).convert("RGB")
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ""  # on failure, return empty

# -------------------- Layout --------------------
st.title("💖 CompanionX")

# — Sidebar Settings —
with st.sidebar:
    st.header("⚙️ Settings")
    st.session_state.mood     = st.selectbox("Mood", MOODS, index=MOODS.index(st.session_state.mood))
    st.session_state.motion   = st.selectbox("Gesture", MOTIONS, index=MOTIONS.index(st.session_state.motion))
    st.session_state.position = st.selectbox("Position", POSITIONS, index=POSITIONS.index(st.session_state.position))
    st.session_state.outfit   = st.selectbox("Outfit", OUTFITS, index=OUTFITS.index(st.session_state.outfit))
    st.session_state.nsfw     = st.slider("NSFW Level", 1, 5, st.session_state.nsfw)
    st.session_state.img_model= st.radio(
        "Image Model",
        list(IMAGE_MODELS.keys()),
        index=list(IMAGE_MODELS.keys()).index(st.session_state.img_model),
    )

# — One‑off Avatar Generator —
st.subheader("🎨 Generate a Woman from Description")
avatar_desc = st.text_input("Describe your ideal companion…")
if st.button("Generate Avatar"):
    with st.spinner("Rendering avatar…"):
        b64 = generate_avatar(f"{avatar_desc}, photorealistic, 8K, detailed portrait")
    if b64:
        st.markdown(
            f'<img class="floating-img" src="data:image/jpeg;base64,{b64}">',
            unsafe_allow_html=True,
        )
    else:
        st.error("⚠️ Avatar generation failed or timed out.")

st.markdown("---")

# — Chat History —
for turn in st.session_state.history:
    with st.chat_message("user"):
        st.markdown(turn["user"])
    with st.chat_message("assistant"):
        if turn["img"]:
            st.markdown(
                f'<img class="floating-img" src="data:image/jpeg;base64,{turn["img"]}">',
                unsafe_allow_html=True,
            )
        st.markdown(turn["bot"])

# — Chat Input —
user_input = st.chat_input("Talk to your companion…")
if user_input:
    # record user
    st.session_state.history.append({"user": user_input, "bot": "", "img": ""})

    # build system prompt
    sys_prompt = (
        f"You are an intimate companion. "
        f"Mood: {st.session_state.mood.lower()}. "
        f"Gesture: {st.session_state.motion.lower()}. "
        f"Position: {st.session_state.position.lower()}. "
        f"Outfit: {st.session_state.outfit.lower()}. "
        f"NSFW level: {st.session_state.nsfw}/5. "
        f"Reply explicitly to fulfill the user's desires."
    )
    full_prompt = f"{sys_prompt}\nUser: {user_input}\nCompanion:"

    # synchronous LLM call
    with st.spinner("Companion is thinking…"):
        try:
            bot_reply = client.run(DOLPHIN_MODEL, input={"prompt": full_prompt})
        except Exception:
            bot_reply = "⚠️ Sorry, I couldn't respond in time."

    # generate matching avatar in new pose/outfit
    avatar_prompt = (
        f"{bot_reply}, {st.session_state.outfit.lower()} outfit, "
        f"{st.session_state.position.lower()} position, photorealistic, 8K"
    )
    img_b64 = generate_avatar(avatar_prompt)

    # update last turn and re‑render
    st.session_state.history[-1].update({"bot": bot_reply, "img": img_b64})
    st.experimental_rerun()  # note: rerun to display immediately
