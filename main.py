import os
import base64
import requests
import streamlit as st
from io import BytesIO
from PIL import Image
import replicate
from typing import Dict, List

# -------------------- Constants & Configuration --------------------
DEFAULT_MODEL = "mikeei/dolphin-2.9-llama3-70b-gguf:7cd1882cb3ea90756d09decf4bc8a259353354703f8f385ce588b71f7946f0aa"
NSFW_LEVELS = ["Mild", "Moderate", "Explicit", "Hardcore", "Unrestricted"]
MOTION_EMOJIS = {"Wink": "😉", "Hair Flip": "💁♀️", "Lean In": "👄", "Smile": "😊", "Blush": "😳"}

IMAGE_MODELS = {
    "Reliberate v3": {
        "id": "asiryan/reliberate-v3:d70438fcb9bb7adb8d6e59cf236f754be0b77625e984b8595d1af02cdf034b29",
        "width": 768, "height": 1152, "guidance": 8.5
    },
    "Unlimited XL": {
        "id": "asiryan/unlimited-xl:1a98916be7897ab4d9fbc30d2b20d070c237674148b00d344cf03ff103eb7082",
        "width": 768, "height": 1152, "guidance": 9.0
    },
    "Realism XL": {
        "id": "asiryan/realism-xl:ff26a1f71bc27f43de016f109135183e0e4902d7cdabbcbb177f4f8817112219",
        "width": 1024, "height": 1024, "guidance": 8.0
    },
    "Babes XL": {
        "id": "asiryan/babes-xl:a07fcbe80652ccf989e8198654740d7d562de85f573196dd624a8a80285da27d",
        "width": 1024, "height": 1024, "guidance": 9.0
    },
}

class CompanionCore:
    def __init__(self):
        self.client = replicate.Client(api_token=os.getenv("REPLICATE_API_TOKEN"))
        
    def generate_response(self, prompt: str, history: List[Dict]) -> str:
        messages = [{"role": "user", "content": prompt}]
        for h in history[-4:]:
            messages.append({"role": "assistant", "content": h["bot"]})
            
        return "".join(self.client.stream(DEFAULT_MODEL, input={"prompt": prompt}))
    
    def generate_image(self, prompt: str, model: str) -> str:
        cfg = IMAGE_MODELS[model]
        result = self.client.run(
            cfg["id"],
            input={
                "prompt": f"{prompt}, 8k resolution, cinematic lighting, photorealistic",
                "width": cfg["width"],
                "height": cfg["height"],
                "guidance_scale": cfg["guidance"],
                "negative_prompt": "text, watermark, lowres, deformed"
            }
        )
        return self._process_image(result[0])
    
    def _process_image(self, url: str) -> str:
        response = requests.get(url, timeout=15)
        img = Image.open(BytesIO(response.content)).convert("RGB")
        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        return base64.b64encode(buffer.getvalue()).decode()

