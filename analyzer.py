import os
import requests
from collections import Counter

BASE_URL = "https://open-api.bser.io"
API_KEY = os.getenv("ER_API_KEY")

HEADERS = {
    "accept": "application/json",
    "x-api-key": API_KEY
}

def api_get(path, params=None):
    r = requests.get(
        BASE_URL + path,
        headers=HEADERS,
        params=params,
        timeout=5
    )

    if r.status_code != 200:
        print("HTTP ERROR:", r.status_code, r.text)
        return None

    data = r.json()

    # 내부 code 검사
    if data.get("code") != 200:
        print("API ERROR:", data)
        return None

    return data


# -------------------------
# UID 조회
# -------------------------
def get_uid(nickname):
    data = api_get("/v1/user/nickname", {"query": nickname})
    if not data or "user" not in data:
        return None

    return data["user"].get("userId")   # 🔥 수정 완료


# -------------------------
# 최근 경기
# -------------------------
def get_recent_games(uid, limit=20):
    data = api_get(f"/v1/user/games/uid/{uid}")
    if not data or "userGames" not in data:
        return []

    return data["userGames"][:limit]


# -------------------------
# 시즌 통계
# -------------------------
def get_season_stats(uid, season_id):
    data = api_get(f"/v2/user/stats/uid/{uid}/{season_id}/3")
    if not data or "userStats" not in data:
        return None

    return data["userStats"][0]


# -------------------------
# 점수 계산
# -------------------------
def calc_score_and_comment(stats):
    if not stats:
        return 0, "", ""

    total = stats.get("totalGames", 1)
    wins = stats.get("wins", 0)
    top3 = stats.get("top3", 0)
    avg_dmg = stats.get("averageDamage", 0)
    avg_rank = stats.get("averageRank", 8)
    avg_kill = stats.get("averageKill", 0)
    avg_assist = stats.get("averageAssist", 0)
    top5 = stats.get("top5", 0)
    top7 = stats.get("top7", 0)

    score = 0
    strength = ""
    weakness = ""

    win_rate = wins / total if total else 0
    top3_rate = top3 / total if total else 0
    team_kill = avg_kill + avg_assist
    diff = (top7 - top5) / total if total else 0

    # 승률
    if win_rate >= 0.15: score += 10
    elif win_rate >= 0.12: score += 7
    elif win_rate >= 0.10: score += 5

    # TOP3
    if top3_rate >= 0.50: score += 15
    elif top3_rate >= 0.47: score += 12
    elif top3_rate >= 0.45: score += 9
    elif top3_rate >= 0.43: score += 6
    elif top3_rate >= 0.40: score += 3

    # 평균 딜
    if avg_dmg >= 18000: score += 15
    elif avg_dmg >= 15000: score += 10
    elif avg_dmg >= 12000: score += 5

    # 평균 등수
    if avg_rank <= 3.5: score += 20
    elif avg_rank <= 3.8: score += 16
    elif avg_rank <= 4.0: score += 12
    elif avg_rank <= 4.2: score += 8
    elif avg_rank <= 4.5: score += 4

    # 팀 기여
    if team_kill >= 11: score += 15
    elif team_kill >= 8: score += 10
    elif team_kill >= 6: score += 5

    # 하위권 방지
    if diff <= 0: score += 15
    elif diff <= 0.05: score += 10
    elif diff <= 0.10: score += 5

    # 강점
    if avg_rank <= 3.8:
        strength = "평균 등수가 안정적입니다."
    elif avg_dmg >= 15000:
        strength = "전투 기여도가 높습니다."
    elif team_kill >= 8:
        strength = "교전 참여도가 준수합니다."

    # 약점
    if diff > 0.10:
        weakness = "중하위권 탈락이 잦습니다."
    elif top3_rate < 0.43:
        weakness = "상위권 진입 비율이 높지 않습니다."
    elif win_rate < 0.10:
        weakness = "승률이 낮은 편입니다."

    return score, strength, weakness


# -------------------------
# 최종 평가
# -------------------------
def evaluate_player(nickname):
    uid = get_uid(nickname)
    if not uid:
        return {"status": "닉네임 없음"}

    games = get_recent_games(uid, 20)
    if not games:
        return {"status": "전적 없음"}

    season_id = next((g["seasonId"] for g in games if g.get("seasonId")), None)
    stats = get_season_stats(uid, season_id)

    score, strength, weakness = calc_score_and_comment(stats)

    if score >= 65:
        color = "purple"
        weakness = ""
    elif score >= 45:
        color = "green"
    else:
        color = "orange"
        strength = ""

    chars = [g["characterNum"] for g in games if g.get("characterNum")]
    counter = Counter(chars)
    most_char, most_cnt = counter.most_common(1)[0]

    return {
        "nickname": nickname,
        "score": score,
        "color": color,
        "games": stats.get("totalGames", 0) if stats else 0,
        "mostChar": most_char,
        "mostCharGames": most_cnt,
        "strength": strength,
        "weakness": weakness
    }
