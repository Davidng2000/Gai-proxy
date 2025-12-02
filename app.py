from flask import Flask, request, jsonify
import google.generativeai as genai
import os, traceback

app = Flask(__name__)

# configure from environment
genai.configure(api_key=os.getenv("GEMINI_KEY"))

@app.route("/")
def home():
    return "bot online"

@app.route("/ask")
def ask():
    q = request.args.get("q", "")
    if not q:
        return jsonify({"ok": False, "error": "no query provided, use ?q=your+question"}), 400
    try:
        # use the same free model you chose
        model = genai.GenerativeModel("gemini-1.5-flash")
        resp = model.generate_content(q)
        # try common response shapes
        text = None
        if hasattr(resp, "text"):
            text = resp.text
        elif isinstance(resp, dict) and "candidates" in resp:
            # fallback for some sdk shapes
            text = resp["candidates"][0].get("content", "")
        else:
            text = str(resp)
        return jsonify({"ok": True, "query": q, "response": text})
    except Exception as e:
        tb = traceback.format_exc()
        # return the error in json so you can see it in browser
        return jsonify({"ok": False, "error": str(e), "trace": tb}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
        
