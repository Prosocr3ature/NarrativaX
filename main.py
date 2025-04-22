import streamlit as st
import os
import replicate
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from io import BytesIO
from PIL import Image

# Set up page configuration for fullscreen view and hide sidebar menu
st.set_page_config(page_title="AI Companion", page_icon="🌟", layout="wide", initial_sidebar_state="collapsed")
hide_streamlit_style = """<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;}</style>"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# Check for Replicate API token
if "REPLICATE_API_TOKEN" not in os.environ:
    st.error("Missing Replicate API token. Please set the REPLICATE_API_TOKEN environment variable.")
    st.stop()

# Load MythoMax LLM (13B) model and tokenizer
@st.cache_resource
def load_llm():
    tokenizer = AutoTokenizer.from_pretrained("Gryphe/MythoMax-L2-13b", use_fast=False)
    model = AutoModelForCausalLM.from_pretrained(
        "Gryphe/MythoMax-L2-13b", 
        device_map="auto", 
        load_in_8bit=True,   # 8-bit quantization for efficiency
        torch_dtype=torch.float16
    )
    return tokenizer, model

tokenizer, model = load_llm()

# Define companion profiles with persona and appearance
companions_data = {
    "Luna": {
        "persona": "a flirty and playful girlfriend who teases affectionately.",
        "appearance": "a 22-year-old woman with long brown hair and a mischievous smile"
    },
    "Reina": {
        "persona": "a confident, dominant partner who likes to take control.",
        "appearance": "a 30-year-old woman with black hair and piercing eyes, often wearing leather."
    },
    "Lily": {
        "persona": "a shy, submissive partner who is eager to please.",
        "appearance": "a 19-year-old woman with short blonde hair and a bashful smile"
    }
}

# Initialize session state for chat logs if not already
if 'chat_logs' not in st.session_state:
    st.session_state['chat_logs'] = {}

# Create two tabs: Chat and Sex Scene Generator
tab_chat, tab_scene = st.tabs(["Chat", "Sex Scene Generator"])

with tab_chat:
    st.header("💬 Live Companion Chat")
    # Select one or multiple companions to chat with
    selected_names = st.multiselect(
        "Choose your companion(s):", 
        options=list(companions_data.keys()), 
        default=[list(companions_data.keys())[0]]
    )
    if len(selected_names) == 0:
        st.warning("Please select at least one companion to begin chatting.")
    else:
        # Determine session key for this conversation (single or group)
        conv_key = ", ".join(sorted(selected_names))
        if conv_key not in st.session_state['chat_logs']:
            st.session_state['chat_logs'][conv_key] = []  # initialize empty chat history for this combination
        
        # Display existing conversation from session state
        for msg in st.session_state['chat_logs'][conv_key]:
            if msg['speaker'] == 'User':
                with st.chat_message("user"):
                    st.markdown(msg['text'])
            else:
                # Assistant (companion) message
                with st.chat_message("assistant"):
                    img = Image.open(BytesIO(msg['image_bytes']))
                    st.image(img, caption=msg['speaker'])
                    st.markdown(msg['text'])
        
        # Controls for mood, intensity, gesture
        col1, col2, col3 = st.columns([1,1,1])
        with col1:
            mood = st.selectbox("Mood:", ["Flirty", "Submissive", "Dominant"], index=0)
        with col2:
            intensity = st.slider("Intensity (NSFW):", 1, 5, value=3)
        with col3:
            gesture = st.selectbox("Motion/Gesture:", ["Winking", "Touching chest", "Straddling"], index=0)
        
        # Chat input box (for user message)
        user_input = st.chat_input("Type a message and press Enter...")
        if user_input:
            # Append user message to session history and display it
            st.session_state['chat_logs'][conv_key].append({"speaker": "User", "text": user_input})
            with st.chat_message("user"):
                st.markdown(user_input)
            
            # Prepare conversation history for LLM prompt
            history_text = "".join([f"{entry['speaker']}: {entry['text']}\n" for entry in st.session_state['chat_logs'][conv_key]])
            
            # Generate a response for each selected companion
            for name in selected_names:
                persona = companions_data[name]['persona']
                appearance = companions_data[name]['appearance']
                # Construct the LLM prompt using Alpaca-style format
                instruction = (
                    f"{name} is {persona} Appearance: {appearance} "
                    f"{name} currently feels {mood.lower()} and responds in a {mood.lower()} manner. "
                    f"The reply should have intensity {intensity} (1=mild,5=explicit) and subtly include the gesture '{gesture.lower()}'. "
                    f"Given the conversation so far, write {name}'s next reply."
                )
                prompt = f"### Instruction:\n{instruction}\n### Input:\n{history_text}\n### Response:"
                
                # Generate text reply with the LLM
                with st.spinner(f"{name} is replying..."):
                    inputs = tokenizer(prompt, return_tensors='pt')
                    inputs = inputs.to(model.device)
                    output_ids = model.generate(
                        **inputs, max_new_tokens=200, do_sample=True, 
                        temperature=0.8, top_p=0.95
                    )
                    reply_text = tokenizer.decode(
                        output_ids[0][inputs['input_ids'].shape[1]:], 
                        skip_special_tokens=True
                    )
                reply_text = reply_text.strip()
                if reply_text.startswith(name + ':'):
                    reply_text = reply_text[len(name)+1:].strip()
                
                # Create an image prompt combining appearance, gesture, mood, and intensity cues
                style = "highly explicit" if intensity >= 5 else ("erotic" if intensity >= 4 else ("sensual" if intensity >= 3 else "attractive"))
                img_prompt = f"{appearance}, {gesture.lower()}, {mood.lower()} expression, {style}"
                if intensity <= 2:
                    img_prompt += ", fully clothed"
                else:
                    img_prompt += ", nude" if intensity >= 4 else ", lingerie"
                img_prompt += ", photo real, extremely detailed"
                negative_prompt = "bad quality, blurry, deformed, extra limbs, disfigured"
                
                # Generate companion image via Replicate [oai_citation_attribution:1‡replicate.com](https://replicate.com/docs/get-started/python#:~:text=output%20%3D%20replicate.run%28%20%22black,2%7D)
                with st.spinner(f"Generating {name}'s image..."):
                    output = replicate.run(
                        "asiryan/reliberate-v3", 
                        input={"prompt": img_prompt, "negative_prompt": negative_prompt, "num_outputs": 1}
                    )
                    image_bytes = output[0].read()
                
                # Display the assistant's response (image + text)
                with st.chat_message("assistant"):
                    st.image(Image.open(BytesIO(image_bytes)), caption=name)
                    st.markdown(reply_text)
                
                # Save companion's response in chat history
                st.session_state['chat_logs'][conv_key].append({
                    "speaker": name,
                    "text": reply_text,
                    "image_bytes": image_bytes
                })

with tab_scene:
    st.header("📖 Sex Scene Generator")
    st.write("Enter a scene description and generate a vivid erotic story with images.")
    scene_seed = st.text_area("Scene description:", placeholder="A romantic evening by the fireplace...")
    scene_intensity = st.slider("Scene Intensity (NSFW):", 1, 5, value=5, key="scene_intensity")
    image_count = st.slider("Images to generate:", 1, 3, value=1, key="scene_img_count")
    if st.button("Generate Scene"):
        if scene_seed.strip() == "":
            st.error("Please enter a description for the scene.")
        else:
            # Generate scene text using the LLM
            instruction = (
                f"Write a detailed erotic scene based on the following description. "
                f"The scene's content has intensity {scene_intensity} (1=mild,5=explicit). "
                f"Description: {scene_seed}"
            )
            prompt = f"### Instruction:\n{instruction}\n### Response:"
            with st.spinner("Writing the scene..."):
                inputs = tokenizer(prompt, return_tensors='pt')
                inputs = inputs.to(model.device)
                output_ids = model.generate(
                    **inputs, max_new_tokens=500, do_sample=True, 
                    temperature=0.7, top_p=0.9
                )
                scene_text = tokenizer.decode(
                    output_ids[0][inputs['input_ids'].shape[1]:], 
                    skip_special_tokens=True
                )
            st.markdown(scene_text)
            # Generate images for the scene
            img_prompt_scene = scene_seed
            if scene_intensity >= 5:
                img_prompt_scene += ", extremely explicit"
            elif scene_intensity >= 3:
                img_prompt_scene += ", erotic"
            else:
                img_prompt_scene += ", romantic"
            img_prompt_scene += ", photo real, detailed"
            negative_prompt = "bad quality, blurry, deformed, extra limbs, disfigured"
            with st.spinner("Generating images..."):
                output = replicate.run(
                    "asiryan/reliberate-v3", 
                    input={"prompt": img_prompt_scene, "negative_prompt": negative_prompt, "num_outputs": image_count}
                )
                images = [Image.open(BytesIO(file.read())) for file in output]
            for img in images:
                st.image(img)
