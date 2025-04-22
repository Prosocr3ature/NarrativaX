import os
import streamlit as st
import requests
import replicate
import base64
from io import BytesIO
from PIL import Image

# ——— Page & Style Setup —————————————————————————————————————————————
st.set_page_config(
    page_title="💋 AI Companion Chat",
    page_icon="💋",
    layout="wide",
)
st.markdown("""
    <style>
      /* Hide default Streamlit header & footer */
      #MainMenu, footer {visibility: hidden;}
      /* Darken background for immersion */
      [data-testid="stAppViewContainer"] {background: #0a0a0a;}
      /* Chat bubble styles */
      .user-msg {background: #2a2a2a; padding:10px; border-radius:10px; margin:5px 0; color:#fff;}
      .bot-msg  {background: #3a3a3a; padding:10px; border-radius:10px; margin:5px 0; color:#eee;}
    </style>
""", unsafe_allow_html=True)

# ——— Credentials —————————————————————————————————————————————————
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
if not OPENROUTER_API_KEY:
    st.error("🔑 Set OPENROUTER_API_KEY in your environment.")
    st.stop()
if not REPLICATE_API_TOKEN:
    st.error("🔑 Set REPLICATE_API_TOKEN in your environment.")
    st.stop()

# Initialize Replicate client
replicate_client = replicate.Client(api_token=REPLICATE_API_TOKEN)

# ——— Models & Options ——————————————————————————————————————————————
LLM_MODEL   = "gryphe/mythomax-l2-13b"
IMAGE_MODELS = {
    "Realistic":  "lucataco/realistic-vision-v5.1",
    "Reliberate": "asiryan/reliberate-v3",
}
MOODS = ["Flirty", "Loving", "Dominant", "Submissive", "Playful"]

# ——— Session State ————————————————————————————————————————————————
if "history" not in st.session_state:
    st.session_state.history = []  # list of dicts: {speaker, text, img_b64}
if "image_style" not in st.session_state:
    st.session_state.image_style = "Realistic"
if "mood" not in st.session_state:
    st.session_state.mood = MOODS[0]

# ——— Helpers ——————————————————————————————————————————————————————
def chat_with_mythomax(system_prompt: str, user_prompt: str) -> str:
    """Send a chat-completion request to OpenRouter/MythoMax."""
    hdr = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    msgs = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_prompt}
    ]
    payload = {
        "model": LLM_MODEL,
        "messages": msgs,
        "temperature": 0.8,
        "max_tokens": 400,
    }
    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=hdr, json=payload, timeout=30
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"❌ LLM Error: {e}"

def generate_avatar(prompt: str) -> str:
    """Generate one image via Replicate and return as base64 string."""
    model_id = IMAGE_MODELS[st.session_state.image_style]
    try:
        urls = replicate_client.run(
            model_id,
            input={
                "prompt": prompt + ", photorealistic, detailed, 8k",
                "width": 768,
                "height": 1024,
                "num_outputs": 1
            }
        )
        url = urls[0] if isinstance(urls, (list, tuple)) else urls
        img = Image.open(BytesIO(requests.get(url, timeout=20).content))
        buf = BytesIO()
        img.save(buf, format="JPEG")
        return base64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        st.error(f"🖼️ Image Error: {e}")
        return ""

# ——— UI —————————————————————————————————————————————————————————
st.title("💋 AI Companion Chat")
st.write("Chat live with a photorealistic avatar powered by MythoMax L2‑13B & Stable Diffusion.")

# — Controls: Mood & Image Style ————————————————————————————————
c1, c2 = st.columns([1,1])
with c1:
    st.session_state.mood = st.selectbox("Mood", MOODS, index=MOODS.index(st.session_state.mood))
with c2:
    st.session_state.image_style = st.radio(
        "Image Style",
        list(IMAGE_MODELS.keys()),
        index=list(IMAGE_MODELS).index(st.session_state.image_style),
        horizontal=True
    )

st.markdown("---")

# — Display conversation history ——————————————————————————————
for entry in st.session_state.history:
    if entry["speaker"] == "User":
        st.markdown(f"<div class='user-msg'>**You:** {entry['text']}</div>", unsafe_allow_html=True)
    else:
        with st.container():
            if entry["img_b64"]:
                st.image(
                    "data:image/jpeg;base64," + entry["img_b64"],
                    use_column_width=True,
                    caption="Companion"
                )
            st.markdown(f"<div class='bot-msg'>**Companion:** {entry['text']}</div>", unsafe_allow_html=True)

# — Chat input ———————————————————————————————————————————————————
user_text = st.chat_input("Say something to your companion…")
if user_text:
    # 1) Append user message
    st.session_state.history.append({
        "speaker": "User",
        "text": user_text,
        "img_b64": ""
    })

    # 2) Build system & user prompts
    recent = "\n".join(f"{h['speaker']}: {h['text']}" for h in st.session_state.history[-6:])
    system_prompt = f"You are a sultry virtual companion. Mood: {st.session_state.mood.lower()}."
    user_prompt = f"{recent}\nUser: {user_text}\nCompanion:"

    # 3) Generate companion reply
    with st.spinner("Companion is typing…"):
        bot_reply = chat_with_mythomax(system_prompt, user_prompt)

    # 4) Generate avatar reaction
    avatar_prompt = f"virtual companion, mood {st.session_state.mood.lower()}, reacting to '{user_text}', portrait"
    with st.spinner("Generating avatar…"):
        img_b64 = generate_avatar(avatar_prompt)

    # 5) Append bot message
    st.session_state.history.append({
        "speaker": "Companion",
        "text": bot_reply,
        "img_b64": img_b64
    })

    # 6) Rerun to show new content
    st.experimental_rerun()
