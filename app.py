from flask import Flask, send_from_directory
import os

app = Flask(__name__, static_folder="public")

@app.route("/<path:path>")
def static_files(path):
    return send_from_directory("public", path)

@app.route("/")
def home():
    return "NarrativaX Flask Backend Running"
