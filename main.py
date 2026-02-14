from flask import Flask, render_template, request
from concurrent.futures import ThreadPoolExecutor
import re

from analyzer import evaluate_player
from self_analyzer import evaluate_self_player

app = Flask(__name__)

# -------------------------------------------------
# 닉네임 파서 (스페이스, 쉼표, 슬래시 대응)
# -------------------------------------------------
def parse_names(input_text):
    if not input_text:
        return []

    names = re.split(r"[ ,/]+", input_text.strip())
    return [n for n in names if n]


# -------------------------------------------------
# 1️⃣ 팀원 초상화 (기본 빠른 분석)
# -------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def index():

    results = None

    if request.method == "POST":
        raw_input = request.form.get("nickname")
        names = parse_names(raw_input)

        if names:
            # 병렬 처리 (2명 기준)
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(evaluate_player, names))

    return render_template("index.html", results=results)


# -------------------------------------------------
# 2️⃣ 자화상 (확장 분석 전용)
# -------------------------------------------------
@app.route("/self", methods=["GET", "POST"])
def self_portrait():

    result = None

    if request.method == "POST":
        nickname = request.form.get("nickname")

        if nickname:
            result = evaluate_self_player(nickname)

    return render_template("self.html", result=result)


# -------------------------------------------------
# 3️⃣ 채점표
# -------------------------------------------------
@app.route("/scoreboard")
def scoreboard():
    return render_template("scoreboard.html")


# -------------------------------------------------
# 실행
# -------------------------------------------------
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
