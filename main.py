# main.py
import streamlit as st
import requests
import json
import time
from gtts import gTTS
from io import BytesIO
import uuid
from datetime import datetime

# ========== App Configuration ==========
st.set_page_config(
    page_title="Narrativax Pro",
    page_icon="🧙♂️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ========== Constants ==========
GENRES = {
    "Mainstream": ["Fantasy", "Sci-Fi", "Mystery", "Historical", "Adventure"],
    "Adult": ["Noir", "Psychological Thriller", "Dark Fantasy", "Dystopian", "Gothic"]
}

OPENROUTER_MODELS = {
    "Claude-3 Opus": "anthropic/claude-3-opus",
    "GPT-4 Turbo": "openai/gpt-4-turbo",
    "Llama3-70B": "meta-llama/llama-3-70b-instruct"
}

# ========== Session State Management ==========
def initialize_session():
    session_defaults = {
        "characters": [],
        "stories": [],
        "current_story": "",
        "adult_mode": False,
        "selected_model": "anthropic/claude-3-opus",
        "api_key": "",
        "editing_char": None,
        "character_versions": {}
    }
    
    for key, value in session_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

initialize_session()

# ========== AI Integration Core ==========
def openrouter_handler(prompt: str, system_prompt: str = "") -> str:
    """Handle OpenRouter API calls with full error handling"""
    if not st.session_state.api_key:
        st.error("🔑 Missing API Key! Add it in the sidebar.")
        return ""
    
    headers = {
        "Authorization": f"Bearer {st.session_state.api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": st.session_state.selected_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }
    
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=45
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except requests.exceptions.HTTPError as e:
        st.error(f"API Error: {e.response.text}")
    except Exception as e:
        st.error(f"Connection Error: {str(e)}")
    return ""

# ========== Intelligent Character System ==========
class CharacterEngine:
    @staticmethod
    def generate_character(role: str):
        """AI-powered character generation with version tracking"""
        system_prompt = """You are a professional character designer. Create complex characters with:
        - Unique personality traits
        - Detailed backstory
        - Internal conflicts
        - Visual description
        - Core motivation"""
        
        prompt = f"""Generate a {role} character in JSON format with these keys:
        name, age, description, personality, backstory, secret, motivation, visual_desc"""
        
        response = openrouter_handler(prompt, system_prompt)
        
        try:
            character = json.loads(response)
            character.update({
                "id": str(uuid.uuid4()),
                "role": role,
                "version": 1,
                "created_at": datetime.now().isoformat()
            })
            return character
        except:
            return CharacterEngine.create_default_character(role)

    @staticmethod
    def create_default_character(role: str):
        """Fallback character template"""
        return {
            "id": str(uuid.uuid4()),
            "name": "Unknown",
            "age": 30,
            "description": "Mysterious figure",
            "personality": "Complex",
            "backstory": "Unknown origins",
            "secret": "Hidden past",
            "motivation": "Seeking truth",
            "visual_desc": "Hooded cloak, piercing eyes",
            "role": role,
            "version": 1,
            "created_at": datetime.now().isoformat()
        }

# ========== Story Generation Engine ==========
class StoryForge:
    @staticmethod
    def craft_story(characters: list, genre: str, tone: str):
        """AI-driven story generation with dynamic parameters"""
        system_prompt = f"""You are an award-winning {genre} author. Write a story with:
        - Engaging opening hook
        - Character development arcs
        - Meaningful conflicts
        - Satisfying resolution
        - At least two plot twists
        Tone: {tone}"""
        
        character_card = "\n".join(
            [f"### {c['name']}\n"
             f"**Role**: {c['role'].title()}\n"
             f"**Motivation**: {c['motivation']}\n"
             f"**Secret**: {c['secret']}" 
             for c in characters]
        )
        
        prompt = f"""Write a 700-1000 word story featuring these characters:
        {character_card}
        
        Include:
        - Detailed setting descriptions
        - Character interactions
        - Dialogue sequences
        - Pacing variations"""
        
        return openrouter_handler(prompt, system_prompt)

# ========== UI Components ==========
def settings_panel():
    """Configuration sidebar"""
    with st.sidebar:
        st.header("⚙️ System Settings")
        
        # API Configuration
        st.session_state.api_key = st.text_input(
            "OpenRouter API Key",
            type="password",
            help="Get from https://openrouter.ai/keys"
        )
        
        # Model Selection
        st.session_state.selected_model = st.selectbox(
            "AI Model",
            options=list(OPENROUTER_MODELS.values()),
            format_func=lambda x: list(OPENROUTER_MODELS.keys())[
                list(OPENROUTER_MODELS.values()).index(x)
            ]
        )
        
        # Content Filters
        st.session_state.adult_mode = st.toggle(
            "Mature Content", 
            help="Enable adult themes and genres"
        )
        
        # System Controls
        if st.button("🧹 Full System Reset"):
            st.session_state.clear()
            initialize_session()
            st.rerun()

def character_workshop():
    """Character management interface"""
    st.header("👥 Character Workshop")
    
    # Creation Panel
    with st.expander("➕ Create New Character", expanded=True):
        col1, col2 = st.columns([1, 3])
        with col1:
            role = st.selectbox("Character Role", 
                              ["protagonist", "antagonist", "supporting"])
            if st.button("✨ Generate Character"):
                new_char = CharacterEngine.generate_character(role)
                st.session_state.characters.append(new_char)
                st.rerun()
        
        with col2:
            if st.session_state.characters:
                st.info(f"Total Characters: {len(st.session_state.characters)}")

    # Management Panel
    if st.session_state.characters:
        st.divider()
        selected_char = st.selectbox(
            "Select Character",
            options=[c["name"] for c in st.session_state.characters],
            index=0
        )
        
        char = next(c for c in st.session_state.characters 
                   if c["name"] == selected_char)
        
        # Character Controls
        cols = st.columns(4)
        with cols[0]:
            if st.button("🔄 Regenerate"):
                new_char = CharacterEngine.generate_character(char["role"])
                char.update(new_char)
                st.session_state.character_versions[char["id"]] = char["version"] + 1
                st.rerun()
        with cols[1]:
            if st.button("📝 Edit"):
                st.session_state.editing_char = char["id"]
        with cols[2]:
            if st.button("🗑️ Delete"):
                st.session_state.characters.remove(char)
                st.rerun()
        with cols[3]:
            st.metric("Version", char["version"])
        
        # Editing Interface
        if st.session_state.editing_char == char["id"]:
            edit_character(char)

def edit_character(char: dict):
    """Interactive character editor"""
    with st.form(f"edit_{char['id']}"):
        cols = st.columns(2)
        with cols[0]:
            char["name"] = st.text_input("Name", char["name"])
            char["age"] = st.number_input("Age", value=char["age"], min_value=1)
            char["role"] = st.selectbox("Role", ["protagonist", "antagonist", "supporting"])
        with cols[1]:
            char["description"] = st.text_area("Description", char["description"])
            char["motivation"] = st.text_input("Motivation", char["motivation"])
            char["secret"] = st.text_input("Secret", char["secret"])
        
        if st.form_submit_button("💾 Save Changes"):
            char["version"] += 1
            st.session_state.editing_char = None
            st.rerun()

def story_interface():
    """Main story generation interface"""
    st.header("📜 Story Forge")
    
    with st.form("story_config"):
        cols = st.columns(3)
        with cols[0]:
            genre_type = "Adult" if st.session_state.adult_mode else "Mainstream"
            genre = st.selectbox("Genre", GENRES[genre_type])
        with cols[1]:
            tone = st.select_slider("Narrative Tone", 
                                  ["Whimsical", "Neutral", "Dark", "Suspenseful"])
        with cols[2]:
            length = st.selectbox("Story Length", 
                                ["Short (500 words)", "Medium (1000 words)", "Long (2000 words)"])
        
        if st.form_submit_button("🔥 Generate Story"):
            if len(st.session_state.characters) < 1:
                st.error("Create at least 1 character first!")
            else:
                with st.spinner("🚀 Launching creative engines..."):
                    story = StoryForge.craft_story(
                        st.session_state.characters,
                        genre,
                        tone
                    )
                    st.session_state.current_story = story
                    st.session_state.stories.append({
                        "content": story,
                        "timestamp": datetime.now().isoformat(),
                        "characters": [c["id"] for c in st.session_state.characters]
                    })
    
    if st.session_state.current_story:
        st.divider()
        st.subheader("Generated Story")
        st.write(st.session_state.current_story)
        
        # Audio Conversion
        if st.button("🎧 Convert to Audiobook"):
            with st.spinner("Rendering audio..."):
                audio_file = BytesIO()
                tts = gTTS(st.session_state.current_story, lang="en")
                tts.write_to_fp(audio_file)
                st.audio(audio_file, format="audio/mp3")
        
        # Story History
        with st.expander("📚 Story Archive"):
            for idx, story in enumerate(st.session_state.stories):
                st.markdown(f"**Story #{idx+1}** - {story['timestamp']}")
                st.button(f"Load Story #{idx+1}", key=f"load_{idx}")

# ========== Main Application ==========
def main():
    settings_panel()
    character_workshop()
    story_interface()
    st.divider()
    st.markdown("🧠 Powered by [OpenRouter AI](https://openrouter.ai) | v3.1.0")

if __name__ == "__main__":
    main()
