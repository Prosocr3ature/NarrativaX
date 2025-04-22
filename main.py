import os
import base64
import requests
import streamlit as st
from io import BytesIO
from PIL import Image
import replicate
from typing import Dict, List, Tuple

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
    """Core functionality for companion interactions and media generation"""
    
    def __init__(self):
        self.client = self._authenticate()
        
    def _authenticate(self):
        """Initialize Replicate client with environment token"""
        if not (token := os.getenv("REPLICATE_API_TOKEN")):
            raise ValueError("Missing REPLICATE_API_TOKEN in environment variables")
        return replicate.Client(api_token=token)
    
    @st.cache_data(show_spinner=False)
    def generate_response(_self, prompt: str, history: List[Dict]) -> Tuple[str, str]:
        """Generate AI response with contextual awareness"""
        try:
            messages = [{"role": "user", "content": prompt}]
            for h in history[-4:]:
                messages.append({"role": "assistant", "content": h["response"]})
            
            response = "".join(_self.client.stream(DEFAULT_MODEL, input={"prompt": prompt}))
            return response, ""
        except Exception as e:
            return "", f"⚠️ Failed to generate response: {str(e)}"
    
    @st.cache_data(show_spinner=False)
    def generate_image(_self, prompt: str, model: str) -> Tuple[str, str]:
        """Generate and process companion image"""
        try:
            cfg = IMAGE_MODELS[model]
            result = _self.client.run(
                cfg["id"],
                input={
                    "prompt": f"{prompt}, 8k resolution, cinematic lighting, photorealistic",
                    "width": cfg["width"],
                    "height": cfg["height"],
                    "guidance_scale": cfg["guidance"],
                    "negative_prompt": "text, watermark, lowres, deformed"
                }
            )
            return _self._process_image(result[0]), ""
        except Exception as e:
            return "", f"⚠️ Failed to generate image: {str(e)}"
    
    def _process_image(self, url: str) -> str:
        """Convert image URL to base64 encoded string"""
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        img = Image.open(BytesIO(response.content)).convert("RGB")
        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=90)
        return base64.b64encode(buffer.getvalue()).decode()

