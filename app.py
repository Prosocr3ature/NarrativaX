from flask import Flask, send_from_directory

app = Flask(__name__, static_folder='public', static_url_path='/public')

@app.route('/')
def index():
    return send_from_directory('public', 'index.html')

@app.route('/manifest.json')
def manifest():
    return send_from_directory('public', 'manifest.json')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('public', path)
