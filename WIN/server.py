import webbrowser
from threading import Thread

from flask import Flask
import requests
app = Flask(__name__)

@app.route("/")
def home():
    page = requests.get("https://github.com/")
    return page.text


if __name__ == "__main__":
    webbrowser.open("http://localhost:5002/")
    app.run(port=5002, debug=False)
    
