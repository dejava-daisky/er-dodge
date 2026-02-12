from flask import Flask, request, render_template, jsonify, send_from_directory
from analyzer import evaluate_player
import os

app = Flask(__name__)

# -----------------------------
# 메인 페이지
# -----------------------------

@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")


# -----------------------------
# 분석 API
# -----------------------------

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


# -----------------------------
# templates 폴더 이미지 서빙
# -----------------------------

@app.route("/<path:filename>")
def serve_file(filename):
    return send_from_directory("templates", filename)


# -----------------------------
# 실행
# -----------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
