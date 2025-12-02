from flask import Flask, request
import google.generativeai as genai
import os, traceback, random, string, time, threading

app = Flask(__name__)

# load key
KEY = os.getenv("GEMINI_KEY") or os.getenv("GOOGLE_API_KEY")
if not KEY:
    raise RuntimeError("no api key found, set GOOGLE_API_KEY or GEMINI_KEY in environment")

# default model
DEFAULT_MODEL = "gemini-2.5-flash"

# configure google ai
genai.configure(api_key=KEY)

# session storage (in memory)
SESSIONS = {}
SESSION_TTL = 24 * 60 * 60  # 24h

def generate_code(n=3):
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choice(chars) for _ in range(n))

# clean old sessions
def cleanup():
    while True:
        now = time.time()
        dead = [c for c, s in SESSIONS.items() if now - s["ts"] > SESSION_TTL]
        for c in dead:
            del SESSIONS[c]
        time.sleep(600)

threading.Thread(target=cleanup, daemon=True).start()

def new_session(prompt):
    code = generate_code()
    while code in SESSIONS:
        code = generate_code()
    SESSIONS[code] = {
        "prompt": prompt,
        "ts": time.time()
    }
    return code

def update_session(code, new_prompt):
    if code in SESSIONS:
        SESSIONS[code]["prompt"] = new_prompt
        SESSIONS[code]["ts"] = time.time()
        return True
    return False


@app.route("/")
def home():
    return "bot online"


@app.route("/ask")
def ask():
    q = request.args.get("q", "").strip()

    # no query
    if not q:
        return "no query", 400

    try:
        # detect code continuation
        parts = q.split(maxsplit=1)
        first = parts[0]
        rest = parts[1] if len(parts) > 1 else ""

        # remove # from start
        if first.startswith("#"):
            code = first[1:]
        else:
            code = first

        # continuation if valid code
        if code in SESSIONS:
            # continuation mode
            if rest:
                prompt = rest
                update_session(code, rest)
            else:
                prompt = SESSIONS[code]["prompt"]
        else:
            # new session
            prompt = q
            code = new_session(prompt)

        # call model
        model = genai.GenerativeModel(DEFAULT_MODEL)
        resp = model.generate_content(prompt)

        # extract text
        if hasattr(resp, "text") and resp.text:
            text = resp.text
        else:
            text = str(resp)

        # update session prompt to last reply so continuation works
        update_session(code, text)

        # return reply + continuation code
        return f"{text}  #{code}"

    except Exception as e:
        tb = traceback.format_exc()
        print(tb)
        return f"error: {str(e)}", 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
        
