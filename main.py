import streamlit as st
import replicate
import os
from PIL import Image
import base64
from datetime import datetime

# -------------------- Configuration --------------------
st.set_page_config(
    page_title="🍬 Candy AI Companions",
    page_icon="🍭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -------------------- Styles --------------------
st.markdown("""
<style>
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #2a0a36 0%, #1a1a2e 100%) !important;
    }
    .companion-card {
        border-radius: 15px;
        padding: 20px;
        background: rgba(255,255,255,0.1);
        margin: 10px;
        transition: transform 0.2s;
    }
    .companion-card:hover {
        transform: scale(1.02);
        cursor: pointer;
    }
    .header {
        background: linear-gradient(90deg, #ff6b6b 0%, #ff8e53 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
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
    "Reliberate v3": {
        "id": "asiryan/reliberate-v3:d70438fcb9bb7adb8d6e59cf236f754be0b77625e984b8595d1af02cdf034b29",
        "params": {"width": 768, "height": 1152, "guidance_scale": 8.5}
    },
    # Add additional models with specific parameters as needed
}

MOODS = ["Flirty", "Loving", "Dominant", "Submissive", "Playful"]
MOTIONS = ["Wink", "Hair Flip", "Lean In", "Smile", "Blush"]

# -------------------- Helper Functions --------------------
def generate_response(prompt: str) -> str:
    """Generate companion response using Replicate"""
    try:
        output = client.run(
            LLM_MODEL,
            input={
                "prompt": prompt,
                "temperature": 0.85,
                "max_new_tokens": 250
            }
        )
        return output.strip().replace("</s>", "")
    except Exception as e:
        return "Hmm, let's explore that further... 😏"

def generate_image(prompt: str, model_name: str):
    """Generate dynamic images based on prompts"""
    model_info = IMAGE_MODELS[model_name]
    try:
        image_data = client.run(
            model_info["id"],
            input={"prompt": prompt, **model_info["params"]}
        )
        img = Image.open(BytesIO(image_data.content)).convert("RGB")
        buf = BytesIO()
        img.save(buf, format="JPEG")
        return base64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        return ""

# -------------------- Main App --------------------
def main():
    st.title("🍭 Candy AI Companions")
    
    # Sidebar for mood and model selection
    with st.sidebar:
        mood = st.selectbox("Choose the mood of your companion:", MOODS)
        image_model = st.selectbox("Select image model for generation:", list(IMAGE_MODELS.keys()))

    # User input for chat
    user_input = st.text_input("Type something to your AI companion:")
    
    if user_input:
        # Generate text response from LLM
        prompt = f"You are a companion in a {mood.lower()} mood. {user_input}"
        response = generate_response(prompt)
        
        # Generate image response
        image_prompt = f"{response} in a {mood.lower()} mood"
        image_b64 = generate_image(image_prompt, image_model)
        
        if image_b64:
            st.image(f"data:image/jpeg;base64,{image_b64}", use_column_width=True)
        st.markdown(f"**AI Companion**: {response}")
        
        # Update chat history dynamically
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []
        st.session_state.chat_history.append({"user": user_input, "bot": response, "image": image_b64})

        # Display chat history
        for chat in st.session_state.chat_history:
            st.markdown(f"**You**: {chat['user']}")
            st.markdown(f"**AI Companion**: {chat['bot']}")
            if chat["image"]:
                st.image(f"data:image/jpeg;base64,{chat['image']}", use_column_width=True)

if __name__ == "__main__":
    main()
