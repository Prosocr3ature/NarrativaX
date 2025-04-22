import os
import base64
import requests
import streamlit as st
import replicate

from io import BytesIO
from PIL import Image

# ====================
# CONFIG & CONSTANTS
# ====================
MODELS = {
    "🧠 MythoMax": "gryphe/mythomax-l2-13b",
    "🐬 Dolphin":  "cognitivecomputations/dolphin-mixtral",
    "🤖 OpenChat": "openchat/openchat-3.5-0106",
}

IMAGE_MODELS = {
    "🎨 Realistic Vision": "lucataco/realistic-vision-v5.1:2c8e954decbf70b7607a4414e5785ef9e4de4b8c51d50fb8b8b349160e0ef6bb",
    "🔥 Reliberate NSFW":  "asiryan/reliberate-v3:d70438fcb9bb7adb8d6e59cf236f754be0b77625e984b8595d1af02cdf034b29",
    "🔞 XL Porn Merge":    "John6666/uber-realistic-porn-merge-xl-urpmxl-v3-sdxl",
}

MAX_TOKENS = 1800
IMAGE_SIZE = (768, 1024)


# ====================
# HELPERS
# ====================
def call_openrouter(prompt: str, model_key: str) -> str:
    headers = {
        "Authorization": f"Bearer {st.secrets['OPENROUTER_API_KEY']}",
        "Content-Type": "application/json"
    }
    payload = {
        "model":       MODELS[model_key],
        "messages":    [{"role": "user", "content": prompt}],
        "max_tokens":  MAX_TOKENS,
        "temperature": 0.8
    }
    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers, json=payload, timeout=30
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def generate_image(prompt: str, model_key: str) -> Image.Image:
    version = IMAGE_MODELS[model_key]
    out = replicate.run(version, input={
        "prompt": prompt,
        "width":  IMAGE_SIZE[0],
        "height": IMAGE_SIZE[1],
    })
    url = out[0] if isinstance(out, list) else out
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return Image.open(BytesIO(resp.content))


def img_to_base64(img: Image.Image) -> str:
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode()


# ====================
# STATE INIT
# ====================
def init_state():
    if "persona_name" not in st.session_state:
        st.session_state.update({
            "persona_name":      "",
            "persona_bio":       "",
            "persona_model":     list(MODELS.keys())[0],
            "persona_img_model": list(IMAGE_MODELS.keys())[0],
            "persona_desc":      "",
            "persona_img":       None,
            "chat_history":      [],  # list of {"role","content"}
        })


# ====================
# MAIN
# ====================
def main():
    st.set_page_config("Virtual GF", "❤️", layout="centered")
    init_state()

    # --- GLOBAL CSS & FLOATING ANIMATION ---
    st.markdown("""
    <style>
      body { background:#111; color:#eee; }
      .img-container { text-align:center; margin:16px 0; }
      .img-container img {
        width:280px; border-radius:12px;
        animation: float 4s ease-in-out infinite;
      }
      @keyframes float {
        0%   { transform: translateY(0px); }
        50%  { transform: translateY(-10px); }
        100% { transform: translateY(0px); }
      }
      .chat { display:flex; flex-direction:column; gap:8px; margin-top:16px; }
      .user { align-self:flex-end; background:#0066cc; padding:8px 12px; border-radius:12px; max-width:80%; color:#fff; }
      .bot  { align-self:flex-start; background:#444;   padding:8px 12px; border-radius:12px; max-width:80%; color:#fff; }
      .input-row { display:flex; gap:8px; margin-top:12px; }
      .input-row input { flex:1; padding:8px; border-radius:8px; border:none; }
      .input-row button { padding:8px 16px; border:none; border-radius:8px; background:#28a745; color:#fff; }
    </style>
    """, unsafe_allow_html=True)

    st.title("👩‍💻 Create Your Virtual GF")

    # — Persona builder —
    st.text_input("Name her:", key="persona_name")
    st.text_area("Give her a little bio/traits:", key="persona_bio", height=80)
    st.selectbox("Chat model:", list(MODELS.keys()), key="persona_model")
    st.selectbox("Image model:", list(IMAGE_MODELS.keys()), key="persona_img_model")

    if st.button("🎨 Generate Persona"):
        if not (st.session_state.persona_name and st.session_state.persona_bio):
            st.error("Please enter both a name and some traits.")
        else:
            # Build system persona description
            sys_prompt = (
                f"You are a virtual girlfriend named {st.session_state.persona_name}. "
                f"{st.session_state.persona_bio}. Speak in-character, lightly flirtatious."
            )
            st.session_state.persona_desc = call_openrouter(
                sys_prompt, st.session_state.persona_model
            )
            # Initial portrait
            img_prompt = (
                f"Photorealistic portrait of {st.session_state.persona_name}, "
                f"{st.session_state.persona_bio}, friendly expression, studio lighting."
            )
            st.session_state.persona_img = generate_image(
                img_prompt, st.session_state.persona_img_model
            )

    # — Chat interface once persona exists —
    if st.session_state.persona_desc and st.session_state.persona_img:
        # Display current portrait
        b64 = img_to_base64(st.session_state.persona_img)
        st.markdown(f'''
          <div class="img-container">
            <img src="data:image/jpeg;base64,{b64}" alt="GF Portrait"/>
          </div>
        ''', unsafe_allow_html=True)

        # Chat history bubbles
        st.markdown("<div class='chat'>", unsafe_allow_html=True)
        for msg in st.session_state.chat_history:
            cls = "user" if msg["role"] == "user" else "bot"
            content = msg["content"].replace("\n", "<br/>")
            st.markdown(f'<div class="{cls}">{content}</div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        # Input form (auto‑clears)
        with st.form("chat_form", clear_on_submit=True):
            user_input = st.text_input("", key="chat_input", placeholder="Say something...")
            submitted = st.form_submit_button("➡️")
            if submitted and user_input.strip():
                # 1) add user message
                st.session_state.chat_history.append({
                    "role": "user", "content": user_input.strip()
                })

                # 2) build conversation prompt
                convo = st.session_state.persona_desc + "\n"
                for m in st.session_state.chat_history:
                    speaker = "User:" if m["role"]=="user" else f"{st.session_state.persona_name}:"
                    convo += f"{speaker} {m['content']}\n"
                convo += f"{st.session_state.persona_name}:"

                # 3) get her reply
                reply = call_openrouter(convo, st.session_state.persona_model)
                st.session_state.chat_history.append({
                    "role": "assistant", "content": reply
                })

                # 4) **Regenerate her portrait** based on your last line
                react_prompt = (
                    f"Photorealistic portrait of {st.session_state.persona_name} reacting to "
                    f"\"{user_input.strip()}\" with a warm, expressive look, "
                    f"{st.session_state.persona_bio}, ultra HD."
                )
                st.session_state.persona_img = generate_image(
                    react_prompt, st.session_state.persona_img_model
                )

                # force rerun so new image & message appear
                st.experimental_rerun()
    else:
        st.info("Fill in her name & bio, pick models, then click **Generate Persona** to begin.")

if __name__ == "__main__":
    main()
