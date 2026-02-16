import requests
import os
import time

BASE_URL = "https://open-api.bser.io"
API_KEY = os.getenv("ER_API_KEY")

HEADERS = {
    "accept": "application/json",
    "x-api-key": API_KEY
}

# =========================
# 안전 GET
# =========================
def safe_get(url, params=None):
    try:
        res = requests.get(url, headers=HEADERS, params=params, timeout=5)
        print("API:", res.status_code, url)

        if res.status_code != 200:
            return None

        return res.json()

    except Exception as e:
        print("API FAIL:", e)
        return None


# =========================
# 시즌 (fallback 구조)
# =========================
CURRENT_SEASON = 29  # 실패 시 이 값 사용

def get_current_season_safe():
    url = f"{BASE_URL}/v1/game/season"
    data = safe_get(url)
    if data and "seasonId" in data:
        return data["seasonId"]
    return CURRENT_SEASON


# =========================
# UID 조회
# =========================
def get_uid(nickname):
    url = f"{BASE_URL}/v1/user/nickname"
    data = safe_get(url, params={"query": nickname})

    if not data or "user" not in data:
        return None

    return data["user"]["userNum"]


# =========================
# 시즌 전적
# =========================
def get_season_stats(uid):
    season = get_current_season_safe()
    url = f"{BASE_URL}/v2/user/stats/uid/{uid}/{season}/3"
    data = safe_get(url)

    if not data or "userStats" not in data:
        return None

    return data["userStats"][0]


# =========================
# 최근 경기 (self_analyzer용)
# =========================
def get_recent_games(uid, limit=20):
    try:
        url = f"{BASE_URL}/v1/user/games/{uid}"
        data = safe_get(url)

        if not data or "userGames" not in data:
            return []

        games = data["userGames"][:limit]

        result = []
        for g in games:
            result.append({
                "gameId": g.get("gameId"),
                "seasonId": g.get("seasonId"),
                "characterNum": g.get("characterNum"),
                "rank": g.get("gameRank"),
                "mmr": g.get("mmr"),
                "mode": g.get("matchingMode")
            })

        return result

    except Exception as e:
        print("recent fail:", e)
        return []


# =========================
# 메인 평가
# =========================
def evaluate_player(nickname):
    uid = get_uid(nickname)
    if not uid:
        return {
            "nickname": nickname,
            "status": "error",
            "message": "닉네임 없음"
        }

    stats = get_season_stats(uid)
    if not stats:
        return {
            "nickname": nickname,
            "status": "error",
            "message": "API 실패"
        }

    total_games = stats.get("totalGames", 0)
    win_rate = stats.get("top1Rate", 0)

    if total_games < 50:
        return {
            "nickname": nickname,
            "status": "sample_low",
            "score": 0
        }

    score = int(win_rate * 100)

    if score >= 70:
        color = "purple"
    elif score >= 50:
        color = "green"
    else:
        color = "orange"

    return {
        "nickname": nickname,
        "status": "ok",
        "score": score,
        "color": color,
        "totalGames": total_games,
        "winRate": win_rate
    }
# =========================
# 점수 계산 (self_analyzer용)
# =========================
def calculate_score(win_rate, total_games):
    """
    self_analyzer에서 호출하는 점수 계산 함수
    서버 죽지 않게 매우 단순 구조
    """
    try:
        if total_games < 5:
            return 0

        score = int(win_rate * 100)

        if score > 100:
            score = 100
        if score < 0:
            score = 0

        return score

    except:
        return 0
