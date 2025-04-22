import os
import base64
import requests
import streamlit as st
from io import BytesIO
from PIL import Image
import replicate

# -------------------- Page Config & Fullscreen CSS --------------------
st.set_page_config(
    page_title="💖 CompanionX",
    page_icon="💖",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
  /* hide default header & footer */
  #MainMenu, header, footer {visibility: hidden !important;}
  /* make the main container fill the viewport */
  .appview-container .main {padding: 0; margin: 0;}
  .block-container {padding: 0 1rem 1rem 1rem;}
  /* two‑panel layout */
  .panel {height: calc(100vh - 4rem); overflow: auto;}
  .avatar-panel {background: #111; color: white; padding:1rem;}
  .chat-panel {background: #1e1e1e; color: #ddd; padding:1rem;}
  /* Quick Actions bar */
  .quick-bar {
    position: fixed;
    bottom: 0; left: 0; right: 0;
    background: #222; padding: 0.5rem;
    display: flex; overflow-x: auto;
    z-index: 99;
  }
  .quick-bar button {
    margin-right: 0.5rem;
    background: #444; color: #fff;
    border: none; padding: 0.5rem 1rem;
    border-radius: 5px;
    cursor: pointer;
  }
  .quick-bar button:hover {background: #666;}
  /* Floating avatar */
  @keyframes float {0%,100%{transform:translateY(0);}50%{transform:translateY(-10px);}}
  .floating-img {animation: float 3s ease-in-out infinite; max-width:100%;}
</style>
""", unsafe_allow_html=True)

# -------------------- API Setup --------------------
REPLICATE_TOKEN = os.getenv("REPLICATE_API_TOKEN")
if not REPLICATE_TOKEN:
    st.error("⚠️ Please set REPLICATE_API_TOKEN in your environment.")
    st.stop()
client = replicate.Client(api_token=REPLICATE_TOKEN)

# -------------------- Models & Defaults --------------------
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

MOODS     = ["Flirty","Loving","Dominant","Submissive","Playful"]
MOTIONS   = ["Wink","Hair Flip","Lean In","Smile","Blush"]
POSITIONS = ["None","Missionary","Doggy","Cowgirl","69","Standing"]
OUTFITS   = ["None","Lingerie","Latex","Uniform","Casual"]
QUICK     = [
    "Blowjob","Titty Fucking","Handjob","Lap Dance","Strip Tease",
    "69","Doggy","Cowgirl","Missionary"
]

# initialize session state
if "history" not in st.session_state:
    st.session_state.history = []
defaults = dict(
    mood=MOODS[0],
    motion=MOTIONS[0],
    position=POSITIONS[0],
    outfit=OUTFITS[0],
    nsfw=3,
    img_model=list(IMAGE_MODELS.keys())[0],
    last_avatar=""
)
for k,v in defaults.items():
    st.session_state.setdefault(k, v)

# -------------------- Helpers --------------------
def gen_avatar(prompt: str, steps: int = 20) -> str:
    cfg = IMAGE_MODELS[st.session_state.img_model]
    result = client.run(
        cfg["id"],
        input={
            "prompt": prompt,
            "width": cfg["width"],
            "height": cfg["height"],
            "num_inference_steps": steps,
            "guidance_scale": cfg["guidance"],
            "negative_prompt": "text, watermark, lowres",
        },
    )
    url = result[0] if isinstance(result, list) else result
    img = Image.open(BytesIO(requests.get(url, timeout=10).content)).convert("RGB")
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=75)
    return base64.b64encode(buf.getvalue()).decode()

# -------------------- Mode Switch & Settings --------------------
mode = st.radio("", ["Chat","Instruct"], horizontal=True)

with st.expander("⚙️ Settings", expanded=False):
    st.selectbox("Mood", MOODS, key="mood")
    st.selectbox("Gesture", MOTIONS, key="motion")
    st.selectbox("Position", POSITIONS, key="position")
    st.selectbox("Outfit", OUTFITS, key="outfit")
    st.slider("NSFW Level", 1, 5, key="nsfw")
    st.radio("Image Model", list(IMAGE_MODELS.keys()), key="img_model")

# -------------------- Two‑Column Layout --------------------
col1, col2 = st.columns([3,7], gap="small")

with col1:
    st.markdown('<div class="panel avatar-panel">', unsafe_allow_html=True)
    st.markdown("### Your Companion")
    if st.session_state.last_avatar:
        st.markdown(
            f'<img class="floating-img" src="data:image/jpeg;base64,{st.session_state.last_avatar}">',
            unsafe_allow_html=True
        )
    else:
        st.info("Use Chat or Instruct to generate an avatar…")
    st.markdown("</div>", unsafe_allow_html=True)

with col2:
    st.markdown('<div class="panel chat-panel">', unsafe_allow_html=True)

    if mode == "Chat":
        # render history
        for turn in st.session_state.history:
            st.markdown(f"**You:** {turn['user']}")
            if turn["img"]:
                st.markdown(
                    f'<img class="floating-img" src="data:image/jpeg;base64,{turn["img"]}">',
                    unsafe_allow_html=True
                )
            st.markdown(f"**Her:** {turn['bot']}")

        # input box
        user_in = st.text_input("Talk to her…", key="chat_in")
        if user_in:
            # append user
            st.session_state.history.append({"user": user_in, "bot": "", "img": st.session_state.last_avatar})
            # build system prompt
            sys_p = (
                f"Mood:{st.session_state.mood.lower()} "
                f"Gesture:{st.session_state.motion.lower()} "
                f"Position:{st.session_state.position.lower()} "
                f"Outfit:{st.session_state.outfit.lower()} "
                f"NSFW:{st.session_state.nsfw}/5 "
                f"User:{user_in} Companion:"
            )
            # stream LLM
            bot_reply = ""
            ph = st.empty()
            for chunk in replicate.stream(DOLPHIN_MODEL, input={"prompt": sys_p}):
                bot_reply += chunk
                ph.markdown(f"**Her:** {bot_reply}")
            # generate new avatar
            img_prompt = f"{bot_reply}, {st.session_state.outfit.lower()}, {st.session_state.position.lower()}, photorealistic"
            new_img = gen_avatar(img_prompt)
            if new_img:
                st.session_state.last_avatar = new_img
            # update last turn
            st.session_state.history[-1].update(bot=bot_reply, img=new_img)

    else:  # Instruct mode
        instruction = st.text_area("Tell her exactly what to do…", key="instr_in")
        if st.button("Execute"):
            # run LLM
            bot_resp = client.run(DOLPHIN_MODEL, input={"prompt": instruction})
            st.markdown(f"**Her:** {bot_resp}")
            # new avatar
            new_img = gen_avatar(f"{instruction}, photorealistic")
            if new_img:
                st.session_state.last_avatar = new_img
                st.markdown(
                    f'<img class="floating-img" src="data:image/jpeg;base64,{new_img}">',
                    unsafe_allow_html=True
                )

    st.markdown("</div>", unsafe_allow_html=True)

# -------------------- Quick‑Actions Bar --------------------
st.markdown('<div class="quick-bar">', unsafe_allow_html=True)
for action in QUICK:
    if st.button(action, key=f"quick_{action}"):
        # record action
        st.session_state.history.append({
            "user": f"*Action:* {action}",
            "bot": "",
            "img": st.session_state.last_avatar
        })
        # LLM reaction
        resp = client.run(DOLPHIN_MODEL, input={"prompt": action})
        # new pose/avatar
        prompt_img = f"{action}, {st.session_state.outfit.lower()}, {st.session_state.position.lower()}, photorealistic"
        updated_img = gen_avatar(prompt_img)
        if updated_img:
            st.session_state.last_avatar = updated_img
        # update history turn
        st.session_state.history[-1].update(bot=resp, img=updated_img)
st.markdown('</div>', unsafe_allow_html=True)