class CompanionUI:
    """User interface and interaction handler for companion app"""
    
    def __init__(self):
        self.core = CompanionCore()
        self._init_session_state()
        self._setup_page_config()
        self._inject_custom_css()
        
    def _init_session_state(self):
        """Initialize or reset session state variables"""
        defaults = {
            "history": [],
            "mood": "Flirty",
            "motion": "Wink",
            "outfit": "Lingerie",
            "nsfw_level": 2,
            "img_model": list(IMAGE_MODELS.keys())[0],
            "current_image": "",
            "image_gallery": [],
            "processing": False
        }
        for key, value in defaults.items():
            st.session_state.setdefault(key, value)
            
    def _setup_page_config(self):
        """Configure Streamlit page settings"""
        st.set_page_config(
            page_title="🔥 Intima Pro",
            page_icon="💞",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        
    def _inject_custom_css(self):
        """Inject custom CSS styles"""
        st.markdown("""
        <style>
            /* Enhanced main layout */
            .main {background: #0a0a0a !important; color: #f0f0f0;}
            .st-emotion-cache-6qob1r {background: #1a1a1a;}
            
            /* Modern avatar panel */
            .avatar-panel {
                background: linear-gradient(45deg, #1a1a1a, #2a2a2a);
                border-radius: 15px;
                padding: 1rem;
                box-shadow: 0 0 20px rgba(255,50,150,0.1);
                position: relative;
                overflow: hidden;
            }
            
            /* Animated chat bubbles */
            .user-bubble {
                background: #2b2b2b;
                border-radius: 15px 15px 0 15px;
                padding: 1rem;
                margin: 0.5rem 0;
                max-width: 70%;
                align-self: flex-end;
                transition: transform 0.2s ease;
            }
            
            .bot-bubble {
                background: #363636;
                border-radius: 15px 15px 15px 0;
                padding: 1rem;
                margin: 0.5rem 0;
                max-width: 70%;
                align-self: flex-start;
                transition: transform 0.2s ease;
            }
            
            /* Enhanced floating animation */
            @keyframes float {
                0%, 100% { transform: translateY(0); filter: drop-shadow(0 5px 15px rgba(255,50,100,0.4)); }
                50% { transform: translateY(-15px); filter: drop-shadow(0 10px 20px rgba(255,50,100,0.6)); }
            }
            .floating-avatar {
                animation: float 3s ease-in-out infinite;
                border-radius: 15px;
                border: 2px solid #ff3264;
                cursor: pointer;
                transition: transform 0.3s ease;
            }
            
            /* Professional quick actions */
            .quick-actions {
                position: fixed;
                bottom: 0;
                left: 0;
                right: 0;
                background: rgba(26,26,26,0.97);
                backdrop-filter: blur(12px);
                padding: 0.8rem;
                display: flex;
                gap: 0.8rem;
                justify-content: center;
                z-index: 999;
                border-top: 1px solid #333;
            }
            
            /* Loading spinner customization */
            .stSpinner > div { border-color: #ff3264 transparent transparent transparent !important; }
        </style>
        """, unsafe_allow_html=True)
        
    def _render_sidebar(self):
        """Render settings sidebar with state controls"""
        with st.sidebar:
            with st.expander("⚙️ Companion Settings", expanded=True):
                col1, col2 = st.columns(2)
                with col1:
                    st.session_state.mood = st.selectbox(
                        "Mood", ["Flirty", "Loving", "Dominant", "Submissive", "Playful"],
                        help="Set your companion's emotional state"
                    )
                    st.session_state.outfit = st.selectbox(
                        "Outfit", ["Lingerie", "Latex", "Uniform", "Casual", "Nude"],
                        help="Choose your companion's attire"
                    )
                    
                with col2:
                    st.session_state.motion = st.selectbox(
                        "Gesture", list(MOTION_EMOJIS.keys()),
                        format_func=lambda x: f"{MOTION_EMOJIS[x]} {x}",
                        help="Select companion's body language"
                    )
                    st.session_state.nsfw_level = st.select_slider(
                        "Intensity", options=NSFW_LEVELS,
                        value=NSFW_LEVELS[st.session_state.nsfw_level],
                        help="Control content explicitness"
                    )
                
                st.radio("Image Model", list(IMAGE_MODELS.keys()),
                        key="img_model", horizontal=True,
                        help="Select image generation model")
                
                self._render_management_controls()
                
    def _render_management_controls(self):
        """Render session management controls"""
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🧹 Clear History", help="Reset conversation history"):
                st.session_state.history = []
                st.session_state.current_image = ""
                st.rerun()
        with col2:
            if st.button("🔄 Reset All", help="Reset all settings to default"):
                self._init_session_state()
                st.rerun()
                
    def _render_avatar_panel(self):
        """Render companion avatar panel with interaction controls"""
        with st.container():
            st.markdown("### Your Companion 💖")
            if st.session_state.current_image:
                self._render_avatar_image()
                self._render_gallery_controls()
            else:
                st.info("Start chatting to see your companion come to life...")
                
    def _render_avatar_image(self):
        """Render main avatar image with hover effects"""
        st.markdown(
            f'<img class="floating-avatar" src="data:image/jpeg;base64,{st.session_state.current_image}" '
            'style="width:100%; max-width:600px; margin:auto; transform: scale(1);" '
            'onmouseover="this.style.transform=\'scale(1.02)\'" '
            'onmouseout="this.style.transform=\'scale(1)\'">',
            unsafe_allow_html=True
        )
                
    def _render_gallery_controls(self):
        """Render gallery navigation controls"""
        col1, col2, col3 = st.columns([2,6,2])
        with col1:
            if st.button("◀️ Previous", disabled=len(st.session_state.image_gallery) < 2):
                self._cycle_gallery(-1)
        with col3:
            if st.button("Next ▶️", disabled=len(st.session_state.image_gallery) < 2):
                self._cycle_gallery(1)
                
    def _cycle_gallery(self, direction: int):
        """Cycle through image gallery"""
        current_index = st.session_state.image_gallery.index(st.session_state.current_image)
        new_index = (current_index + direction) % len(st.session_state.image_gallery)
        st.session_state.current_image = st.session_state.image_gallery[new_index]
        st.rerun()
                
    def _render_chat(self):
        """Render chat interface with message history"""
        with st.container(height=700):
            for msg in st.session_state.history:
                self._render_message(msg)
                
            if not st.session_state.processing:
                user_input = st.chat_input("Type your message...")
                if user_input:
                    self._process_user_input(user_input)
                
    def _render_message(self, msg: Dict):
        """Render individual chat message with styling"""
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
        """Handle user input processing pipeline"""
        st.session_state.processing = True
        try:
            with st.status("💭 Processing...", expanded=False) as status:
                # Generate response
                status.update(label="💬 Generating response...", state="running")
                prompt = self._build_prompt(text)
                response, error = self.core.generate_response(prompt, st.session_state.history)
                
                if error:
                    st.error(error)
                    return
                
                # Generate image
                status.update(label="🎨 Creating visualization...", state="running")
                image_prompt = f"{response}, {st.session_state.outfit}, {st.session_state.mood}"
                image_b64, error = self.core.generate_image(image_prompt, st.session_state.img_model)
                
                if error:
                    st.error(error)
                    return
                
                # Update session state
                self._update_session_state(text, response, image_b64)
                
        finally:
            st.session_state.processing = False
            st.rerun()
            
    def _update_session_state(self, text: str, response: str, image_b64: str):
        """Update session state with new interaction"""
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
            
    def _build_prompt(self, text: str) -> str:
        """Construct context-aware prompt for AI model"""
        return (
            f"NSFW Level: {NSFW_LEVELS[st.session_state.nsfw_level]}\n"
            f"Mood: {st.session_state.mood}\n"
            f"Gesture: {st.session_state.motion}\n"
            f"Outfit: {st.session_state.outfit}\n"
            f"Previous Context: {self._get_recent_context()}\n"
            f"User Input: {text}\n"
            "Response:"
        )
    
    def _get_recent_context(self) -> str:
        """Extract recent conversation context"""
        return " | ".join([msg["content"] for msg in st.session_state.history[-3:]])
    
    def _render_quick_actions(self):
        """Render quick action buttons with enhanced UI"""
        actions = ["Blowjob", "Titty Fuck", "Handjob", "Lap Dance", "69", "Cowgirl"]
        st.markdown('<div class="quick-actions">', unsafe_allow_html=True)
        for action in actions:
            if st.button(f"✨ {action}", key=f"qa_{action}"):
                self._process_quick_action(action)
        st.markdown('</div>', unsafe_allow_html=True)
        
    def _process_quick_action(self, action: str):
        """Handle quick action processing"""
        st.session_state.processing = True
        try:
            with st.spinner(f"✨ Engaging {action}..."):
                response, error = self.core.generate_response(action, st.session_state.history)
                if error:
                    st.error(error)
                    return
                
                image_b64, error = self.core.generate_image(
                    f"{action}, {st.session_state.outfit}", 
                    st.session_state.img_model
                )
                if error:
                    st.error(error)
                    return
                
                self._update_session_state(f"*Action: {action}*", response, image_b64)
        finally:
            st.session_state.processing = False
            st.rerun()
            
    def run(self):
        """Main application runner"""
        self._render_sidebar()
        col1, col2 = st.columns([3, 7], gap="medium")
        
        with col1:
            with st.container():
                self._render_avatar_panel()
                
        with col2:
            self._render_chat()
            
        self._render_quick_actions()

if __name__ == "__main__":
    try:
        ui = CompanionUI()
        ui.run()
    except Exception as e:
        st.error(f"Critical Error: {str(e)}")
        st.stop()
