import os
from flask import Flask, render_template, request, jsonify

from analyzer import evaluate_player
from self_analyzer import evaluate_self_player

app = Flask(
    __name__,
    static_folder="static",
    template_folder="templates"
)

# 메인 페이지
@app.route("/")
def index():
    return render_template("index.html")


# 팀원 분석(JSON)
@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        data = request.get_json(force=True)
        names = data.get("names", [])

        results = []
        for name in names:
            if not name.strip():
                continue
            r = evaluate_player(name.strip())
            results.append(r)

        return jsonify({"results": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 자화상
@app.route("/self", methods=["GET", "POST"])
def self_page():
    if request.method == "POST":
        nickname = request.form.get("nickname", "").strip()
        if nickname:
            result = evaluate_self_player(nickname)
            return render_template("self.html", result=result)
    return render_template("self.html")


# 채점표
@app.route("/scoreboard")
def scoreboard():
    return render_template("scoreboard.html")


# 로컬 실행용
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
