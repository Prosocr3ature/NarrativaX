import os
import base64
import requests
import streamlit as st
from io import BytesIO
from PIL import Image
import replicate

# ==================== CONSTANTS & CONFIGURATION ====================
DEFAULT_MODEL = "mikeei/dolphin-2.9-llama3-70b-gguf:7cd1882cb3ea90756d09decf4bc8a259353354703f8f385ce588b71f7946f0aa"
NSFW_LEVELS = ["Mild", "Moderate", "Explicit", "Hardcore", "Unrestricted"]

FETISH_LIST = [
    "Feet", "Anal", "BDSM", "Latex", "Leather", "Public",
    "Cumshots", "Deepthroat", "Futanari", "Cuckold"
]

MOTION_PRESETS = [
    "Shaking hips", "Slow thrust", "Deep penetration",
    "Pulsating", "Grinding", "Wet & slippery"
]

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
    "Deliberate V6": {
        "id": "asiryan/deliberate-v6:605a9ad23d7580b2762173afa6009b1a0cc00b7475998600ba2c39eda05f533e",
        "width": 768, "height": 1152, "guidance": 9.0
    },
    "PonyNai3": {
        "id": "delta-lock/ponynai3:ea38949bfddea2db315b598620110edfa76ddaf6313a18e6cbc6a98f496a34e9",
        "width": 768, "height": 1152, "guidance": 10.0
    }
}

# ==================== COMPANION ENGINE ====================
class CompanionEngine:
    def __init__(self):
        self.client = replicate.Client(api_token=os.getenv("REPLICATE_API_TOKEN"))

    def generate_image(self, prompt: str, model: str) -> (str, str):
        cfg = IMAGE_MODELS[model]
        full_prompt = (
            f"{prompt}, uncensored, explicit, hyperrealistic, "
            "extremely detailed, 8k, photorealistic, cinematic lighting"
        )
        try:
            result = self.client.run(
                cfg["id"],
                input={
                    "prompt": full_prompt,
                    "width": cfg["width"],
                    "height": cfg["height"],
                    "num_inference_steps": 35,
                    "guidance_scale": cfg["guidance"],
                    "negative_prompt": (
                        "low quality, bad anatomy, cartoon, deformed, text, watermark"
                    )
                }
            )
            return self._to_webp_b64(result[0]), ""
        except Exception as e:
            return "", f"⚠️ Image Error: {e}"

    def generate_scene(self, prompt: str, model: str, length: int=5) -> (str, str):
        frames = []
        for i in range(length):
            img_b64, err = self.generate_image(f"{prompt}, frame {i+1}", model)
            if err:
                return "", err
            frames.append(self._b64_to_pil(img_b64))
        buf = BytesIO()
        frames[0].save(
            buf, format="GIF", save_all=True,
            append_images=frames[1:], duration=300, loop=0
        )
        gif_b64 = base64.b64encode(buf.getvalue()).decode()
        return f"data:image/gif;base64,{gif_b64}", ""

    def _to_webp_b64(self, url: str) -> str:
        resp = requests.get(url, timeout=30)
        img = Image.open(BytesIO(resp.content)).convert("RGB")
        img = img.resize((768,1024), Image.Resampling.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="WEBP", quality=95)
        return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()

    def _b64_to_pil(self, b64: str) -> Image.Image:
        header, data = b64.split(",", 1)
        raw = base64.b64decode(data)
        return Image.open(BytesIO(raw)).convert("RGB")

# ==================== STREAMLIT INTERFACE ====================
class CompanionInterface:
    def __init__(self):
        self.engine = CompanionEngine()
        self._init_state()
        self._config_page()

    def _init_state(self):
        defaults = {
            "appearance": "Princess Jasmine with big tits and big ass, olive skin...",
            "action_prompt": "sucking dick",
            "pose": "Doggy style",
            "fetishes": [],
            "motion_presets": [],
            "nsfw_level": "Unrestricted",
            "img_model": "Reliberate v3",
            "num_others": 0,
            "sequence_mode": False,
            "sequence_length": 5,
            "current_image": "",
            "current_scene": "",
        }
        for k,v in defaults.items():
            st.session_state.setdefault(k, v)

    def _config_page(self):
        st.set_page_config(
            page_title="AI Companion Pro",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        st.markdown("""
        <style>
           .sidebar .block-container { background: #1a1a1a; color: #fff; }
           .main { background: #000; color: #fff; }
        </style>
        """, unsafe_allow_html=True)

    def _controls(self):
        with st.sidebar:
            st.header("🎨 DESIGN YOUR COMPANION")
            st.text_area("Physical Description", key="appearance", height=100)
            st.text_area("Sexual Actions / Scenarios", key="action_prompt", height=80)
            st.selectbox(
                "Base Pose / Position",
                ["Doggy style","Missionary","Standing","Kneeling","Riding","Spitroast","Laying on back"],
                key="pose"
            )
            st.multiselect("Fetishes", FETISH_LIST, key="fetishes")
            st.multiselect("Motion Presets", MOTION_PRESETS, key="motion_presets")
            st.slider("Additional Partners", 0, 4, key="num_others")
            for i in range(st.session_state.num_others):
                st.text_input(f"Partner {i+1} Description", key=f"partner_{i}")
            st.checkbox("Generate Animated Scene", key="sequence_mode")
            if st.session_state.sequence_mode:
                st.slider("Sequence Length", 2, 10, key="sequence_length")
            col1, col2 = st.columns(2)
            with col1:
                st.selectbox("Image Model", list(IMAGE_MODELS.keys()), key="img_model")
            with col2:
                st.select_slider("NSFW Level", NSFW_LEVELS, key="nsfw_level")
            if st.button("🚀 GENERATE COMPANION", use_container_width=True):
                self._generate()

    def _generate(self):
        parts = [
            st.session_state.appearance,
            st.session_state.action_prompt,
            st.session_state.pose
        ]
        others = [
            st.session_state.get(f"partner_{i}", "")
            for i in range(st.session_state.num_others)
            if st.session_state.get(f"partner_{i}", "").strip()
        ]
        if others:
            parts.append("with " + ", ".join(others))
        if st.session_state.fetishes:
            parts.append("fetishes: " + ", ".join(st.session_state.fetishes))
        if st.session_state.motion_presets:
            parts.append("motion: " + ", ".join(st.session_state.motion_presets))
        parts.append("uncensored, explicit, hyperrealistic, 8k, photorealistic, cinematic lighting")
        merged = ", ".join(parts)

        if st.session_state.sequence_mode:
            data, err = self.engine.generate_scene(
                merged, st.session_state.img_model, st.session_state.sequence_length
            )
            if err:
                st.error(err)
                return
            st.session_state.current_scene = data
            st.session_state.current_image = ""
        else:
            data, err = self.engine.generate_image(
                merged, st.session_state.img_model
            )
            if err:
                st.error(err)
                return
            st.session_state.current_image = data
            st.session_state.current_scene = ""

    def _display(self):
        st.markdown("## Your Companion")
        if st.session_state.current_scene:
            st.markdown(
                f'<img src="{st.session_state.current_scene}" width="100%">',
                unsafe_allow_html=True
            )
        elif st.session_state.current_image:
            st.markdown(
                f'<img src="{st.session_state.current_image}" width="100%">',
                unsafe_allow_html=True
            )
        else:
            st.info("Configure your companion on the left and hit Generate.")

    def run(self):
        if not os.getenv("REPLICATE_API_TOKEN"):
            st.error("Missing REPLICATE_API_TOKEN")
            st.stop()
        self._controls()
        self._display()

if __name__ == "__main__":
    CompanionInterface().run()
