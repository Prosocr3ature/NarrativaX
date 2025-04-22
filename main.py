import os
import streamlit as st
import requests
import replicate
import base64
from io import BytesIO
from PIL import Image

# ——— Page Setup & Styling —————————————————————————————————————
st.set_page_config(
    page_title="💋 AI Companion Chat",
    page_icon="💋",
    layout="wide",
)
st.markdown("""
<style>
   /* Hide default Streamlit header & footer */
   #MainMenu, footer {visibility: hidden;}
   /* Dark background */
   [data-testid="stAppViewContainer"] {background: #0a0a0a;}
   /* Chat bubbles */
   .user {background:#2a2a2a; color:#fff; padding:12px; border-radius:8px; margin:6px 0;}
   .bot  {background:#3a3a3a; color:#eee; padding:12px; border-radius:8px; margin:6px 0;}
</style>
""", unsafe_allow_html=True)

# ——— Credentials ——————————————————————————————————————————————
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
if not OPENROUTER_API_KEY:
    st.error("🔑 Please set OPENROUTER_API_KEY in your environment.")
    st.stop()
if not REPLICATE_API_TOKEN:
    st.error("🔑 Please set REPLICATE_API_TOKEN in your environment.")
    st.stop()

# Initialize Replicate client
replicate_client = replicate.Client(api_token=REPLICATE_API_TOKEN)

# ——— Models & Controls ——————————————————————————————————————————
LLM_MODEL    = "gryphe/mythomax-l2-13b"
IMAGE_MODELS = {
    "Realistic":  "dreamlike-art/dreamlike-photoreal-2.0",
    "Reliberate": "stability-ai/sdxl"
}
MOODS = ["Flirty", "Loving", "Dominant", "Submissive", "Playful"]

# ——— Session State ——————————————————————————————————————————————
if "history" not in st.session_state:
    st.session_state.history = []  # [{speaker,text,img_b64},...]
if "mood" not in st.session_state:
    st.session_state.mood = MOODS[0]
if "style" not in st.session_state:
    st.session_state.style = list(IMAGE_MODELS.keys())[0]

# ——— Helper Functions ——————————————————————————————————————————
def chat_with_mythomax(system_prompt: str, user_prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        "temperature": 0.8,
        "max_tokens": 400
    }
    r = requests.post("https://openrouter.ai/api/v1/chat/completions",
                      headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()

def generate_avatar(prompt: str) -> str:
    model_id = IMAGE_MODELS[st.session_state.style]
    try:
        outputs = replicate_client.run(
            model_id,
            input={
                "prompt": prompt + ", photorealistic, 8k, detailed",
                "width": 768,
                "height": 1024,
                "num_outputs": 1
            }
        )
        url = outputs[0] if isinstance(outputs, (list,tuple)) else outputs
        img = Image.open(BytesIO(requests.get(url, timeout=20).content))
        buf = BytesIO(); img.save(buf, format="JPEG")
        return base64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        st.error(f"🖼️ Image Error: {e}")
        return ""

# ——— UI ——————————————————————————————————————————————————————
st.title("💋 AI Companion Chat")
st.write("A live, photoreal avatar powered by MythoMax & Stable Diffusion.")

# — Controls ————————————————————————————————————————————————
c1, c2 = st.columns(2)
with c1:
    st.session_state.mood = st.selectbox("Mood", MOODS,
                                         index=MOODS.index(st.session_state.mood))
with c2:
    st.session_state.style = st.radio("Image Style",
                                      list(IMAGE_MODELS.keys()),
                                      index=list(IMAGE_MODELS).index(st.session_state.style),
                                      horizontal=True)

st.markdown("---")

# — Render Conversation ——————————————————————————————————————
for msg in st.session_state.history:
    css = "user" if msg["speaker"]=="User" else "bot"
    if msg["speaker"]=="Companion" and msg["img_b64"]:
        st.image("data:image/jpeg;base64,"+msg["img_b64"],
                 use_column_width=True, caption="Companion")
    st.markdown(f"<div class='{css}'><b>{msg['speaker']}:</b> {msg['text']}</div>",
                unsafe_allow_html=True)

# — Chat Input —————————————————————————————————————————————————
user_text = st.chat_input("Say something to your companion…")
if user_text:
    # 1) record you
    st.session_state.history.append({
        "speaker":"User","text":user_text,"img_b64":""
    })

    # 2) build prompt
    recent = "\n".join(f"{h['speaker']}: {h['text']}"
                      for h in st.session_state.history[-6:])
    system_p = f"You are a sultry virtual companion. Mood: {st.session_state.mood.lower()}."
    user_p   = f"{recent}\nUser: {user_text}\nCompanion:"

    # 3) get reply
    with st.spinner("Companion is typing…"):
        reply = chat_with_mythomax(system_p, user_p)

    # 4) get avatar
    avatar_p = (f"virtual companion, mood {st.session_state.mood.lower()}, "
                f"reacting to '{user_text}', portrait")
    with st.spinner("Generating avatar…"):
        img64 = generate_avatar(avatar_p)

    # 5) record companion
    st.session_state.history.append({
        "speaker":"Companion","text":reply,"img_b64":img64
    })

    # no explicit rerun needed — state mutation triggers rerun itself
