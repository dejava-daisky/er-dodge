from flask import Flask, request, jsonify
from analyzer import evaluate_player

app = Flask(__name__)

@app.post("/analyze")
def analyze():
    data = request.get_json()
    nicks = data.get("nicknames", [])
    
    if not nicks or not isinstance(nicks, list):
        return jsonify({"error": "nicknames 리스트를 보내세요"}), 400
    
    results = {}
    for nick in nicks:
        try:
            results[nick] = evaluate_player(nick)
        except Exception as e:
            results[nick] = {"error": str(e)}

    return jsonify(results)

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
