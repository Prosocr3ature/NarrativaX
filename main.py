import os
import base64
import requests
import streamlit as st
from io import BytesIO
from PIL import Image
import replicate
from typing import Dict, List, Tuple, Optional, Union

# ==================== CONSTANTS & CONFIGURATION ====================
DEFAULT_MODEL = "mikeei/dolphin-2.9-llama3-70b-gguf:7cd1882cb3ea90756d09decf4bc8a259353354703f8f385ce588b71f7946f0aa"

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
        "requires_image": False,
        "output_type": "url"
    },
    "Hardcore Edition": {
        "id": "asiryan/reliberate-v3:d70438fcb9bb7adb8d6e59cf236f754be0b77625e984b8595d1af02cdf034b29",
        "width": 768,
        "height": 1152,
        "guidance": 8.5,
        "requires_image": False,
        "output_type": "url"
    },
    "Porn Diffusion": {
        "id": "delta-lock/ponynai3:ea38949bfddea2db315b598620110edfa76ddaf6313a18e6cbc6a98f496a34e9",
        "width": 768,
        "height": 1152,
        "guidance": 10.0,
        "requires_image": False,
        "output_type": "url"
    },
    "Pornographic": {
        "id": "tencentarc/photomaker:ddfc2b08d209f9fa8c1eca692712918bd449f695dabb4a958da31802a9570fe4",
        "width": 1024,
        "height": 1536,
        "guidance": 10.0,          # clamp to model max
        "requires_image": True,
        "output_type": "url"
    },
    "Flux 1.1 Pro": {
        "id": "black-forest-labs/flux-1.1-pro",
        "requires_image": False,
        "output_type": "binary"
    }
}

# ==================== CORE FUNCTIONALITY ====================
class NSFWCompanionEngine:
    def __init__(self):
        token = os.getenv("REPLICATE_API_TOKEN")
        if not token:
            raise EnvironmentError("REPLICATE_API_TOKEN not set")
        self.client = replicate.Client(api_token=token)

    def generate_image(
        self,
        prompt: str,
        model_name: str,
        appearance: str,
        actions: List[str],
        input_image: Optional[BytesIO] = None
    ) -> Tuple[str, str]:
        cfg = IMAGE_MODELS[model_name]
        model_id = cfg["id"]

        # require base image if needed
        if cfg.get("requires_image") and input_image is None:
            return "", "⚠️ Error: This model requires a base image. Please upload one."

        # unified explicit prompt
        full_prompt = (
            f"ULTRA-EXPLICIT, UNCENSORED, {', '.join(actions)}, "
            f"{appearance}, {prompt}, 8k RAW photo, intricate details, "
            "perfect anatomy, vaginal penetration, explicit nudity, "
            "highly detailed skin texture"
        )

        # build payload
        if cfg["output_type"] == "binary":
            # Flux 1.1 Pro now driven by our full_prompt, NSFW allowed
            payload = {
                "prompt": full_prompt,
                "prompt_upsampling": True,
                "safety_checker": False
            }
        else:
            guidance = min(cfg["guidance"], 10.0)
            payload = {
                "prompt": full_prompt,
                "width": cfg["width"],
                "height": cfg["height"],
                "num_inference_steps": 45,
                "guidance_scale": guidance,
                "negative_prompt": "censored, blurry, cartoon, text, watermark, clothes",
                "safety_checker": False
            }
            if cfg.get("requires_image"):
                payload["input_image"] = input_image

        try:
            result = self.client.run(model_id, input=payload)
        except Exception as e:
            return "", f"⚠️ Error generating image: {e}"

        # handle binary vs URL outputs
        if cfg["output_type"] == "binary":
            if hasattr(result, "read"):
                img_bytes = result.read()
            elif isinstance(result, (bytes, bytearray)):
                img_bytes = result
            else:
                return "", "⚠️ Error: Unexpected binary output format"
            return self._to_base64(img_bytes), ""
        else:
            if isinstance(result, list) and result:
                return self._fetch_and_encode(result[0]), ""
            return "", "⚠️ Error: Unexpected URL output format"

    def _fetch_and_encode(self, url: str) -> str:
        resp = requests.get(url, timeout=25)
        resp.raise_for_status()
        return self._to_base64(resp.content)

    def _to_base64(self, img_bytes: Union[bytes, bytearray]) -> str:
        img = Image.open(BytesIO(img_bytes)).convert("RGB")
        img = img.resize((1024, 1536), Image.Resampling.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="WEBP", quality=100)
        return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()


# ==================== USER INTERFACE ====================
class NSFWCompanionInterface:
    def __init__(self):
        self.engine = NSFWCompanionEngine()
        self._init_state()
        self._configure_page()

    def _init_state(self):
        defaults = {
            "appearance": "Princess Jasmine from Alladin, huge round tits, massive ass, tiny waist, thick thighs, blue fishnet stockings, no underwear, nipple piercings",
            "positions": [],
            "oral": [],
            "custom_actions": "",
            "current_image": "",
            "processing": False,
            "model": "Unrestricted XL",
            "input_image_upload": None
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
            st.text_area("Physical Description", key="appearance", height=200,
                         value=st.session_state.appearance)
            st.selectbox("Model Version", list(IMAGE_MODELS.keys()), key="model")

            cfg = IMAGE_MODELS[st.session_state.model]
            if cfg.get("requires_image"):
                up = st.file_uploader("Upload Base Image",
                                      type=["png", "jpg", "jpeg"],
                                      key="input_image_upload")
                if up:
                    st.session_state.input_image_upload = BytesIO(up.read())

    def _generate(self):
        st.session_state.processing = True
        actions = [
            *st.session_state.positions,
            *st.session_state.oral,
            st.session_state.custom_actions
        ]
        with st.spinner("Generating content…"):
            img_b64, err = self.engine.generate_image(
                prompt=", ".join(actions),
                model_name=st.session_state.model,
                appearance=st.session_state.appearance,
                actions=actions,
                input_image=st.session_state.input_image_upload
            )
        st.session_state.processing = False

        if err:
            st.error(err)
        else:
            st.session_state.current_image = img_b64
            st.experimental_rerun()

    def _render_display(self):
        c1, c2 = st.columns([1, 2])
        with c1:
            st.markdown("## Live Preview")
            if st.session_state.current_image:
                st.image(st.session_state.current_image, use_column_width=True)
            else:
                st.info("Configure settings and generate content")
        with c2:
            with st.expander("📝 SCENE DESIGNER", expanded=True):
                st.write("Combine positions & actions for complex scenes")
                if st.button("💦 NEW VARIATION"):
                    self._generate()

    def run(self):
        self._action_controls()
        self._appearance_controls()
        self._render_display()


# ==================== APPLICATION ENTRYPOINT ====================
if __name__ == "__main__":
    try:
        NSFWCompanionInterface().run()
    except EnvironmentError as e:
        st.error(str(e)); st.stop()
    except Exception as e:
        st.error(f"Fatal Error: {e}"); st.stop()
