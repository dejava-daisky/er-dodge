from flask import Flask, request, render_template, jsonify, send_from_directory
from analyzer import evaluate_player
import os

app = Flask(__name__)

# -----------------------------
# 페이지 라우팅
# -----------------------------

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/self")
def self_page():
    return render_template("self.html")

@app.route("/criteria")
def criteria_page():
    # 아직 페이지 없으면 나중에 추가
    return "<h2>채점표 준비중</h2>"

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
# templates 폴더 이미지/파일 서빙
# -----------------------------

@app.route("/<path:filename>")
def serve_template_file(filename):
    try:
        return send_from_directory("templates", filename)
    except:
        return "File not found", 404

# -----------------------------
# 실행 (Render 대응)
# -----------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
