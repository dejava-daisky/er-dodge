import requests
import time
import os
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("ER_API_KEY")
BASE_URL = "https://open-api.bser.io"

headers = {"x-api-key": API_KEY}


# -----------------------------
# API 기본 함수
# -----------------------------

def safe_get(url, params=None):
    res = requests.get(url, headers=headers, params=params)
    time.sleep(1.1)
    return res.json()


def get_uid(nickname):
    url = f"{BASE_URL}/v1/user/nickname"
    data = safe_get(url, params={"query": nickname})
    return data["user"]["userId"]


def get_rank_season_from_games(uid):
    url = f"{BASE_URL}/v1/user/games/uid/{uid}"
    data = safe_get(url)
    for g in data["userGames"]:
        if g["matchingMode"] == 3 and g["seasonId"] > 0:
            return g["seasonId"]
    raise Exception("랭크 시즌 찾기 실패")


def get_season_stats(uid, season_id):
    url = f"{BASE_URL}/v2/user/stats/uid/{uid}/{season_id}/3"
    data = safe_get(url)
    return data["userStats"][0]


def get_recent_games(uid, count=20):
    url = f"{BASE_URL}/v1/user/games/uid/{uid}"
    data = safe_get(url)
    rank_games = [g for g in data["userGames"] if g["matchingMode"] == 3]
    return rank_games[:count]


# -----------------------------
# 점수 계산 + 장단점 생성
# -----------------------------

def calculate_score(stats, recent_games):

    total_games = stats["totalGames"]
    average_rank = stats["averageRank"]
    win_rate = stats["totalWins"] / total_games
    top3 = stats.get("top3", 0)
    top5 = stats.get("top5", 0)
    top7 = stats.get("top7", 0)

    char_stats = stats["characterStats"]
    most_used = max(c["totalGames"] for c in char_stats)
    most_used_ratio = most_used / total_games

    score = 0
    strengths = []
    major_risks = []
    minor_risks = []

    # ---------------- 평균 등수
    if average_rank <= 4.0:
        score += 15
        strengths.append("평균등수가 안정적입니다.")
    elif average_rank <= 4.3:
        score += 12
    elif average_rank <= 4.5:
        score += 8

    # ---------------- 승률
    if win_rate >= 0.18:
        score += 20
        strengths.append("막금구교전에서 빛을 발합니다.")
    elif win_rate >= 0.14:
        score += 14
    elif win_rate >= 0.10:
        score += 8
    else:
        if total_games >= 50 and win_rate < 0.08:
            major_risks.append("승률이 낮은편입니다.")

    # ---------------- TOP3
    if top3 >= 0.50:
        score += 15
        strengths.append("TOP3비율이 높습니다.")
    elif top3 >= 0.40:
        score += 12
    elif top3 >= 0.30:
        score += 8
    elif top3 >= 0.20:
        score += 4

    # ---------------- 숙련도
    if total_games >= 50:
        if most_used_ratio >= 0.40:
            score += 20
            strengths.append("한 실험체를 많이 플레이합니다.")
        elif most_used_ratio < 0.15:
            major_risks.append("이것저것 실험체를 여러개 하는편입니다.")
    else:
        score += 10

    # ---------------- 최근 폼
    if recent_games:
        avg_rank_recent = sum(g["gameRank"] for g in recent_games) / len(recent_games)
        avg_damage_recent = sum(g["damageToPlayer"] for g in recent_games) / len(recent_games)

        if avg_rank_recent <= 4:
            score += 20
            strengths.append("최근20경기의 폼이 좋습니다.")
        elif avg_rank_recent > 6 and avg_damage_recent < 7000:
            major_risks.append("최근20경기 폼이 급락중입니다.")

        if avg_damage_recent >= 15000:
            score += 10
            strengths.append("최근20경기에서 딜량이 좋습니다.")
        elif avg_damage_recent < 9000:
            minor_risks.append("최근20경기 딜량이 낮습니다. 탱커유저인가요?")

    # ---------------- 초반 사출 감점
    gap = top7 - top5
    if gap >= 0.25:
        score -= 10
        major_risks.append("초반(6~8등)에 사출을 자주당합니다.")
    elif gap >= 0.15:
        score -= 5
        minor_risks.append("초반에 사출당하는 경향이 있습니다.")

    if score < 0:
        score = 0

    return score, strengths[:3], major_risks, minor_risks


# -----------------------------
# 다람쥐 상태
# -----------------------------

def decide_squirrel(strengths, major_risks):
    if len(major_risks) >= 2:
        return "orange"
    elif len(strengths) >= 2 and len(major_risks) <= 1:
        return "purple"
    else:
        return "green"


# -----------------------------
# 총평 생성 (줄바꿈 포함)
# -----------------------------

def generate_summary(strengths, major_risks, minor_risks, squirrel):

    lines = []

    # 위험형이면 장점 제외
    if squirrel != "orange":
        for i, s in enumerate(strengths):
            if i == len(strengths) - 1 and (major_risks or minor_risks):
                lines.append(s.replace("입니다.", "입니다. 하지만"))
            else:
                lines.append(s)

    risks = major_risks + minor_risks
    for r in risks:
        lines.append(r)

    return "\n".join(lines)


# -----------------------------
# 최종 평가
# -----------------------------

def evaluate_player(nickname):

    uid = get_uid(nickname)
    season = get_rank_season_from_games(uid)
    stats = get_season_stats(uid, season)
    recent = get_recent_games(uid)

    total_games = stats["totalGames"]

    if total_games < 50:
        return {
            "nickname": nickname,
            "status": "sample",
            "message": "표본 부족 (50판 미만)"
        }

    score, strengths, major_risks, minor_risks = calculate_score(stats, recent)
    squirrel = decide_squirrel(strengths, major_risks)
    summary = generate_summary(strengths, major_risks, minor_risks, squirrel)

    return {
        "nickname": nickname,
        "score": score,
        "squirrel": squirrel,
        "strengths": strengths,
        "major_risks": major_risks,
        "minor_risks": minor_risks,
        "summary": summary
    }
