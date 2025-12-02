# app.py
from flask import Flask, request
import google.generativeai as genai
import os, traceback

app = Flask(__name__)

# pick key from env
key = os.getenv("GEMINI_KEY") or os.getenv("GOOGLE_API_KEY")
if not key:
    raise RuntimeError("no api key found, set GOOGLE_API_KEY or GEMINI_KEY in environment")

# default model, override by setting MODEL_NAME env var or passing &model= in query
DEFAULT_MODEL = os.getenv("MODEL_NAME") or "gemini-2.5-flash"

# configure sdk
genai.configure(api_key=key)

@app.route("/")
def home():
    return "bot online"

@app.route("/ask")
def ask():
    q = request.args.get("q", "")
    if not q:
        return "no query provided, use ?q=your+question", 400

    model_name = request.args.get("model") or DEFAULT_MODEL
    try:
        gen_model = genai.GenerativeModel(model_name)
        resp = gen_model.generate_content(q)

        # try to extract text safely
        if hasattr(resp, "text") and resp.text:
            text = resp.text
        elif isinstance(resp, dict) and "candidates" in resp and resp["candidates"]:
            text = resp["candidates"][0].get("content", "")
        else:
            text = str(resp)

        # return plain text so nightbot urlfetch works cleanly
        return text
    except Exception as e:
        tb = traceback.format_exc()
        # return short error for browser, but not full stack to public, print stack to logs
        print(tb)
        return f"error, check logs: {str(e)}", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
    
