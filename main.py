import os
import requests
import replicate
import streamlit as st
from io import BytesIO
from PIL import Image
from tempfile import NamedTemporaryFile

# ====================
# CONFIG & CONSTANTS
# ====================
IMAGE_MODEL = "asiryan/reliberate-v3:d70438fcb9bb7adb8d6e59cf236f754be0b77625e984b8595d1af02cdf034b29"
OPENROUTER_API = "https://openrouter.ai/api/v1/chat/completions"
MAX_TOKENS = 1024

# ====================
# SESSION STATE INIT
# ====================
def init_state():
    if "persona" not in st.session_state:
        st.session_state.persona = None          # dict with name & bio
    if "persona_image" not in st.session_state:
        st.session_state.persona_image = None    # PIL.Image
    if "chat_history" not in st.session_state:
        # list of (role, message) tuples
        st.session_state.chat_history = []

# ====================
# API CALLS
# ====================
def call_openrouter(messages):
    """messages: list of {"role":..., "content":...}"""
    headers = {
        "Authorization": f"Bearer {st.secrets['OPENROUTER_API_KEY']}",
        "Content-Type":  "application/json"
    }
    payload = {
        "model":       st.session_state.persona.get("model", "gryphe/mythomax-l2-13b"),
        "messages":    messages,
        "max_tokens":  MAX_TOKENS,
        "temperature": 0.8
    }
    r = requests.post(OPENROUTER_API, headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def generate_image(prompt):
    """Generate persona image via Replicate Reliberate NSFW."""
    out = replicate.run(
        IMAGE_MODEL,
        input={
            "prompt": prompt,
            "width": 512,
            "height": 512,
        }
    )
    url = out[0] if isinstance(out, list) else out
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return Image.open(BytesIO(resp.content))

# ====================
# UI
# ====================
def create_persona():
    st.header("👩 Create Your Virtual GF")
    name = st.text_input("Name her:", value="")
    bio  = st.text_area("Give her a little bio/traits:", height=100)
    model = st.selectbox(
        "Chat model",
        ["🧠 MythoMax","🐬 Dolphin","🤖 OpenChat"],
        index=0
    )
    if st.button("🎨 Generate Persona"):
        if not name.strip() or not bio.strip():
            st.warning("Please provide both a name and bio.")
            return
        with st.spinner("Generating her portrait…"):
            try:
                img = generate_image(f"photorealistic portrait of a {bio}")
                st.session_state.persona = {
                    "name": name.strip(),
                    "bio":  bio.strip(),
                    "model": {
                        "🧠 MythoMax": "gryphe/mythomax-l2-13b",
                        "🐬 Dolphin":  "cognitivecomputations/dolphin-mixtral",
                        "🤖 OpenChat":"openchat/openchat-3.5-0106"
                    }[model]
                }
                st.session_state.persona_image = img
                st.session_state.chat_history = []
                st.success(f"{name} is ready!")
            except Exception as e:
                st.error(f"Image generation failed: {e}")

def chat_interface():
    persona = st.session_state.persona
    st.sidebar.markdown(f"### Your Virtual GF: {persona['name']}")
    if st.sidebar.button("🔄 Reset Persona"):
        st.session_state.persona = None
        st.session_state.persona_image = None
        st.session_state.chat_history = []
        st.experimental_rerun()

    # Show her portrait
    st.image(st.session_state.persona_image, use_column_width=False, width=256, caption=persona["name"])
    st.markdown(f"**Bio:** {persona['bio']}")

    # Display chat history
    for role, msg in st.session_state.chat_history:
        if role == "user":
            st.chat_message("user").write(msg)
        else:
            st.chat_message(persona["name"]).write(msg)

    # Input
    user_input = st.chat_input("Say something…")
    if user_input:
        st.session_state.chat_history.append(("user", user_input))
        # build message list
        messages = [
            {"role":"system", "content":
                f"You are {persona['name']}, {persona['bio']}. Respond as her."}
        ]
        for role, msg in st.session_state.chat_history:
            messages.append({"role": role, "content": msg})
        try:
            with st.spinner("She’s typing…"):
                reply = call_openrouter(messages)
            st.session_state.chat_history.append(("assistant", reply))
            st.experimental_rerun()
        except Exception as e:
            st.error(f"Chat failed: {e}")

def main():
    st.set_page_config("Virtual GF", page_icon="💕", layout="wide")
    init_state()

    st.title("💕 Virtual GF Chat")
    if st.session_state.persona is None:
        create_persona()
    else:
        chat_interface()

if __name__ == "__main__":
    main()
