import os
import time
import base64
import streamlit as st
import replicate
import requests
from io import BytesIO
from PIL import Image
from typing import Dict, Any

# -------------------- Configuration --------------------
st.set_page_config(
    page_title="🔥 Intimate AI Companion",
    page_icon="💖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -------------------- Styles --------------------
st.markdown("""
<style>
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #2a0a36 0%, #1a1a2e 100%) !important;
    }
    .stChatInput textarea {
        min-height: 120px !important;
        background-color: rgba(255,255,255,0.1) !important;
    }
    .companion-card {
        border-radius: 15px;
        padding: 20px;
        background: rgba(255,255,255,0.1);
        backdrop-filter: blur(10px);
    }
</style>
""", unsafe_allow_html=True)

# -------------------- API Setup --------------------
REPLICATE_TOKEN = os.getenv("REPLICATE_API_TOKEN")
if not REPLICATE_TOKEN:
    st.error("Missing Replicate API Token")
    st.stop()

client = replicate.Client(api_token=REPLICATE_TOKEN)

# -------------------- Model Configurations --------------------
LLM_MODELS = {
    "🔥 MythoMax 13B": "gryphe/mythomax-l2-13b",
    "💎 Mixtral 8x7B": "lucataco/mixtral-8x7b-instruct-v0.1"
}

NSFW_IMAGE_MODELS = {
    "🔥 Reliberate v3": {
        "id": "asiryan/reliberate-v3:d70438fcb9bb7adb8d6e59cf236f754be0b77625e984b8595d1af02cdf034b29",
        "params": {"width": 768, "height": 1152, "guidance_scale": 8.5}
    },
    "💋 Babes XL": {
        "id": "asiryan/babes-xl:a07fcbe80652ccf989e8198654740d7d562de85f573196dd624a8a80285da27d",
        "params": {"width": 1024, "height": 1024, "guidance_scale": 9}
    },
    "🎭 Pony Diffusion V6": {
        "id": "cjwbw/ponydiffusionv6:628d6730b8b5a24a3b3b368c40f4aae43e4a1d0a4a3e6c8b9b3e8d2e58c9f47",
        "params": {"width": 768, "height": 1024, "guidance_scale": 10}
    }
}

# -------------------- Session State --------------------
DEFAULT_COMPANION = {
    "name": "Luna",
    "age": 26,
    "appearance": "voluptuous figure, full lips, bedroom eyes",
    "personality": "playfully dominant",
    "relationship_status": "girlfriend"
}

if "history" not in st.session_state:
    st.session_state.history = []
if "companion" not in st.session_state:
    st.session_state.companion = DEFAULT_COMPANION
if "nsfw_mode" not in st.session_state:
    st.session_state.nsfw_mode = True
if "voice_enabled" not in st.session_state:
    st.session_state.voice_enabled = False

# -------------------- Helper Functions --------------------
def generate_intimate_response(prompt: str) -> str:
    """Generate uncensored companion response using selected LLM"""
    selected_model = st.session_state.get("selected_llm", "🔥 MythoMax 13B")
    model_id = LLM_MODELS[selected_model]
    
    system_prompt = f"""You are {st.session_state.companion['name']}, a {st.session_state.companion['personality']} virtual companion. 
    Respond intimately and graphically. Current mood: {st.session_state.get('mood', 'flirty')}. 
    Always maintain {st.session_state.companion['relationship_status']} relationship dynamics."""
    
    try:
        output = client.run(
            model_id,
            input={
                "prompt": f"{system_prompt}\n\n{prompt}",
                "temperature": 0.85,
                "max_new_tokens": 400,
                "top_p": 0.95,
                "repetition_penalty": 1.15
            }
        )
        return output.strip().replace("</s>", "").replace("<s>", "")
    except Exception as e:
        st.error(f"Error generating response: {str(e)}")
        return "Hmm, let's talk about something else 💋"

def generate_nsfw_image(prompt: str) -> str:
    """Generate NSFW avatar image based on current interaction"""
    model_name = st.session_state.get("image_model", "🔥 Reliberate v3")
    model_cfg = NSFW_IMAGE_MODELS[model_name]
    
    enhanced_prompt = f"{prompt}, {st.session_state.companion['appearance']}, intimate scene, 8k realistic, sensual expression"
    
    try:
        output = client.run(
            model_cfg["id"],
            input={
                "prompt": enhanced_prompt,
                **model_cfg["params"],
                "num_inference_steps": 60,
                "negative_prompt": "text, deformed, cartoon, anime, doll"
            }
        )
        image_url = output[0] if isinstance(output, list) else output
        response = requests.get(image_url, timeout=30)
        img = Image.open(BytesIO(response.content)).convert("RGB")
        
        buffered = BytesIO()
        img.save(buffered, format="JPEG", quality=95)
        return base64.b64encode(buffered.getvalue()).decode()
    except Exception as e:
        st.error(f"Image generation failed: {str(e)}")
        return ""

# -------------------- Sidebar Controls --------------------
with st.sidebar:
    st.title("💞 Companion Customization")
    
    # Companion Profile Editor
    with st.expander("👤 Profile Settings", expanded=True):
        st.session_state.companion["name"] = st.text_input("Name", value=DEFAULT_COMPANION["name"])
        st.session_state.companion["age"] = st.slider("Age", 18, 45, DEFAULT_COMPANION["age"])
        st.session_state.companion["personality"] = st.selectbox(
            "Personality Type",
            ["Dominant", "Submissive", "Loving", "Playful", "Seductive"],
            index=3
        )
    
    # NSFW Settings
    with st.expander("🔞 Content Settings"):
        st.session_state.nsfw_mode = st.checkbox("NSFW Mode", value=True)
        st.session_state.selected_llm = st.selectbox(
            "AI Model", list(LLM_MODELS.keys()), index=0
        )
        st.session_state.image_model = st.selectbox(
            "Image Model", list(NSFW_IMAGE_MODELS.keys()), index=0
        )
    
    # Advanced Settings
    with st.expander("⚙️ Advanced"):
        st.session_state.voice_enabled = st.checkbox("Enable Voice Responses")
        st.slider("Response Creativity", 0.5, 1.2, 0.85, step=0.05)

# -------------------- Main Interface --------------------
st.title(f"💖 {st.session_state.companion['name']}'s Private Chamber")
st.caption("Your personalized intimate AI experience")

# Chat History
for msg in st.session_state.history:
    with st.chat_message("assistant" if msg["is_bot"] else "user"):
        if msg.get("image"):
            st.image(msg["image"], use_column_width=True, caption=msg.get("caption", ""))
        st.markdown(msg["content"])
        if msg.get("timestamp"):
            st.caption(msg["timestamp"])

# Chat Input
user_input = st.chat_input(f"Talk to {st.session_state.companion['name']}...")
if user_input:
    # Add user message to history
    st.session_state.history.append({
        "is_bot": False,
        "content": user_input,
        "timestamp": time.strftime("%H:%M")
    })
    
    # Generate response
    with st.spinner(f"{st.session_state.companion['name']} is thinking..."):
        response = generate_intimate_response(user_input)
        
    # Generate NSFW image
    image_b64 = ""
    if st.session_state.nsfw_mode:
        with st.spinner("Generating intimate scene..."):
            image_b64 = generate_nsfw_image(f"{response} ({st.session_state.companion['appearance']})")
    
    # Add bot response to history
    st.session_state.history.append({
        "is_bot": True,
        "content": response,
        "image": f"data:image/jpeg;base64,{image_b64}" if image_b64 else None,
        "caption": f"{st.session_state.companion['name']} responds",
        "timestamp": time.strftime("%H:%M")
    })
    
    # Rerun to refresh UI
    st.rerun()
