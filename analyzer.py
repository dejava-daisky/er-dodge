import requests
import os
import time

API_KEY = os.getenv("ER_API_KEY")
BASE_URL = "https://open-api.bser.io"

HEADERS = {
    "accept": "application/json",
    "x-api-key": API_KEY
}


# =========================
# 안전 요청 함수
# =========================
def safe_get(url):
    try:
        res = requests.get(url, headers=HEADERS, timeout=5)
        print("API:", res.status_code, url)

        if res.status_code != 200:
            return None

        return res.json()

    except Exception as e:
        print("API FAIL:", e)
        return None


# =========================
# 시즌 자동 감지
# =========================
def get_current_season():
    url = f"{BASE_URL}/v1/game/season"
    data = safe_get(url)
    if data and "seasonId" in data:
        return data["seasonId"]
    return 29   # fallback


CURRENT_SEASON = get_current_season()


# =========================
# UID 조회
# =========================
def get_uid(nickname):
    url = f"{BASE_URL}/v1/user/nickname?query={nickname}"
    data = safe_get(url)

    if not data or "user" not in data:
        return None

    return data["user"]["userNum"]


# =========================
# 시즌 전적 조회
# =========================
def get_season_stats(uid):
    url = f"{BASE_URL}/v2/user/stats/uid/{uid}/{CURRENT_SEASON}/3"
    data = safe_get(url)

    if not data or "userStats" not in data:
        return None

    return data["userStats"][0]


# =========================
# 평가 메인
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
# 최근 경기 조회 (self_analyzer용)
# =========================
def get_recent_games(uid, limit=20):
    """
    최근 경기 기록을 간단 리스트로 반환
    실패 시 빈 리스트 반환 (서버 죽지 않게)
    """
    try:
        # 최근 매치 ID 목록
        url = f"{BASE_URL}/v1/user/games/{uid}"
        data = safe_get(url)

        if not data or "userGames" not in data:
            return []

        games = data["userGames"][:limit]

        # 필요한 최소 정보만 정리
        result = []
        for g in games:
            result.append({
                "gameId": g.get("gameId"),
                "seasonId": g.get("seasonId"),
                "characterNum": g.get("characterNum"),
                "rank": g.get("gameRank"),
                "mmr": g.get("mmr"),
                "gameMode": g.get("matchingMode"),
                "createdAt": g.get("startDtm")
            })

        return result

    except Exception as e:
        print("recent games fail:", e)
        return []
