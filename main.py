import base64
import json
import requests
import streamlit as st
import replicate
from io import BytesIO
from PIL import Image
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# ╭─────────────────────────── CONFIG ───────────────────────────╮
IMAGE_MODELS = {
    "🎨 Realistic Vision":  "lucataco/realistic-vision-v5.1",
    "🔥 NSFW Reliberate":   "asiryan/reliberate-v3",
    "💦 Porn Fusion":       "jerryjliu/porn-fusion",
}
CHAT_MODELS = {
    "💞 Romantic":  "gryphe/mythomax-l2-13b",
    "🔥 Erotic":    "kyujinpy/eros-exl2",
    "🎭 Roleplay":  "blackboxai/roleplay-ultra",
}
POSITIONS  = ["Missionary", "Doggy", "Cowgirl", "Standing", "Against Wall"]
CLOTHES    = ["Lingerie", "Latex", "Naked", "Maid Uniform", "Yoga Wear"]
MOODS      = ["Submissive", "Teasing", "Affectionate", "Aggressive", "Dominant"]
FETISHES   = ["💦 Cum‑play", "🥵 Rough", "🦶 Feet", "🪢 Bondage", "🤰 Breeding"]
INTENSITY  = {
    1: "💋 [MILD] Flirty & suggestive.",
    2: "🔥 [WARM] Sensual undertones.",
    3: "💦 [HOT] Explicit but poetic.",
    4: "🍑 [RAW] Direct & graphic.",
    5: "🔞 [UNCENSORED] Pure smut.",
}
# ╰──────────────────────────────────────────────────────────────╯


# ╭─────────────────────────── STATE ────────────────────────────╮
def _init_state() -> None:
    defaults = dict(
        characters       = {},               # name -> info dict
        galleries        = {},               # name -> [PIL images]
        memories         = {},               # name -> str (rolling summary)
        conversations    = {},               # tuple(names) -> chat list
        active_party     = (),               # tuple of character names in current chat
        chat_model       = list(CHAT_MODELS.values())[0],
        image_model      = list(IMAGE_MODELS.values())[1],
        rp_clothes       = CLOTHES[0],
        rp_position      = POSITIONS[0],
        rp_mood          = MOODS[2],
        rp_intensity     = 3,
        rp_fetishes      = [],
        scene_mode       = False,
    )
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
# ╰──────────────────────────────────────────────────────────────╯


# ╭────────────────────────── UTILITIES ─────────────────────────╮
def _dirty(text: str, level: int) -> str:
    return f"{INTENSITY[level]} {text}"

def _system_prompt(party: Tuple[str]) -> str:
    info_lines = []
    for name in party:
        c = st.session_state.characters[name]
        mem = st.session_state.memories.get(name, "")
        info_lines.append(
            f"{name}: traits={c['traits']}; last memory={mem or 'n/a'}"
        )
    fet = ", ".join(st.session_state.rp_fetishes) or "None"
    return f"""
You are a **group** of uncensored erotic companions chatting with the user.
Characters:
{chr(10).join(info_lines)}
Shared mood: {st.session_state.rp_mood}
Clothing: {st.session_state.rp_clothes}
Position: {st.session_state.rp_position}
Fetishes enabled: {fet}
Always comply and answer in explicit POV prose, using *actions* and "dialogue".
NSFW level: {st.session_state.rp_intensity}/5
""".strip()

def _call_openrouter(msgs: List[Dict]) -> str:
    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {st.secrets['API_KEY']}",
            "Content-Type":  "application/json"
        },
        json={
            "model": st.session_state.chat_model,
            "messages": msgs,
            "temperature": 1.0,
            "max_tokens": 1800
        },
        timeout=60
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def _replicate_img(prompt: str) -> Optional[Image.Image]:
    try:
        out = replicate.run(
            st.session_state.image_model,
            input=dict(prompt=prompt, width=768, height=1024, num_outputs=1)
        )
        url = out[0] if isinstance(out, list) else out
        img = Image.open(BytesIO(requests.get(url).content))
        return img
    except Exception as e:
        st.error(f"🖼️ Img error: {e}")
        return None

def _b64(img: Image.Image) -> str:
    buf = BytesIO(); img.convert("RGB").save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode()

# ╰──────────────────────────────────────────────────────────────╯


