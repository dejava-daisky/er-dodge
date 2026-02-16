from flask import Flask, render_template, request, jsonify
from analyzer import analyze_player

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/scoreboard")
def scoreboard():
    return render_template("scoreboard.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.json
    nickname = data.get("nickname")

    if not nickname:
        return jsonify({"error": "닉네임 없음"})

    result = analyze_player(nickname)
    return jsonify(result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
