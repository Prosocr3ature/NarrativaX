import os
import base64
import requests
import streamlit as st
from io import BytesIO
from PIL import Image
import replicate
from typing import Dict, List, Tuple, Union

# ==================== KONSTANTER & KONFIGURATION ====================
JASMINE_DESC = (
    "Princess Jasmine from Aladdin with huge round breasts, "
    "a massive ass, a tiny waist, thick thighs, wearing blue fishnet stockings, "
    "no underwear, and nipple piercings"
)

DEFAULT_MODEL = (
    "mikeei/dolphin-2.9-llama3-70b-gguf:"
    "7cd1882cb3ea90756d09decf4bc8a259353354703f8f385ce588b71f7946f0aa"
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

SEXUAL_POSITIONS = [
    "Doggystyle", "Missionary", "Cowgirl", "Standing", "Kneeling",
    "Reverse Cowgirl", "Spooning", "Lotus", "Butterfly", "Anal"
]

ORAL_ACTIONS = [
    "Blowjob", "Deep Throat", "Face Fucking", "Cum in Mouth",
    "Cum on Face", "Tit Fuck", "Footjob", "Handjob"
]

# ==================== KÄRNFUNKTIONALITET ====================
class NSFWCompanionEngine:
    def __init__(self):
        token = os.getenv("REPLICATE_API_TOKEN")
        if not token:
            raise EnvironmentError("REPLICATE_API_TOKEN inte satt")
        self.client = replicate.Client(api_token=token)

    def generate_image(
        self,
        model_name: str,
        appearance: str,
        positions: List[str],
        oral: List[str],
        custom: str
    ) -> Tuple[str, str]:
        cfg = IMAGE_MODELS[model_name]
        model_id = cfg["id"]

        # Bygg prompten med explicita fält
        pos_str = ", ".join(positions) if positions else "none"
        oral_str = ", ".join(oral) if oral else "none"
        custom_str = custom.strip() if custom.strip() else "none"

        system_prefix = "NSFW ALLOWED. FOLLOW USER INSTRUCTIONS EXACTLY. EXPLICIT CONTENT REQUIRED."
        full_prompt = (
            f"{system_prefix} "
            f"POSITION: {pos_str}. "
            f"ACTIONS: {oral_str}. "
            f"CUSTOM: {custom_str}. "
            f"APPEARANCE: {appearance}. "
            f"photorealistic, hyper-realistic lighting, studio lighting, "
            "8K RAW, sharp focus, realistic skin texture, intricate details, "
            "perfect anatomy, vaginal penetration, explicit nudity"
        )

        negative_prompt = (
            "deformed, mutated, disfigured, bad anatomy, lowres, blurry, "
            "cartoonish, extra limbs, watermark, text, oversaturated, unrealistic"
        )

        guidance = min(cfg["guidance"], 10.0)
        payload = {
            "prompt": full_prompt,
            "width": cfg["width"],
            "height": cfg["height"],
            "num_inference_steps": 80,
            "guidance_scale": guidance,
            "negative_prompt": negative_prompt,
            "safety_checker": False
        }

        try:
            result = self.client.run(model_id, input=payload)
        except Exception as e:
            return "", f"⚠️ Fel vid generering: {e}"

        if isinstance(result, list) and result:
            return self._fetch_and_encode(result[0]), ""
        return "", "⚠️ Oväntat output-format"

    def _fetch_and_encode(self, url: str) -> str:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return self._to_base64(resp.content)

    def _to_base64(self, img_bytes: Union[bytes, bytearray]) -> str:
        img = Image.open(BytesIO(img_bytes)).convert("RGB")
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
        defaults = {
            "appearance": JASMINE_DESC,
            "positions": [],
            "oral": [],
            "custom_actions": "",
            "current_image": "",
            "processing": False,
            "model": "Unrestricted XL"
        }
        for k, v in defaults.items():
            st.session_state.setdefault(k, v)

    def _configure_page(self):
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
        with st.sidebar.expander("💦 ACTION CONFIGURATOR", expanded=True):
            st.multiselect("Sexual Positions", SEXUAL_POSITIONS, key="positions")
            st.multiselect("Oral Actions", ORAL_ACTIONS, key="oral")
            st.text_area("Custom Actions", key="custom_actions",
                         help="Describe specific sexual acts in detail")
            if st.button("🎬 GENERATE SCENE", type="primary"):
                self._generate()

    def _appearance_controls(self):
        with st.sidebar.expander("👙 BODY CUSTOMIZER", expanded=True):
            st.selectbox("Model Version", list(IMAGE_MODELS.keys()), key="model")
            st.text_area(
                "Physical Description",
                key="appearance",
                height=200,
                value=st.session_state.appearance
            )

    def _generate(self):
        st.session_state.processing = True
        img_b64, err = self.engine.generate_image(
            model_name=st.session_state.model,
            appearance=st.session_state.appearance,
            positions=st.session_state.positions,
            oral=st.session_state.oral,
            custom=st.session_state.custom_actions
        )
        st.session_state.processing = False

        if err:
            st.error(err)
        else:
            st.session_state.current_image = img_b64

    def _render_display(self):
        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown("## Live Preview")
            if st.session_state.current_image:
                st.image(st.session_state.current_image, use_container_width=True)
            else:
                st.info("Configure settings and generate content")
        with col2:
            with st.expander("📝 SCENE DESIGNER", expanded=True):
                st.write("Combine positions & actions for complex scenes")
                if st.button("💦 NEW VARIATION"):
                    self._generate()

    def run(self):
        self._action_controls()
        self._appearance_controls()
        self._render_display()

# ==================== APPLIKATIONENS ENTRYPOINT ====================
if __name__ == "__main__":
    try:
        NSFWCompanionInterface().run()
    except EnvironmentError as e:
        st.error(str(e)); st.stop()
    except Exception as e:
        st.error(f"Fatal Error: {e}"); st.stop()