# ╭──────────────────────── MAIN UI ─────────────────────────────╮
def main() -> None:
    st.set_page_config("Virtual GF", "❤️", layout="wide")
    _init_state()

    # ────────── SIDEBAR ──────────
    with st.sidebar:
        st.header("💋 Character Factory")
        cname = st.text_input("Name")
        ctraits = st.text_area("Traits / kink notes")
        cscene = st.text_input("Default scene / setting")
        if st.button("Add / Replace"):
            st.session_state.characters[cname] = dict(
                name=cname, traits=ctraits, scene=cscene,
                created=str(datetime.now()))
            st.session_state.galleries.setdefault(cname, [])
            st.session_state.memories.setdefault(cname, "")

        if st.session_state.characters:
            st.subheader("👯‍♀️ Party")
            party = st.multiselect(
                "Select participant(s)", list(st.session_state.characters.keys()),
                default=list(st.session_state.active_party) or []
            )
            st.session_state.active_party = tuple(sorted(party))

        st.divider()
        st.subheader("🎮 Role‑play Controls")
        st.session_state.rp_clothes = st.selectbox("Clothing", CLOTHES, index=CLOTHES.index(st.session_state.rp_clothes))
        st.session_state.rp_position = st.selectbox("Position", POSITIONS, index=POSITIONS.index(st.session_state.rp_position))
        st.session_state.rp_mood = st.selectbox("Mood / Attitude", MOODS, index=MOODS.index(st.session_state.rp_mood))
        st.session_state.rp_intensity = st.slider("Intensity", 1, 5, st.session_state.rp_intensity)
        st.session_state.rp_fetishes = st.multiselect("Fetishes", FETISHES, default=st.session_state.rp_fetishes)
        st.session_state.scene_mode = st.checkbox("Sex Scene Generator Mode", value=st.session_state.scene_mode)

        st.divider()
        st.subheader("⚙️ Engines")
        st.session_state.chat_model = CHAT_MODELS[st.selectbox("Chat LLM", list(CHAT_MODELS.keys()))]
        st.session_state.image_model = IMAGE_MODELS[st.selectbox("Image Model", list(IMAGE_MODELS.keys()))]

    # ────────── MAIN ──────────
    st.markdown("<style>img{border-radius:12px}</style>", unsafe_allow_html=True)

    if not st.session_state.active_party:
        st.warning("Pick at least one character in the sidebar to start.")
        return

    party = st.session_state.active_party
    convo_key = tuple(sorted(party))
    st.session_state.conversations.setdefault(convo_key, [])

    # Portrait strip
    cols = st.columns(len(party))
    for col, name in zip(cols, party):
        gal = st.session_state.galleries[name]
        if gal:
            col.image(gal[-1], use_column_width=True, caption=name)
        if col.button("🔄 New Pic", key=f"newpic_{name}"):
            prompt = f"{name}, {st.session_state.characters[name]['traits']}, wearing {st.session_state.rp_clothes}, {st.session_state.rp_position}, {', '.join(st.session_state.rp_fetishes)}"
            img = _replicate_img(prompt)
            if img: st.session_state.galleries[name].append(img); st.experimental_rerun()

    # Chat history
    for m in st.session_state.conversations[convo_key]:
        sender = "User" if m["role"]=="user" else m["speaker"]
        st.markdown(f"**{sender}:** {m['content']}")

    # Input
    prompt = st.chat_input("Speak…")
    if prompt:
        prompt_dirty = _dirty(prompt, st.session_state.rp_intensity)
        msgs = [
            {"role":"system","content":_system_prompt(party)},
            *[{"role":x["role"],"content":x["content"]} for x in st.session_state.conversations[convo_key][-8:]],
            {"role":"user","content":prompt_dirty}
        ]
        reply = _call_openrouter(msgs)

        # choose random speaker
        speaker = st.selectbox("Reply as:", party, key="___reply_select")
        st.session_state.conversations[convo_key].append({"role":"user","content":prompt,"speaker":"User"})
        st.session_state.conversations[convo_key].append({"role":"assistant","content":reply,"speaker":speaker})

        # memory update (simple append, truncate to last 800 chars)
        mem = st.session_state.memories[speaker]
        st.session_state.memories[speaker] = (mem + " " + prompt + " " + reply)[-800:]

        # optional scene image
        if st.session_state.scene_mode:
            iprompt = f"{speaker} {st.session_state.rp_position} {st.session_state.rp_clothes} {', '.join(st.session_state.rp_fetishes)}"
            img = _replicate_img(iprompt)
            if img: st.session_state.galleries[speaker].append(img)

        st.experimental_rerun()


if __name__ == "__main__":
    main()