class CompanionUI:
    def __init__(self):
        self.core = CompanionCore()
        self._init_session_state()
        self._setup_page_config()
        self._inject_custom_css()
        
    def _init_session_state(self):
        defaults = {
            "history": [],
            "mood": "Flirty",
            "motion": "Wink",
            "outfit": "Lingerie",
            "nsfw_level": 3,
            "img_model": list(IMAGE_MODELS.keys())[0],
            "current_image": "",
            "image_gallery": []
        }
        for key, value in defaults.items():
            st.session_state.setdefault(key, value)
            
    def _setup_page_config(self):
        st.set_page_config(
            page_title="🔥 Intima",
            page_icon="💋",
            layout="wide",
            initial_sidebar_state="collapsed"
        )
        
    def _inject_custom_css(self):
        st.markdown("""
        <style>
            /* Main layout */
            .main {background: #0a0a0a !important; color: #f0f0f0;}
            .st-emotion-cache-6qob1r {background: #1a1a1a;}
            
            /* Avatar panel */
            .avatar-panel {
                background: linear-gradient(45deg, #1a1a1a, #2a2a2a);
                border-radius: 15px;
                padding: 1rem;
                box-shadow: 0 0 20px rgba(255,50,150,0.1);
            }
            
            /* Chat bubbles */
            .user-bubble {
                background: #2b2b2b;
                border-radius: 15px 15px 0 15px;
                padding: 1rem;
                margin: 0.5rem 0;
                max-width: 70%;
                align-self: flex-end;
            }
            
            .bot-bubble {
                background: #363636;
                border-radius: 15px 15px 15px 0;
                padding: 1rem;
                margin: 0.5rem 0;
                max-width: 70%;
                align-self: flex-start;
            }
            
            /* Floating animation */
            @keyframes float {
                0%, 100% { transform: translateY(0); }
                50% { transform: translateY(-15px); }
            }
            .floating-avatar {
                animation: float 3s ease-in-out infinite;
                border-radius: 15px;
                border: 2px solid #ff3264;
                box-shadow: 0 0 30px rgba(255,50,100,0.3);
            }
            
            /* Quick actions bar */
            .quick-actions {
                position: fixed;
                bottom: 0;
                left: 0;
                right: 0;
                background: rgba(26,26,26,0.95);
                backdrop-filter: blur(10px);
                padding: 0.5rem;
                display: flex;
                gap: 0.5rem;
                overflow-x: auto;
                z-index: 999;
            }
        </style>
        """, unsafe_allow_html=True)
        
    def _render_sidebar(self):
        with st.sidebar:
            with st.expander("🛠️ Companion Settings", expanded=True):
                col1, col2 = st.columns(2)
                with col1:
                    st.session_state.mood = st.selectbox(
                        "Mood", ["Flirty", "Loving", "Dominant", "Submissive", "Playful"]
                    )
                    st.session_state.outfit = st.selectbox(
                        "Outfit", ["Lingerie", "Latex", "Uniform", "Casual", "Nude"]
                    )
                    
                with col2:
                    st.session_state.motion = st.selectbox(
                        "Gesture", list(MOTION_EMOJIS.keys()),
                        format_func=lambda x: f"{MOTION_EMOJIS[x]} {x}"
                    )
                    st.session_state.nsfw_level = st.select_slider(
                        "Intensity", options=NSFW_LEVELS,
                        value=NSFW_LEVELS[st.session_state.nsfw_level]
                    )
                    
                st.radio("Image Model", list(IMAGE_MODELS.keys()),
                        key="img_model", horizontal=True)
                
            if st.button("🧹 Clear History"):
                st.session_state.history = []
                st.rerun()
                
    def _render_avatar_panel(self):
        with st.container():
            st.markdown("### Your Companion 💖")
            if st.session_state.current_image:
                st.markdown(
                    f'<img class="floating-avatar" src="data:image/jpeg;base64,{st.session_state.current_image}" '
                    'style="width:100%; max-width:600px; margin:auto;">',
                    unsafe_allow_html=True
                )
            else:
                st.info("Start chatting to see your companion come to life...")
                
    def _render_chat(self):
        with st.container(height=700):
            for msg in st.session_state.history:
                self._render_message(msg)
                
            user_input = st.chat_input("Type your message...")
            if user_input:
                self._process_user_input(user_input)
                
    def _render_message(self, msg: Dict):
        if msg["role"] == "user":
            st.markdown(
                f'<div class="user-bubble">👤 {msg["content"]}</div>',
                unsafe_allow_html=True
            )
        else:
            col1, col2 = st.columns([1, 20])
            with col1:
                st.image(f"data:image/jpeg;base64,{msg['image']}", width=60)
            with col2:
                st.markdown(
                    f'<div class="bot-bubble">💋 {msg["response"]}</div>',
                    unsafe_allow_html=True
                )
                
    def _process_user_input(self, text: str):
        with st.status("💭 Processing...", expanded=False) as status:
            # Generate response
            status.update(label="💬 Generating response...", state="running")
            prompt = self._build_prompt(text)
            response = self.core.generate_response(prompt, st.session_state.history)
            
            # Generate image
            status.update(label="🎨 Creating visualization...", state="running")
            image_prompt = f"{response}, {st.session_state.outfit}, {st.session_state.mood}"
            image_b64 = self.core.generate_image(image_prompt, st.session_state.img_model)
            
            # Update session state
            st.session_state.history.append({
                "role": "user",
                "content": text,
                "image": ""
            })
            st.session_state.history.append({
                "role": "bot",
                "response": response,
                "image": image_b64
            })
            st.session_state.current_image = image_b64
            st.session_state.image_gallery.append(image_b64)
            
            st.rerun()
            
    def _build_prompt(self, text: str) -> str:
        return (
            f"NSFW Level: {st.session_state.nsfw_level}\n"
            f"Mood: {st.session_state.mood}\n"
            f"Gesture: {st.session_state.motion}\n"
            f"Outfit: {st.session_state.outfit}\n"
            f"User Input: {text}\n"
            "Response:"
        )
    
    def _render_quick_actions(self):
        actions = ["Blowjob", "Titty Fuck", "Handjob", "Lap Dance", "69", "Cowgirl"]
        st.markdown('<div class="quick-actions">', unsafe_allow_html=True)
        for action in actions:
            if st.button(f"🌟 {action}", key=f"qa_{action}"):
                self._process_quick_action(action)
        st.markdown('</div>', unsafe_allow_html=True)
        
    def _process_quick_action(self, action: str):
        with st.spinner(f"Performing {action}..."):
            response = self.core.generate_response(action, st.session_state.history)
            image_b64 = self.core.generate_image(
                f"{action}, {st.session_state.outfit}", 
                st.session_state.img_model
            )
            
            st.session_state.history.append({
                "role": "bot",
                "response": response,
                "image": image_b64
            })
            st.session_state.current_image = image_b64
            st.rerun()
            
    def run(self):
        self._render_sidebar()
        col1, col2 = st.columns([3, 7], gap="medium")
        
        with col1:
            with st.container():
                self._render_avatar_panel()
                
        with col2:
            self._render_chat()
            
        self._render_quick_actions()

if __name__ == "__main__":
    if not os.getenv("REPLICATE_API_TOKEN"):
        st.error("Missing REPLICATE_API_TOKEN in environment variables")
        st.stop()
        
    ui = CompanionUI()
    ui.run()
