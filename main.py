import os
import base64
import requests
import streamlit as st
from io import BytesIO
from PIL import Image
import replicate
from typing import Dict, List, Tuple, Union

# ==================== KONSTANTER & KONFIGURATION ====================
# Default‐beskrivning för karaktärens utseende och handlingar
DEFAULT_PROMPT = (
    "Princess Jasmine from Aladdin with huge round breasts, a massive ass, "
    "a tiny waist, thick thighs, wearing blue fishnet stockings, no underwear, "
    "and nipple piercings. "
    "Describe in detail what you want her to do."
)

IMAGE_MODELS: Dict[str, Dict] = {
    "Unrestricted XL": {
        "id": "asiryan/unlimited-xl:1a98916be7897ab4d9fbc30d2b20d070c237674148b00d344cf03ff103eb7082",
        "width": 768, "height": 1152, "guidance": 9.0
    },
    "Hardcore Edition": {
        "id": "asiryan/reliberate-v3:d70438fcb9bb7adb8d6e59cf236f754be0b77625e984b8595d1af02cdf034b29",
        "width": 768, "height": 1152, "guidance": 8.5
    },
    "Porn Diffusion": {
        "id": "delta-lock/ponynai3:ea38949bfddea2db315b598620110edfa76ddaf6313a18e6cbc6a98f496a34e9",
        "width": 768, "height": 1152, "guidance": 10.0
    }
}

# ==================== NSFW‐MOTOR ====================
class NSFWCompanionEngine:
    def __init__(self):
        token = os.getenv("REPLICATE_API_TOKEN")
        if not token:
            raise EnvironmentError("REPLICATE_API_TOKEN är inte satt")
        self.client = replicate.Client(api_token=token)

    def generate_image(
        self,
        model_name: str,
        prompt: str
    ) -> Tuple[str, str]:
        cfg = IMAGE_MODELS[model_name]
        model_id = cfg["id"]

        # System‐prefix för maximal frihet
        system_prefix = "NSFW ALLOWED. FOLLOW USER PROMPT EXACTLY."

        full_prompt = (
            f"{system_prefix} {prompt}. "
            "photorealistic, hyper-realistic lighting, studio lighting, "
            "8K RAW, sharp focus, realistic skin texture, intricate details, "
            "perfect anatomy, explicit nudity"
        )

        negative_prompt = (
            "deformed, mutated, disfigured, bad anatomy, lowres, blurry, "
            "cartoonish, extra limbs, watermark, text, oversaturated, unrealistic"
        )

        payload = {
            "prompt": full_prompt,
            "width": cfg["width"],
            "height": cfg["height"],
            "num_inference_steps": 80,
            "guidance_scale": min(cfg["guidance"], 10.0),
            "negative_prompt": negative_prompt,
            "safety_checker": False
        }

        try:
            result = self.client.run(model_id, input=payload)
        except Exception as e:
            return "", f"⚠️ Fel vid generering: {e}"

        if isinstance(result, list) and result:
            return self._fetch_and_encode(result[0]), ""
        return "", "⚠️ Oväntat format från modellen"

    def _fetch_and_encode(self, url: str) -> str:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        img = Image.open(BytesIO(resp.content)).convert("RGB")
        img = img.resize((1024, 1536), Image.Resampling.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="WEBP", quality=100)
        return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()

# ==================== ANVÄNDARGRÄNSSNITT ====================
class NSFWCompanionInterface:
    def __init__(self):
        self.engine = NSFWCompanionEngine()
        self._init_state()
        self._configure_page()

    def _init_state(self):
        st.session_state.setdefault("model", "Unrestricted XL")
        st.session_state.setdefault("prompt", DEFAULT_PROMPT)
        st.session_state.setdefault("current_image", "")
        st.session_state.setdefault("processing", False)

    def _configure_page(self):
        st.set_page_config(
            page_title="NSFW Companion Generator",
            page_icon="🔥",
            layout="wide"
        )
        st.markdown("""
        <style>
          .main {background: #1a1a1a;}
          .sidebar .block-container {background: #2b2b2b;}
          .stButton>button {background: #ff4b4b!important;}
          .stTextArea textarea {background: #333!important;}
        </style>
        """, unsafe_allow_html=True)

    def _controls(self):
        with st.sidebar:
            st.selectbox("Model Version", list(IMAGE_MODELS.keys()), key="model")
            st.text_area(
                "Scene & Action Description",
                key="prompt",
                height=250
            )
            if st.button("🎬 GENERATE IMAGE"):
                self._generate()

    def _generate(self):
        st.session_state.processing = True
        with st.spinner("Generating image…"):
            img_b64, err = self.engine.generate_image(
                model_name=st.session_state.model,
                prompt=st.session_state.prompt
            )
        st.session_state.processing = False

        if err:
            st.error(err)
        else:
            st.session_state.current_image = img_b64

    def _render(self):
        st.markdown("## Live Preview")
        if st.session_state.current_image:
            st.image(st.session_state.current_image, use_container_width=True)
        else:
            st.info("Enter your prompt in the sidebar and hit Generate")

    def run(self):
        self._controls()
        self._render()

if __name__ == "__main__":
    NSFWCompanionInterface().run()
