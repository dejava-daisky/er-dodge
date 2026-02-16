import requests
import os

BASE_URL = "https://open-api.bser.io"
API_KEY = os.getenv("ER_API_KEY")

HEADERS = {
    "accept": "application/json",
    "x-api-key": API_KEY
}

def api_get(path, params=None):
    r = requests.get(BASE_URL + path, headers=HEADERS, params=params)
    if r.status_code != 200:
        return None
    return r.json()

# ------------------
# UID 조회
# ------------------
def get_user_uid(nickname):
    data = api_get("/v1/user/nickname", {"query": nickname})
    if not data or "user" not in data:
        return None
    return data["user"]["userNum"]

# ------------------
# 최근 경기
# ------------------
def get_recent_games(uid, limit=20):
    data = api_get(f"/v1/user/games/uid/{uid}")
    if not data or "userGames" not in data:
        return []
    return data["userGames"][:limit]

# ------------------
# 점수 계산
# ------------------
def calculate_score(games):
    if len(games) < 5:
        return 0

    ranks = [g["gameRank"] for g in games if g.get("gameRank")]
    if not ranks:
        return 0

    avg_rank = sum(ranks) / len(ranks)
    score = int(100 - avg_rank * 6)

    return max(0, min(score, 100))

# ------------------
# 메인 평가
# ------------------
def evaluate_player(nickname):
    uid = get_user_uid(nickname)
    if not uid:
        return {"status": "닉네임 없음"}

    games = get_recent_games(uid)
    if not games:
        return {"status": "표본 부족"}

    score = calculate_score(games)

    color = "orange"
    if score >= 70:
        color = "purple"
    elif score >= 50:
        color = "green"

    return {
        "nickname": nickname,
        "score": score,
        "color": color,
        "games": len(games)
    }
