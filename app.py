from flask import Flask, request, jsonify
import os
import replicate
from gtts import gTTS
from io import BytesIO
import json

app = Flask(__name__)

# Setup Replicate API client
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
replicate_client = replicate.Client(api_token=REPLICATE_API_TOKEN)

# Route to generate text using a specified model
@app.route("/generate", methods=["POST"])
def generate_text():
    data = request.get_json()
    prompt = data.get("prompt", "")
    model_name = data.get("model", "nothingiisreal/mn-celeste-12b")

    try:
        # Send prompt to OpenRouter or other model API (replace this as needed)
        response = replicate_client.run(model_name, input={"prompt": prompt})
        return jsonify({"generated_text": response[0]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Route to generate images based on prompt
@app.route("/generate_image", methods=["POST"])
def generate_image():
    data = request.get_json()
    prompt = data.get("prompt", "")

    try:
        image_url = replicate_client.run("lucataco/realistic-vision-v5.1:latest", input={"prompt": prompt})
        return jsonify({"image_url": image_url[0]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Route to generate audio using gTTS (Google Text-to-Speech)
@app.route("/generate_audio", methods=["POST"])
def generate_audio():
    data = request.get_json()
    text = data.get("text", "")

    try:
        tts = gTTS(text)
        audio_fp = BytesIO()
        tts.save(audio_fp)
        audio_fp.seek(0)
        return jsonify({"audio_url": audio_fp.getvalue()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
