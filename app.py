from flask import Flask, request
import google.generativeai as genai
import os

app = Flask(__name__)

genai.configure(api_key=os.getenv("GEMINI_KEY"))

@app.route("/")
def home():
    return "bot online"

@app.route("/ask")
def ask():
    query = request.args.get("q", "")
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(query)
    return response.text

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
