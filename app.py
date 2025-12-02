# debug safe app.py, paste exactly, commit, then manual sync
from flask import Flask, request, jsonify
import google.generativeai as genai
import os, traceback

app = Flask(__name__)

# choose key from env, fallback
key = os.getenv("GEMINI_KEY") or os.getenv("GOOGLE_API_KEY")
if not key:
    raise RuntimeError("no api key found, set GOOGLE_API_KEY or GEMINI_KEY in environment")
genai.configure(api_key=key)

@app.route("/")
def home():
    return "bot online"

@app.route("/models")
def models():
    try:
        # list models available to your key
        models = genai.list_models()  # generator or list depending on sdk version
        out = []
        for m in models:
            # try common attributes safely
            try:
                name = getattr(m, "name", None) or getattr(m, "model_id", None) or str(m)
            except Exception:
                name = str(m)
            out.append(name)
        return jsonify({"ok": True, "models": out})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()}), 500

@app.route("/ask")
def ask():
    q = request.args.get("q", "")
    if not q:
        return jsonify({"ok": False, "error": "no query provided, use ?q=your+question"}), 400

    # model selection order
    model_from_query = request.args.get("model")
    model_from_env = os.getenv("MODEL_NAME")
    model = model_from_query or model_from_env
    if not model:
        return jsonify({
            "ok": False,
            "error": "no model specified, call /models to see available models, then call /ask?q=...&model=<model_id>"
        }), 400

    try:
        # create model object and call generate_content
        gen_model = genai.GenerativeModel(model)
        resp = gen_model.generate_content(q)
        # try to extract text safely
        text = None
        if hasattr(resp, "text"):
            text = resp.text
        elif isinstance(resp, dict) and "candidates" in resp:
            text = resp["candidates"][0].get("content", "")
        else:
            text = str(resp)
        return jsonify({"ok": True, "model_used": model, "response": text})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
            
