import os
import json
from flask import Flask, request, jsonify
import replicate
from gtts import gTTS
from io import BytesIO
from PIL import Image

# Create the Flask app
app = Flask(__name__)

# Replicate API key (Set in environment variables)
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
replicate_client = replicate.Client(api_token=REPLICATE_API_TOKEN)

# Initialize endpoints
@app.route("/generate", methods=["POST"])
def generate_text():
    data = request.get_json()
    prompt = data.get("prompt")
    
    # Call OpenRouter or similar model for text generation (mockup)
    output = "Generated text based on: " + prompt  # Replace this with real API call

    return jsonify({"generated_text": output})

@app.route("/generate_image", methods=["POST"])
def generate_image():
    data = request.get_json()
    prompt = data.get("prompt")
    
    # Example image generation using Replicate
    output = replicate_client.run("lucataco/realistic-vision-v5.1:2c8e954decbf70b7607a4414e5785ef9e4de4b8c51d50fb8b8b349160e0ef6bb", input={"prompt": prompt})
    
    return jsonify({"image_url": output[0]})

@app.route("/narrate", methods=["POST"])
def narrate():
    data = request.get_json()
    text = data.get("text")
    
    tts = gTTS(text)
    audio_stream = BytesIO()
    tts.save(audio_stream)
    audio_stream.seek(0)

    return jsonify({"audio": audio_stream.getvalue().decode("latin1")})  # Encode in base64 or similar

# Run the app
if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0')
