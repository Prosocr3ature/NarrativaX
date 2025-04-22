import os
import time
import json
import sqlite3
import threading
import base64
from io import BytesIO
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

import streamlit as st
from PIL import Image
import replicate
import requests

# -------------------- Configuration --------------------
st.set_page_config(
    page_title="🍬 Candy AI Companions",
    page_icon="🍭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# hide default menu/footer
st.markdown("""
    <style>
      #MainMenu {visibility: hidden;}
      footer {visibility: hidden;}
      [data-testid="stSidebar"] {
        background: linear-gradient(180deg,#2a0a36 0%,#1a1a2e 100%) !important;
      }
      .companion-card {
        border-radius:15px;
        padding:15px;
        background:rgba(255,255,255,0.1);
        margin-bottom:10px;
        transition: transform .2s;
      }
      .companion-card:hover {transform:scale(1.03);cursor:pointer;}
      .header {background:linear-gradient(90deg,#ff6b6b 0%,#ff8e53 100%);
               -webkit-background-clip:text;-webkit-text-fill-color:transparent;}
    </style>
""", unsafe_allow_html=True)

# -------------------- API Keys --------------------
REPLICATE_TOKEN = os.getenv("REPLICATE_API_TOKEN")
if not REPLICATE_TOKEN:
    st.error("⚠️ Please set REPLICATE_API_TOKEN in your environment.")
    st.stop()
client = replicate.Client(api_token=REPLICATE_TOKEN)

# -------------------- Model Config --------------------
LLM_MODEL = "gryphe/mythomax-l2-13b"

IMAGE_MODELS = {
    "Reliberate v3": {
        "id": "asiryan/reliberate-v3:d70438fcb9bb7adb8d6e59cf236f754be0b77625e984b8595d1af02cdf034b29",
        "params": {"width":768,"height":1152,"guidance_scale":8.5}
    },
    "Babes XL": {
        "id": "asiryan/babes-xl:a07fcbe80652ccf989e8198654740d7d562de85f573196dd624a8a80285da27d",
        "params": {"width":1024,"height":1024,"guidance_scale":9}
    },
    "Realism XL": {
        "id": "asiryan/realism-xl:ff26a1f71bc27f43de016f109135183e0e4902d7cdabbcbb177f4f8817112219",
        "params": {"width":768,"height":1024,"guidance_scale":7.5}
    },
    "Deliberate V6": {
        "id": "asiryan/deliberate-v6:605a9ad23d7580b2762173afa6009b1a0cc00b7475998600ba2c39eda05f533e",
        "params": {"width":768,"height":1024,"guidance_scale":9}
    },
    "Pony Diffusion": {
        "id": "delta-lock/ponynai3:ea38949bfddea2db315b598620110edfa76ddaf6313a18e6cbc6a98f496a34e9",
        "params": {"width":768,"height":1024,"guidance_scale":10}
    },
}

MOODS   = ["Flirty","Loving","Dominant","Submissive","Playful"]
MOTIONS = ["Wink","Hair Flip","Lean In","Smile","Blush"]

QUICK_REPLIES = ["Tell me more…","Show me a smile 😊","Get closer…"]

# -------------------- Persistence (SQLite) --------------------
DB_PATH = "chats.db"
def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute("""
      CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY,
        companion TEXT,
        is_bot INTEGER,
        content TEXT,
        timestamp TEXT
      )
    """)
    conn.commit()
    return conn

db_conn = init_db()

def save_message(companion, is_bot, content):
    ts = datetime.utcnow().isoformat()
    db_conn.execute(
        "INSERT INTO messages(companion,is_bot,content,timestamp) VALUES (?,?,?,?)",
        (companion, int(is_bot), content, ts)
    )
    db_conn.commit()

def load_history(companion):
    cur = db_conn.execute(
        "SELECT is_bot,content,timestamp FROM messages WHERE companion=? ORDER BY id",
        (companion,)
    )
    return [{"is_bot":row[0],"content":row[1],"timestamp":row[2]} for row in cur]

# -------------------- Session State --------------------
if "companions" not in st.session_state:
    # default profiles
    st.session_state.companions = {
      "Raven":   {"age":23,"bio":"Yoga & gym enthusiast","prompt":"You push users to fitness limits","image":None},
      "Tatiana": {"age":24,"bio":"Head maid & dominatrix","prompt":"You maintain strict control","image":None},
      "Savannah":{"age":19,"bio":"Curious college freshman","prompt":"You explore adult life playfully","image":None},
    }
if "page" not in st.session_state:
    st.session_state.page = "home"
if "current" not in st.session_state:
    st.session_state.current = None
if "nsfw" not in st.session_state:
    st.session_state.nsfw = True
if "explicitness" not in st.session_state:
    st.session_state.explicitness = 3

executor = ThreadPoolExecutor(max_workers=2)

# -------------------- Helpers --------------------
def generate_response(user_input, companion_prompt, mood):
    sys = f"You are a {mood.lower()} virtual companion. {companion_prompt}"
    inp = f"{sys}\nUser: {user_input}\nCompanion:"
    try:
        return client.run(LLM_MODEL, input={
            "prompt": inp,
            "temperature":0.85,
            "max_new_tokens":250,
            "top_p":0.9,
            "repetition_penalty":1.1
        }).strip()
    except Exception:
        return "Hmm… let's try something else 😘"

def generate_gif(user_input, companion, mood, motion, count=4, delay=200):
    prompt = f"{companion['prompt']}, mood {mood.lower()}, action {motion}, reacting to “{user_input}”, intimate pose"
    frames = []
    for _ in range(count):
        try:
            urls = client.run(
                IMAGE_MODELS[st.session_state.image_model]["id"],
                input={**IMAGE_MODELS[st.session_state.image_model]["params"],
                       "prompt":prompt + ", photorealistic, 8K, detailed, sensual"}
            )
            url = urls[0] if isinstance(urls,list) else urls
            img = Image.open(BytesIO(requests.get(url).content)).convert("RGB")
            frames.append(img.resize((400,600)))
        except:
            continue
    if not frames:
        return None
    buf = BytesIO()
    frames[0].save(buf, format="GIF", save_all=True, append_images=frames[1:],
                   duration=delay, loop=0)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/gif;base64,{b64}"

# -------------------- UI Components --------------------
def render_sidebar():
    with st.sidebar:
        st.title("🍬 Candy AI")
        if st.button("🏠 Home", use_container_width=True):
            st.session_state.page = "home"
            st.session_state.current = None
        if st.button("🛠 Create Companion", use_container_width=True):
            st.session_state.page = "create"
        st.markdown("---")
        st.header("Your Companions")
        for name, data in st.session_state.companions.items():
            if st.button(f"{name} ({data['age']})", use_container_width=True):
                st.session_state.current = name
                st.session_state.page = "chat"
        st.markdown("---")
        st.checkbox("🔞 NSFW Mode", key="nsfw")
        st.slider("Explicitness",1,5,key="explicitness")
        st.selectbox("Image Style", list(IMAGE_MODELS.keys()), key="image_model")

def render_home():
    st.title("🍭 Meet Your Companions")
    cols = st.columns(3)
    for i,(name,data) in enumerate(st.session_state.companions.items()):
        col = cols[i%3]
        with col:
            st.markdown(f"<div class='companion-card'>", unsafe_allow_html=True)
            st.subheader(f"{name}, {data['age']}")
            st.caption(data["bio"])
            if st.button("Chat →", key=name):
                st.session_state.current = name
                st.session_state.page = "chat"
            st.markdown("</div>", unsafe_allow_html=True)

def render_create():
    st.title("✨ Create New Companion")
    with st.form("new_comp"):
        name = st.text_input("Name")
        age  = st.slider("Age", 18, 45, 25)
        bio  = st.text_area("Short Bio")
        prompt = st.text_area("System Prompt (personality)")
        submitted = st.form_submit_button("Add Companion")
    if submitted and name and bio and prompt:
        st.session_state.companions[name] = {"age":age,"bio":bio,"prompt":prompt,"image":None}
        st.success(f"Added companion {name}!")
        st.experimental_rerun()

def render_chat():
    companion = st.session_state.current
    data = st.session_state.companions[companion]
    st.header(f"💬 Chat with {companion}")
    st.subheader(data["bio"])
    # load history
    msgs = load_history(companion)
    for m in msgs:
        role = "assistant" if m["is_bot"] else "user"
        with st.chat_message(role):
            st.markdown(m["content"])
            st.caption(m["timestamp"])
    # controls
    col1, col2 = st.columns([2,1])
    with col1:
        mood   = st.selectbox("Mood",MOODS,key="chat_mood")
    with col2:
        motion = st.selectbox("Motion",MOTIONS,key="chat_motion")
    # user input
    user_input = st.chat_input("Say something…")
    if user_input:
        # save user
        save_message(companion, False, user_input)
        st.experimental_rerun()  # to show immediately

    # after rerun, detect new message
    if msgs and msgs[-1]["is_bot"]==0:
        # generate bot reply + gif in parallel
        last_user = msgs[-1]["content"]
        text_future  = executor.submit(generate_response, last_user, data["prompt"], st.session_state.chat_mood)
        gif_future   = executor.submit(generate_gif, last_user, data, st.session_state.chat_mood, st.session_state.chat_motion)

        with st.spinner("Companion is replying…"):
            reply = text_future.result(timeout=60)
            save_message(companion, True, reply)
        with st.spinner("Generating avatar GIF…"):
            gif_b64 = gif_future.result(timeout=120)
            if gif_b64:
                save_message(companion, True, f"![gif]({gif_b64})")
        st.experimental_rerun()

    # quick replies
    st.markdown("**Quick replies:**")
    cols = st.columns(len(QUICK_REPLIES))
    for i,qr in enumerate(QUICK_REPLIES):
        if cols[i].button(qr):
            save_message(companion, False, qr)
            st.experimental_rerun()

# -------------------- Main App --------------------
render_sidebar()

if st.session_state.page == "home":
    render_home()
elif st.session_state.page == "create":
    render_create()
elif st.session_state.page == "chat" and st.session_state.current:
    render_chat()
