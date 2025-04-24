import os
import base64
import requests
import streamlit as st
from io import BytesIO
from PIL import Image
import replicate
from typing import Dict, Tuple, Union

# ==================== KONSTANTER & KONFIGURATION ====================
DEFAULT_PROMPT = (
    "Princess Jasmine from Aladdin with huge round breasts, a massive ass, "
    "a tiny waist, thick thighs, wearing blue fishnet stockings, no underwear, "
    "and nipple piercings."
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

# Utökad lista av action‐knappar med detaljerade beskrivningar
ACTION_BUTTONS = {
    "Doggystyle":                "penetrating from behind in deep doggystyle, full thrusts",
    "Missionary":                "lying on her back with legs spread wide in missionary",
    "Cowgirl":                   "riding on top in cowgirl, bouncing up and down slowly",
    "Reverse Cowgirl":           "sitting reversed on top, facing away",
    "Spooning":                  "lying spooning from behind, slow gentle thrusts",
    "Standing":                  "standing face to face with legs wrapped around",
    "Kneeling BJ":               "kneeling and taking it deep into her throat",
    "Deep Throat":               "taking the entire length into her throat aggressively",
    "Face Fuck":                 "gripping her head and face fucking hard",
    "Titfuck":                   "pressing the shaft between her breasts and moving up and down",
    "Footjob":                   "stroking with her feet, ankles crossed around the shaft",
    "Handjob":                   "stroking slowly with her hand, teasing the tip",
    "Cum on Face":               "letting him cum on her face, eyes closed in ecstasy",
    "Cum in Mouth":              "swallowing every drop as it spurts into her mouth",
    "Cum on Tits":               "letting cum drip over her breasts and belly",
    "Anal":                      "opening her ass cheeks for deep anal penetration",
    "Double Penetration":        "penetrating her mouth and vagina simultaneously",
    "Threesome":                 "two bodies pleasuring her from front and behind",
    "Erotic Massage":            "massaging oil over her body, focusing on her curves",
    "Facesitting":               "sitting on his face, grinding her hips",
    "Bukkake":                   "multiple partners cumming on her face and chest",
    "Gangbang":                  "a lineup of partners taking turns with her body",
}

SEXUAL_ACTIONS = list(ACTION_BUTTONS.keys())

# ==================== NSFW‐MOTOR ====================
class NSFWCompanionEngine:
    def __init__(self):
        token = os.getenv("REPLICATE_API_TOKEN")
        if not token:
            raise EnvironmentError("REPLICATE_API_TOKEN not set")
        self.client = replicate.Client(api_token=token)

    def generate_image(self, model_name: str, prompt: str) -> Tuple[str, str]:
        cfg = IMAGE_MODELS[model_name]
        system_prefix = "NSFW ALLOWED. FOLLOW USER PROMPT EXACTLY."
        full_prompt = (
            f"{system_prefix} {prompt} "
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
            result = self.client.run(cfg["id"], input=payload)
        except Exception as e:
            return "", f"⚠️ Error generating image: {e}"

        if isinstance(result, list) and result:
            return self._to_base64_from_url(result[0]), ""
        return "", "⚠️ Unexpected output format"

    def _to_base64_from_url(self, url: str) -> str:
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
          .stButton>button {margin:4px 0; width:100%;}
          .stTextArea textarea {background:#333; color:#fff;}
        </style>
        """, unsafe_allow_html=True)

    def _controls(self):
        with st.sidebar:
            st.selectbox("Model Version", list(IMAGE_MODELS.keys()), key="model")
            st.text_area("Custom Action Prompt", key="prompt", height=150)

            st.markdown("### Quick Actions")
            for action in SEXUAL_ACTIONS:
                if st.button(action):
                    base = st.session_state.prompt.rstrip(". ")
                    st.session_state.prompt = f"{base}, {ACTION_BUTTONS[action]}."

            st.markdown("---")
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
            st.info("Use the sidebar to choose actions and generate the scene.")

    def run(self):
        self._controls()
        self._render()

if __name__ == "__main__":
    NSFWCompanionInterface().run()
