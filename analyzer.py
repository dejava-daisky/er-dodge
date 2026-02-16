import requests
import os

BASE_URL = "https://open-api.bser.io"
API_KEY = os.getenv("ER_API_KEY")

HEADERS = {
    "accept": "application/json",
    "x-api-key": API_KEY
}

# -----------------------
# 공통 API
# -----------------------
def api_get(path, params=None):
    try:
        r = requests.get(BASE_URL + path, headers=HEADERS, params=params, timeout=5)
        if r.status_code != 200:
            print("API FAIL:", r.status_code, path)
            return None
        return r.json()
    except Exception as e:
        print("API EX:", e)
        return None


# -----------------------
# UID 조회
# -----------------------
def get_user_uid(nickname):
    data = api_get("/v1/user/nickname", {"query": nickname})
    if not data or "user" not in data:
        return None
    return data["user"]["userNum"]


# -----------------------
# 최근 경기 (점수 계산용)
# -----------------------
def get_recent_games(uid, limit=20):
    data = api_get(f"/v1/user/games/uid/{uid}")
    if not data or "userGames" not in data:
        return []
    return data["userGames"][:limit]


# -----------------------
# 전체 판수 (표본 경고용)
# -----------------------
def get_total_games(uid):
    # 시즌 고정 (현재 시즌 번호)
    season = 3
    mode = 3

    data = api_get(f"/v2/user/stats/uid/{uid}/{season}/{mode}")
    if not data or "userStats" not in data:
        return 0

    return data["userStats"][0].get("totalGames", 0)


# -----------------------
# 점수 계산
# -----------------------
def calculate_score(games):
    if not games:
        return 0

    ranks = [g["gameRank"] for g in games if g.get("gameRank")]
    if not ranks:
        return 0

    avg_rank = sum(ranks) / len(ranks)

    score = int(100 - avg_rank * 6)

    return max(0, min(score, 100))


# -----------------------
# 최종 평가
# -----------------------
def evaluate_player(nickname):
    uid = get_user_uid(nickname)
    if not uid:
        return {"status": "닉네임 없음"}

    games = get_recent_games(uid)
    if not games:
        return {"status": "전적 없음"}

    score = calculate_score(games)

    # 색상 판정
    color = "orange"
    if score >= 70:
        color = "purple"
    elif score >= 50:
        color = "green"

    # 전체 판수
    total_games = get_total_games(uid)

    warning = None
    if total_games < 50:
        warning = "*50판 이하라서 결과가 부정확할 수 도있어,,참고만해,,!!*"

    return {
        "nickname": nickname,
        "score": score,
        "color": color,
        "recentGames": len(games),
        "totalGames": total_games,
        "warning": warning
    }


# -----------------------
# self_analyzer 호환용
# -----------------------
analyze_player = evaluate_player
