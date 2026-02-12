from flask import Flask, request, render_template, jsonify
from analyzer import evaluate_player

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def home():
    result = None
    
    if request.method == "POST":
        nick1 = request.form.get("nick1")
        nick2 = request.form.get("nick2")

        result = {}

        for nick in [nick1, nick2]:
            if nick:
                try:
                    result[nick] = evaluate_player(nick)
                except Exception as e:
                    result[nick] = {"error": str(e)}

    return render_template("index.html", result=result)


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
