# app.py
from flask import Flask, request
import google.generativeai as genai
import os, traceback, random, string, time, json

app = Flask(__name__)

# config
KEY = os.getenv("GEMINI_KEY") or os.getenv("GOOGLE_API_KEY")
if not KEY:
    raise RuntimeError("no api key found, set GOOGLE_API_KEY or GEMINI_KEY in environment")

DEFAULT_MODEL = os.getenv("MODEL_NAME") or "gemini-2.5-flash"
SESSION_TTL = int(os.getenv("SESSION_TTL_SECONDS") or 24*60*60)  # seconds

genai.configure(api_key=KEY)

# try redis
REDIS_URL = os.getenv("REDIS_URL")
redis_client = None
if REDIS_URL:
    try:
        import redis
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        redis_client.ping()
        print("redis connected")
    except Exception as e:
        print("redis connection failed, falling back to memory, err:", e)
        redis_client = None

# in-memory fallback
IN_MEMORY = {}

def mem_get(code):
    entry = IN_MEMORY.get(code)
    if not entry:
        return None
    if time.time() - entry.get("ts", 0) > SESSION_TTL:
        del IN_MEMORY[code]
        return None
    return entry

def mem_set(code, data):
    data["ts"] = time.time()
    IN_MEMORY[code] = data

def load_session(code):
    if redis_client:
        try:
            raw = redis_client.get(f"sess:{code}")
            if not raw:
                return None
            return json.loads(raw)
        except Exception as e:
            print("redis get err", e)
            return mem_get(code)
    else:
        return mem_get(code)

def save_session(code, data):
    data_to_store = dict(data)
    data_to_store["ts"] = time.time()
    if redis_client:
        try:
            redis_client.set(f"sess:{code}", json.dumps(data_to_store), ex=SESSION_TTL)
            return True
        except Exception as e:
            print("redis set err", e)
            mem_set(code, data_to_store)
            return False
    else:
        mem_set(code, data_to_store)
        return True

def generate_code(n=3):
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choice(chars) for _ in range(n))

def smart_shorten(text, limit=150):
    if not text:
        return text
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    # try to cut at last full stop within limit
    if "." in cut:
        pos = cut.rfind(".")
        if pos != -1 and pos+1 <= limit:
            return cut[:pos+1].strip()
    # if no period, cut at last newline
    if "\n" in cut:
        pos = cut.rfind("\n")
        if pos != -1:
            return cut[:pos].strip() + "..."
    # if no sentence boundary, cut at last space to avoid splitting words
    if " " in cut:
        pos = cut.rfind(" ")
        if pos != -1:
            return cut[:pos].strip() + "..."
    # fallback hard cut
    return cut.strip() + "..."

@app.route("/")
def home():
    return "bot online"

@app.route("/ask")
def ask():
    q = request.args.get("q", "").strip()
    if not q:
        return "no query provided, use ?q=your+question", 400

    try:
        parts = q.split(maxsplit=1)
        first = parts[0]
        rest = parts[1] if len(parts) > 1 else ""

        # normalize candidate code (accept leading #)
        if first.startswith("#"):
            cand = first[1:]
        else:
            cand = first

        is_code = 3 <= len(cand) <= 6 and all(c in (string.ascii_lowercase + string.digits) for c in cand)

        if is_code:
            session = load_session(cand)
            if session:
                # continuation
                if rest:
                    prompt = rest
                    # we will update session prompt to the new user text, model will reply to it
                    session["prompt"] = prompt
                    save_session(cand, session)
                else:
                    # use stored full prompt (last assistant reply or last user prompt)
                    prompt = session.get("prompt", "")
            else:
                # unknown code, treat whole query as a new prompt
                prompt = q
                cand = generate_code(3)
                save_session(cand, {"prompt": prompt})
        else:
            # new session
            prompt = q
            cand = generate_code(3)
            save_session(cand, {"prompt": prompt})

        # call model
        model_name = request.args.get("model") or DEFAULT_MODEL
        gen_model = genai.GenerativeModel(model_name)
        resp = gen_model.generate_content(prompt)

        # extract full reply text if present
        if hasattr(resp, "text") and resp.text:
            full_text = resp.text
        elif isinstance(resp, dict) and "candidates" in resp and resp["candidates"]:
            full_text = resp["candidates"][0].get("content", "")
        else:
            full_text = str(resp)

        # save full reply as the session prompt so next continuation uses full context
        save_session(cand, {"prompt": full_text})

        # return smart shortened version for chat, plus visible code
        short = smart_shorten(full_text, 150)
        return f"{short}  #{cand}"

    except Exception as e:
        tb = traceback.format_exc()
        print(tb)
        return f"error: {str(e)}", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
    
