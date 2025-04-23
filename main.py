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

SEXUAL_POSITIONS = [
    "Doggystyle", "Missionary", "Cowgirl", "Standing", "Kneeling",
    "Reverse Cowgirl", "Spooning", "Lotus", "Butterfly", "Anal"
]

ORAL_ACTIONS = [
    "Blowjob", "Deep Throat", "Face Fucking", "Cum in Mouth",
    "Cum on Face", "Tit Fuck", "Footjob", "Handjob"
]

IMAGE_MODELS = {
    "Unrestricted XL": {
        "id": "asiryan/unlimited-xl:1a98916be7897ab4d9fbc30d2b20d070c237674148b00d344cf03ff103eb7082",
        "width": 768,
        "height": 1152,
        "guidance": 9.0,
        "styles": ["NSFW", "Explicit"]
    },
    "Hardcore Edition": {
        "id": "asiryan/reliberate-v3:d70438fcb9bb7adb8d6e59cf236f754be0b77625e984b8595d1af02cdf034b29",
        "width": 768,
        "height": 1152,
        "guidance": 8.5,
        "styles": ["Hardcore"]
    },
    "Porn Diffusion": {
        "id": "delta-lock/ponynai3:ea38949bfddea2db315b598620110edfa76ddaf6313a18e6cbc6a98f496a34e9",
        "width": 768,
        "height": 1152,
        "guidance": 10.0,
        "styles": ["Hentai"]
    }
}

# ==================== CORE FUNCTIONALITY ====================
class NSFWCompanionEngine:
    """Handles explicit content generation with no restrictions"""
    
    def __init__(self):
        self.client = replicate.Client(api_token=os.getenv("REPLICATE_API_TOKEN"))
    
    def generate_response(self, prompt: str, history: List[Dict]) -> Tuple[str, str]:
        """Generate uncensored response"""
        try:
            messages = [{"role": "user", "content": f"NSFW ALLOWED. EXPLICIT CONTENT REQUIRED. {prompt}"}]
            
            response = "".join(self.client.stream(DEFAULT_MODEL, input={
                "prompt": prompt,
                "max_tokens": 2000,
                "temperature": 0.9
            }))
            return response.strip(), ""
        except Exception as e:
            return "", f"⚠️ Error: {str(e)}"
    
    def generate_image(self, prompt: str, model: str, appearance: str, actions: List[str]) -> Tuple[str, str]:
        """Generate explicit images with precise control"""
        try:
            cfg = IMAGE_MODELS[model]
            full_prompt = (
                f"ULTRA-EXPLICIT, UNCENSORED, {', '.join(actions)}, "
                f"{appearance}, {prompt}, "
                f"8k RAW photo, intricate details, perfect anatomy, "
                f"vaginal penetration, explicit nudity, "
                f"highly detailed skin texture"
            )
            
            result = self.client.run(
                cfg["id"],
                input={
                    "prompt": full_prompt,
                    "width": cfg["width"],
                    "height": cfg["height"],
                    "num_inference_steps": 45,
                    "guidance_scale": cfg["guidance"],
                    "negative_prompt": ("censored, blurry, cartoon, text, watermark, clothes"),
                    "safety_checker": False
                }
            )
            return self._process_image(result[0]), ""
        except Exception as e:
            return "", f"⚠️ Error: {str(e)}"

    def _process_image(self, url: str) -> str:
        """Process image with high-quality settings"""
        response = requests.get(url, timeout=25)
        img = Image.open(BytesIO(response.content)).convert("RGB")
        img = img.resize((1024, 1536), Image.Resampling.LANCZOS)
        buffer = BytesIO()
        img.save(buffer, format="WEBP", quality=100)
        return f"data:image/webp;base64,{base64.b64encode(buffer.getvalue()).decode()}"

# ==================== USER INTERFACE ====================
class NSFWCompanionInterface:
    """Uncensored interface with explicit controls"""
    
    def __init__(self):
        self.engine = NSFWCompanionEngine()
        self._init_session_state()
        self._configure_page()
    
    def _init_session_state(self):
        """Initialize explicit session state"""
        defaults = {
            "history": [],
            "appearance": "22yo Princess Jasmine, huge round tits, massive ass, tiny waist, thick thighs",
            "actions": [],
            "current_image": "",
            "processing": False,
            "model": "Unrestricted XL",
            "nsfw_level": "Unrestricted"
        }
        for k, v in defaults.items():
            st.session_state.setdefault(k, v)
    
    def _configure_page(self):
        """Configure adult-themed UI"""
        st.set_page_config(
            page_title="NSFW Companion Generator",
            page_icon="🔥",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        st.markdown("""
        <style>
            .main {background: #1a1a1a;}
            .sidebar .block-container {background: #2b2b2b;}
            .stButton>button {background: #ff4b4b!important;}
            .stTextArea textarea {background: #333!important;}
        </style>
        """, unsafe_allow_html=True)
    
    def _action_controls(self):
        """Explicit action selection panel"""
        with st.sidebar:
            with st.expander("💦 ACTION CONFIGURATOR", expanded=True):
                st.multiselect("Sexual Positions", SEXUAL_POSITIONS, key="positions")
                st.multiselect("Oral Actions", ORAL_ACTIONS, key="oral")
                st.text_area("Custom Actions", key="custom_actions",
                           help="Describe specific sexual acts in detail")
                
                if st.button("🎬 GENERATE SCENE", type="primary"):
                    self._generate_explicit_content()
    
    def _appearance_controls(self):
        """Detailed appearance controls"""
        with st.sidebar.expander("👙 BODY CUSTOMIZER", expanded=True):
            st.text_area("Physical Description", key="appearance", height=200,
                       value=st.session_state.appearance)
            st.selectbox("Model Version", list(IMAGE_MODELS.keys()), key="model")
    
    def _generate_explicit_content(self):
        """Generate explicit content handler"""
        st.session_state.processing = True
        try:
            actions = [
                *st.session_state.positions,
                *st.session_state.oral,
                st.session_state.custom_actions
            ]
            
            with st.spinner("Generating hardcore content..."):
                img_b64, error = self.engine.generate_image(
                    prompt=", ".join(actions),
                    model=st.session_state.model,
                    appearance=st.session_state.appearance,
                    actions=actions
                )
                
                if error:
                    st.error(error)
                else:
                    st.session_state.current_image = img_b64
                    st.rerun()
        finally:
            st.session_state.processing = False
    
    def _render_display(self):
        """Main display area"""
        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown("## Live Preview")
            if st.session_state.current_image:
                st.image(st.session_state.current_image, use_column_width=True)
            else:
                st.info("Configure settings and generate content")
        
        with col2:
            self._render_action_controls()
    
    def _render_action_controls(self):
        """Action configuration interface"""
        with st.expander("📝 SCENE DESIGNER", expanded=True):
            st.write("Combine positions and actions for complex scenes")
            if st.button("💦 GENERATE NEW VARIATION"):
                self._generate_explicit_content()
    
    def run(self):
        """Main execution flow"""
        self._action_controls()
        self._appearance_controls()
        self._render_display()

# ==================== APPLICATION ENTRY ====================
if __name__ == "__main__":
    if not os.getenv("REPLICATE_API_TOKEN"):
        st.error("REPLICATE_API_TOKEN not found")
        st.stop()
    
    try:
        NSFWCompanionInterface().run()
    except Exception as e:
        st.error(f"Fatal Error: {str(e)}")
        st.stop()
