import os
import base64
import requests
import streamlit as st
from io import BytesIO
from PIL import Image
import replicate
from typing import Dict, List, Tuple

# ==================== CONSTANTS ====================
DEFAULT_MODEL = "mikeei/dolphin-2.9-llama3-70b-gguf:7cd1882cb3ea90756d09decf4bc8a259353354703f8f385ce588b71f7946f0aa"
NSFW_LEVELS = ["Mild", "Moderate", "Explicit", "Hardcore", "Unrestricted"]
SEXUAL_ACTIONS = [
    "Blowjob", "Deep Throat", "Titfuck", "Handjob", "Cowgirl", 
    "Missionary", "Doggy Style", "69", "Facial", "Cum in Mouth"
]

IMAGE_MODELS = {
    "Reliberate v3": {
        "id": "asiryan/reliberate-v3:d70438fcb9bb7adb8d6e59cf236f754be0b77625e984b8595d1af02cdf034b29",
        "width": 768,
        "height": 1152,
        "guidance": 8.5,
        "steps": 25  # Faster generation
    }
}

# ==================== CORE FUNCTIONALITY ====================
class CompanionCore:
    def __init__(self):
        self.client = replicate.Client(api_token=os.getenv("REPLICATE_API_TOKEN"))
    
    def generate_response(self, prompt: str) -> Tuple[str, str]:
        try:
            response = "".join(self.client.stream(DEFAULT_MODEL, input={"prompt": prompt}))
            return response, ""
        except Exception as e:
            return "", str(e)
    
    def generate_action_image(self, action: str, appearance: str) -> Tuple[str, str]:
        try:
            cfg = IMAGE_MODELS["Reliberate v3"]
            prompt = f"{appearance}, {action}, explicit details, realistic anatomy, 8k pornographic quality"
            
            result = self.client.run(
                cfg["id"],
                input={
                    "prompt": prompt,
                    "width": cfg["width"],
                    "height": cfg["height"],
                    "num_inference_steps": cfg["steps"],
                    "guidance_scale": cfg["guidance"],
                    "negative_prompt": "clothes, underwear, deformed, cartoon, text"
                }
            )
            return self._process_image(result[0]), ""
        except Exception as e:
            return "", str(e)

    def _process_image(self, url: str) -> str:
        response = requests.get(url, timeout=15)
        img = Image.open(BytesIO(response.content)).convert("RGB")
        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=90)
        return f"data:image/jpeg;base64,{base64.b64encode(buffer.getvalue()).decode()}"

# ==================== UI & STATE MANAGEMENT ====================
class CompanionUI:
    def __init__(self):
        self.core = CompanionCore()
        self._init_state()
        self._setup_ui()
        
    def _init_state(self):
        defaults = {
            "appearance": "22yo perfect female body, big natural tits, plump lips, seductive expression",
            "current_action": "",
            "current_image": "",
            "action_history": [],
            "processing": False
        }
        for k, v in defaults.items():
            st.session_state.setdefault(k, v)
            
    def _setup_ui(self):
        st.set_page_config(
            page_title="NSFW Companion", 
            page_icon="🔥", 
            layout="centered",
            initial_sidebar_state="collapsed"
        )
        st.markdown("""
        <style>
            [data-testid="stAppViewContainer"] {background: #000;}
            .action-button {transition: transform 0.2s; border: none!important; background: #222!important;}
            .action-button:hover {transform: scale(1.1); background: #333!important;}
            .floating-img {animation: float 2s ease-in-out infinite; border-radius: 15px;}
            @keyframes float {0%,100%{transform:translateY(0);}50%{transform:translateY(-10px);}}
        </style>
        """, unsafe_allow_html=True)
    
    def _render_action_buttons(self):
        cols = st.columns(3)
        for i, action in enumerate(SEXUAL_ACTIONS):
            with cols[i%3]:
                if st.button(f"🌟 {action}", key=f"act_{action}", 
                           on_click=self._trigger_action, args=(action,),
                           disabled=st.session_state.processing):
                    pass
    
    def _trigger_action(self, action: str):
        st.session_state.processing = True
        st.session_state.current_action = action
        self._process_action()
    
    def _process_action(self):
        with st.spinner(f"Performing {st.session_state.current_action}..."):
            # Generate image first for instant visual feedback
            img, err = self.core.generate_action_image(
                st.session_state.current_action,
                st.session_state.appearance
            )
            if err:
                st.error(f"Image Error: {err}")
                return
            
            # Generate text response
            prompt = f"""
            Perform {st.session_state.current_action} action, describe physical sensations and explicit details.
            Appearance: {st.session_state.appearance}
            Response:
            """
            response, err = self.core.generate_response(prompt)
            if err:
                st.error(f"Response Error: {err}")
                return
            
            # Update state
            st.session_state.action_history.append({
                "action": st.session_state.current_action,
                "image": img,
                "response": response
            })
            st.session_state.current_image = img
            
        st.session_state.processing = False
        st.rerun()
    
    def _render_interface(self):
        col1, col2 = st.columns([2, 3])
        
        with col1:
            st.markdown("### Action Controls")
            self._render_action_buttons()
            
            if st.session_state.current_image:
                st.markdown(f'<img class="floating-img" src="{st.session_state.current_image}" style="width:100%;">', 
                           unsafe_allow_html=True)
            else:
                st.info("Select an action to begin")
                
        with col2:
            st.markdown("### Action History")
            for entry in reversed(st.session_state.action_history):
                with st.expander(f"{entry['action']}", expanded=True):
                    cols = st.columns([1, 3])
                    with cols[0]:
                        st.image(entry["image"], use_column_width=True)
                    with cols[1]:
                        st.write(entry["response"])
    
    def run(self):
        self._render_interface()

# ==================== MAIN EXECUTION ====================
if __name__ == "__main__":
    if not os.getenv("REPLICATE_API_TOKEN"):
        st.error("REPLICATE_API_TOKEN environment variable required")
        st.stop()
    
    try:
        CompanionUI().run()
    except Exception as e:
        st.error(f"Fatal Error: {str(e)}")
        st.stop()
