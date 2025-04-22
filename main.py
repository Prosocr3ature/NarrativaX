import os
import base64
import requests
import streamlit as st
from io import BytesIO
from PIL import Image
import replicate
from typing import Dict, List, Tuple

# ==================== CONSTANTS & CONFIGURATION ====================
DEFAULT_MODEL = "mikeei/dolphin-2.9-llama3-70b-gguf:7cd1882cb3ea90756d09decf4bc8a259353354703f8f385ce588b71f7946f0aa"
NSFW_LEVELS = ["Mild", "Moderate", "Explicit", "Hardcore", "Unrestricted"]

IMAGE_MODELS = {
    "Reliberate v3": {
        "id": "asiryan/reliberate-v3:d70438fcb9bb7adb8d6e59cf236f754be0b77625e984b8595d1af02cdf034b29",
        "width": 768,
        "height": 1152,
        "guidance": 8.5,
        "styles": ["Realistic", "Cinematic"]
    },
    "Unlimited XL": {
        "id": "asiryan/unlimited-xl:1a98916be7897ab4d9fbc30d2b20d070c237674148b00d344cf03ff103eb7082",
        "width": 768,
        "height": 1152,
        "guidance": 9.0,
        "styles": ["Fantasy", "Glamour"]
    },
    "Realism XL": {
        "id": "asiryan/realism-xl:ff26a1f71bc27f43de016f109135183e0e4902d7cdabbcbb177f4f8817112219",
        "width": 1024,
        "height": 1024,
        "guidance": 8.0,
        "styles": ["Photorealistic"]
    },
    "Babes XL": {
        "id": "asiryan/babes-xl:a07fcbe80652ccf989e8198654740d7d562de85f573196dd624a8a80285da27d",
        "width": 1024,
        "height": 1024,
        "guidance": 9.0,
        "styles": ["Glamour"]
    },
    "Deliberate V6": {
        "id": "asiryan/deliberate-v6:605a9ad23d7580b2762173afa6009b1a0cc00b7475998600ba2c39eda05f533e",
        "width": 768,
        "height": 1152,
        "guidance": 9.0,
        "styles": ["Artistic"]
    },
    "PonyNai3": {
        "id": "delta-lock/ponynai3:ea38949bfddea2db315b598620110edfa76ddaf6313a18e6cbc6a98f496a34e9",
        "width": 768,
        "height": 1152,
        "guidance": 10.0,
        "styles": ["Anime"]
    }
}

# ==================== CORE FUNCTIONALITY ====================
class CompanionEngine:
    """Handles all AI operations and image processing"""
    
    def __init__(self):
        self.client = replicate.Client(api_token=os.getenv("REPLICATE_API_TOKEN"))
    
    def generate_response(self, prompt: str, history: List[Dict]) -> Tuple[str, str]:
        """Generate conversational response with contextual awareness"""
        try:
            messages = [{"role": "user", "content": prompt}]
            messages += [{"role": "assistant", "content": h["response"]} 
                        for h in history[-4:] if h["role"] == "bot"]
            
            response = "".join(self.client.stream(DEFAULT_MODEL, input={"prompt": prompt}))
            return response.strip(), ""
        except Exception as e:
            return "", f"⚠️ Response Error: {str(e)}"
    
    def generate_image(self, prompt: str, model: str, appearance: str) -> Tuple[str, str]:
        """Generate contextual image with precise appearance control"""
        try:
            cfg = IMAGE_MODELS[model]
            full_prompt = (
                f"Ultra-detailed {cfg['styles'][0]} style, {appearance}, {prompt}, "
                f"8k resolution, intricate details, perfect anatomy"
            )
            
            result = self.client.run(
                cfg["id"],
                input={
                    "prompt": full_prompt,
                    "width": cfg["width"],
                    "height": cfg["height"],
                    "num_inference_steps": 35,
                    "guidance_scale": cfg["guidance"],
                    "negative_prompt": ("ugly, deformed, cartoon, text, watermark, "
                                      "low quality, bad anatomy, extra limbs")
                }
            )
            return self._process_image(result[0]), ""
        except Exception as e:
            return "", f"⚠️ Image Error: {str(e)}"

    def _process_image(self, url: str) -> str:
        """Process image URL to base64 with quality optimization"""
        response = requests.get(url, timeout=25)
        img = Image.open(BytesIO(response.content)).convert("RGB")
        img = img.resize((768, 1024), Image.Resampling.LANCZOS)
        buffer = BytesIO()
        img.save(buffer, format="WEBP", quality=95)
        return f"data:image/webp;base64,{base64.b64encode(buffer.getvalue()).decode()}"

