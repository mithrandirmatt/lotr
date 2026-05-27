import urllib.request, json, sys

MODELS = [
    "sorc/qwen3.5-claude-4.6-opus:latest",
    "qwen3:8b-q4_K_M",
]

for model in MODELS:
    try:
        req = urllib.request.Request(
            "http://localhost:11434/api/generate",
            data=json.dumps({"model": model, "prompt": "hi", "stream": False, "num_predict": 3}).encode(),
            headers={"Content-Type": "application/json"},
        )
        r = urllib.request.urlopen(req, timeout=120)
        d = json.loads(r.read())
        print(model, "OK" if d.get("done") else "FAIL", d.get("response", "")[:40])
    except Exception as e:
        print(model, "ERROR:", str(e)[:80])
