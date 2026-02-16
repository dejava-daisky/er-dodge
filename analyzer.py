import requests
import os
import time

BASE_URL = "https://open-api.bser.io"
API_KEY = os.getenv("ER_API_KEY")

HEADERS = {
    "accept": "application/json",
    "x-api-key": API_KEY
}

def safe_get(url):
    try:
        res = requests.get(url, headers=HEADERS, timeout=5)
        if res.status_code != 200:
            print("API FAIL:", res.status_code, url)
            return None
        return res.json()
    except Exception as e:
        print("API EX:", e)
        return None


# ======================
# UID 조회
# ======================
def get_user_uid(nickname):
    url = f"{BASE_URL}/v1/user/nickname?query={nickname}"
    data = safe_get(url)
    if not data or "user" not in data:
        return None
    return data["user"]["userNum"]


# ======================
# 최근 경기
# ======================
def get_recent_games(uid, limit=20):
    url = f"{BASE_URL}/v1/user/games/uid/{uid}"
    data = safe_get(url)
    if not data or "userGames" not in data:
        return []
    return data["userGames"][:limit]


# ======================
# 점수 계산
# ======================
def calculate_score(games):
    if not games or len(games) < 5:
        return 0

    avg_rank = sum(g["gameRank"] for g in games if g.get("gameRank")) / len(games)
    score = int(100 - avg_rank * 5)

    if score < 0:
        score = 0
    if score > 100:
        score = 100

    return score


# ======================
# 종합 분석
# ======================
def analyze_player(nickname):
    uid = get_user_uid(nickname)
    if not uid:
        return {"error": "닉네임 없음"}

    games = get_recent_games(uid)

    if not games:
        return {"error": "표본 부족"}

    score = calculate_score(games)

    return {
        "nickname": nickname,
        "score": score,
        "games": len(games)
    }
