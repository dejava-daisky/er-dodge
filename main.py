from flask import Flask, render_template, request, jsonify
from analyzer import evaluate_player
from self_analyzer import evaluate_self_player

app = Flask(__name__)

# -------------------------
# 기본 페이지 라우트
# -------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/scoreboard")
def scoreboard():
    return render_template("scoreboard.html")


@app.route("/self")
def self_page():
    return render_template("self.html")


@app.route("/criteria")
def criteria():
    return render_template("criteria.html")


# -------------------------
# 공통 닉네임 추출 함수
# -------------------------
def extract_nickname(data):
    if not isinstance(data, dict):
        return None

    # 일반 페이지
    nickname = data.get("nickname")
    if nickname:
        return nickname.strip()

    # 자화상 페이지 배열 방식
    nicknames = data.get("nicknames")
    if isinstance(nicknames, list) and nicknames:
        return str(nicknames[0]).strip()

    return None


# -------------------------
# 팀원 초상화 분석
# -------------------------
@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        data = request.json or {}
        nickname = extract_nickname(data)

        if not nickname:
            return jsonify({"status": "닉네임 없음"})

        result = evaluate_player(nickname)
        return jsonify(result)

    except Exception as e:
        print("ANALYZE ERROR:", e)
        return jsonify({"status": "검색 실패"})


# -------------------------
# 자화상 분석 (선택 기능)
# -------------------------
@app.route("/self_analyze", methods=["POST"])
def self_analyze():
    try:
        data = request.json or {}
        nickname = extract_nickname(data)

        if not nickname:
            return jsonify({"status": "닉네임 없음"})

        result = evaluate_self_player(nickname)
        return jsonify(result)

    except Exception as e:
        print("SELF ANALYZE ERROR:", e)
        return jsonify({"status": "자화상 분석 실패"})


# -------------------------
# 서버 실행
# -------------------------
if __name__ == "__main__":
    import os

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