# ==================== USER INTERFACE ====================
class CompanionInterface:
    """Manages the complete user interface and state"""
    
    def __init__(self):
        self.engine = CompanionEngine()
        self._init_session_state()
        self._configure_page()
    
    def _init_session_state(self):
        """Initialize all session state variables"""
        defaults = {
            "history": [],
            "appearance": ("22 year old female, flawless skin, hourglass figure, "
                         "C-cup breasts, long wavy hair, perfect facial features"),
            "personality": "Playful, seductive, and intelligent",
            "img_model": "Reliberate v3",
            "nsfw_level": "Explicit",
            "current_image": "",
            "processing": False,
            "initialized": False
        }
        for k, v in defaults.items():
            st.session_state.setdefault(k, v)
    
    def _configure_page(self):
        """Set up page configuration and styles"""
        st.set_page_config(
            page_title="AI Companion Pro",
            page_icon="💖",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        st.markdown("""
        <style>
            .main {background: #0a0a0a; color: #fff;}
            .sidebar .block-container {background: #1a1a1a; padding: 2rem 1rem;}
            .floating-img {
                animation: float 3s ease-in-out infinite;
                border-radius: 15px;
                border: 2px solid #ff3264;
                box-shadow: 0 0 25px rgba(255,50,100,0.3);
            }
            @keyframes float {
                0%, 100% { transform: translateY(0); }
                50% { transform: translateY(-12px); }
            }
            .chat-message {padding: 1.5rem; border-radius: 15px; margin: 1rem 0;}
            .user-message {background: #2b2b2b; margin-left: 25%; border: 1px solid #444;}
            .bot-message {background: #363636; margin-right: 25%; border: 1px solid #555;}
            .stTextInput input {background: #333; color: white;}
        </style>
        """, unsafe_allow_html=True)
    
    def _appearance_controls(self):
        """Render appearance customization panel"""
        with st.sidebar:
            with st.expander("🎨 COMPANION DESIGNER", expanded=True):
                st.text_area("Physical Description", key="appearance", height=150,
                            help="Be SPECIFIC: Age, body type, facial features, hair, etc.")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.selectbox("Art Style", list(IMAGE_MODELS.keys()), key="img_model")
                with col2:
                    st.select_slider("Content Intensity", options=NSFW_LEVELS, 
                                   key="nsfw_level", value="Explicit")
                
                if st.button("✨ GENERATE PREVIEW", type="primary", use_container_width=True):
                    self._generate_preview()
    
    def _generate_preview(self):
        """Generate initial companion preview image"""
        with st.spinner("Creating your perfect companion..."):
            img_b64, error = self.engine.generate_image(
                "Full body view, detailed features, studio lighting",
                st.session_state.img_model,
                st.session_state.appearance
            )
            if error:
                st.error(error)
            else:
                st.session_state.current_image = img_b64
                st.session_state.initialized = True
                st.rerun()
    
    def _render_companion_display(self):
        """Main companion visualization area"""
        col1, col2 = st.columns([4, 6])
        with col1:
            st.markdown("## Your Personal Companion")
            if st.session_state.current_image:
                st.markdown(
                    f'<img class="floating-img" src="{st.session_state.current_image}" style="width:100%">',
                    unsafe_allow_html=True
                )
                if st.button("🔄 Refresh Appearance", type="secondary"):
                    self._generate_preview()
            else:
                st.info("Describe appearance and generate preview to begin")
    
    def _render_chat_interface(self):
        """Interactive chat interface with history"""
        with st.container(height=700):
            # Display chat history
            for msg in st.session_state.history:
                self._render_chat_message(msg)
            
            # Process user input
            if prompt := st.chat_input("Message your companion..."):
                self._process_user_message(prompt)
    
    def _render_chat_message(self, msg: Dict):
        """Render individual chat message with styling"""
        if msg["role"] == "user":
            st.markdown(f'<div class="chat-message user-message">👤 YOU: {msg["content"]}</div>', 
                        unsafe_allow_html=True)
        else:
            cols = st.columns([1, 4])
            with cols[0]:
                st.image(msg["image"], width=120, output_format="WEBP")
            with cols[1]:
                st.markdown(
                    f'<div class="chat-message bot-message">💖 COMPANION: {msg["response"]}</div>',
                    unsafe_allow_html=True
                )
    
    def _process_user_message(self, text: str):
        """Handle complete message processing pipeline"""
        st.session_state.processing = True
        try:
            with st.status("Generating response...", expanded=True):
                # Generate text response
                prompt = self._build_prompt(text)
                response, error = self.engine.generate_response(prompt, st.session_state.history)
                if error:
                    raise Exception(error)
                
                # Generate contextual image
                img_prompt = f"Current context: {response}"
                img_b64, error = self.engine.generate_image(
                    img_prompt,
                    st.session_state.img_model,
                    st.session_state.appearance
                )
                if error:
                    raise Exception(error)
                
                # Update application state
                self._update_state(text, response, img_b64)
        except Exception as e:
            st.error(str(e))
        finally:
            st.session_state.processing = False
            st.rerun()
    
    def _build_prompt(self, text: str) -> str:
        """Construct context-aware prompt for LLM"""
        return f"""
        [APPEARANCE]
        {st.session_state.appearance}
        
        [PERSONALITY]
        {st.session_state.personality}
        
        [BEHAVIOR PROFILE]
        - NSFW Level: {st.session_state.nsfw_level}
        - Communication Style: Flirtatious but intelligent
        - Response Length: 2-3 detailed paragraphs
        
        [CONVERSATION HISTORY]
        {self._get_conversation_history()}
        
        [USER INPUT]
        {text}
        
        [RESPONSE]
        """
    
    def _get_conversation_history(self) -> str:
        """Get formatted conversation history"""
        return "\n".join(
            f"{'USER' if msg['role'] == 'user' else 'ASSISTANT'}: {msg['content']}" 
            for msg in st.session_state.history[-4:]
        )
    
    def _update_state(self, text: str, response: str, image: str):
        """Update session state with new interaction"""
        st.session_state.history.append({"role": "user", "content": text})
        st.session_state.history.append({
            "role": "bot",
            "response": response,
            "image": image
        })
        st.session_state.current_image = image
    
    def run(self):
        """Main application execution flow"""
        self._appearance_controls()
        self._render_companion_display()
        self._render_chat_interface()

# ==================== APPLICATION ENTRY POINT ====================
if __name__ == "__main__":
    if not os.getenv("REPLICATE_API_TOKEN"):
        st.error("Missing REPLICATE_API_TOKEN in environment variables")
        st.stop()
    
    try:
        CompanionInterface().run()
    except Exception as e:
        st.error(f"🚨 Critical Error: {str(e)}")
        st.stop()
