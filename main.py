from flask import Flask, render_template, request, jsonify, send_from_directory
from concurrent.futures import ThreadPoolExecutor
import os
import re

from analyzer import evaluate_player
from self_analyzer import evaluate_self_player

app = Flask(__name__)

# -------------------------------------------------
# templates 내부 파일 직접 서빙
# -------------------------------------------------
@app.route("/assets/<path:filename>")
def serve_template_assets(filename):
    template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
    return send_from_directory(template_dir, filename)


# -------------------------------------------------
# 닉네임 파서
# -------------------------------------------------
def parse_names(input_text):
    if not input_text:
        return []

    names = re.split(r"[ ,/]+", input_text.strip())
    return [n for n in names if n]


# -------------------------------------------------
# 메인 페이지
# -------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


# -------------------------------------------------
# 팀원 분석 API
# -------------------------------------------------
@app.route("/analyze", methods=["POST"])
def analyze():

    data = request.get_json()

    if not data or "nicknames" not in data:
        return jsonify({"error": "닉네임이 없습니다."}), 400

    names = data["nicknames"]

    results = {}

    with ThreadPoolExecutor(max_workers=2) as executor:
        evaluated = list(executor.map(evaluate_player, names))

    for result in evaluated:
        nickname = result.get("nickname")
        if nickname:
            results[nickname] = result

    return jsonify(results)


# -------------------------------------------------
# 자화상
# -------------------------------------------------
@app.route("/self")
def self_page():
    return render_template("self.html")


@app.route("/analyze_self", methods=["POST"])
def analyze_self_route():

    data = request.get_json()

    if not data or "nickname" not in data:
        return jsonify({"error": "닉네임이 없습니다."}), 400

    nickname = data["nickname"]
    result = evaluate_self_player(nickname)

    return jsonify(result)


# -------------------------------------------------
# 채점표
# -------------------------------------------------
@app.route("/scoreboard")
def scoreboard():
    return render_template("scoreboard.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
