from flask import Flask, request, jsonify
import json
import os
from gtts import gTTS
import replicate

app = Flask(__name__)

# API-nycklar
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
replicate_client = replicate.Client(api_token=REPLICATE_API_TOKEN)

# --- Helper functions to interact with AI Models ---
def call_openrouter(prompt, model, max_tokens=1800):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://narrativax.app",
        "X-Title": "NarrativaX"
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.95,
        "max_tokens": max_tokens
    }
    r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


# --- Generate book outline ---
def generate_outline(prompt, genre, tone, chapters, model):
    return call_openrouter(f"You are a ghostwriter. Create an outline for a {tone} {genre} novel with {chapters} chapters. Include: Title, Foreword, Introduction, Chapters, Final Words. Concept:\\n{prompt}", model)


# --- Generate Section ---
def generate_section(title, outline, model):
    return call_openrouter(f"Write the full content for section '{title}' using this outline:\\n{outline}", model)


# --- Generate Characters ---
def generate_characters(outline, genre, tone, model):
    prompt = f"""Create characters for a {tone} {genre} novel based on this outline.
    Return a JSON list like:
    [{{"name": "X", "role": "Y", "personality": "...", "appearance": "..."}}]
    Outline: {outline}"""
    try:
        return json.loads(call_openrouter(prompt, model))
    except:
        return [{"name": "Unnamed", "role": "Unknown", "personality": "N/A", "appearance": ""}]


# --- Generate Image ---
def generate_image(prompt, model_key, id_key):
    model = "lucataco/realistic-vision-v5.1:latest"  # Example image model; change as needed
    args = {"prompt": prompt[:300], "num_inference_steps": 30, "guidance_scale": 7.5, "width": 768, "height": 1024}
    image_url = replicate_client.run(model, input=args)[0]
    return image_url


# --- Generate Audio (TTS) ---
def narrate(text, id_key):
    filename = f"{id_key}.mp3"
    gTTS(text.replace("\n", " ")).save(filename)
    return filename


# --- Endpoints ---
@app.route("/generate_book", methods=["POST"])
def generate_book():
    data = request.get_json()
    try:
        # Getting book data from POST request
        book_prompt = data.get("prompt", "")
        genre = data.get("genre", "Adventure")
        tone = data.get("tone", "Romantic")
        chapters = data.get("chapters", 10)
        model = data.get("model", "nothingiisreal/mn-celeste-12b")

        # Generating outline and characters
        book_outline = generate_outline(book_prompt, genre, tone, chapters, model)
        characters = generate_characters(book_outline, genre, tone, model)

        # Return the generated book and characters
        response = {
            "outline": book_outline,
            "characters": characters
        }
        return jsonify(response), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/generate_portrait", methods=["POST"])
def generate_portrait():
    data = request.get_json()
    try:
        # Receiving character data from POST request
        character_name = data.get("name", "Unknown")
        character_appearance = data.get("appearance", "Unknown")

        # Generating character portrait (placeholder URL for now)
        portrait_url = generate_image(f"Portrait of {character_name} based on appearance: {character_appearance}", "Realistic Vision v5.1", character_name)

        return jsonify({"name": character_name, "portrait_url": portrait_url}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/", methods=["GET"])
def home():
    return "Welcome to NarrativaX API!", 200


# --- Start Flask app ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
