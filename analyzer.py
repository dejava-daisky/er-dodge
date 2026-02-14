import requests
import os
import time
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ER_API_KEY")
BASE_URL = "https://open-api.bser.io"

CURRENT_SEASON = 26   # 🔥 현재 시즌 직접 지정 (변경 필요시 수정)

headers = {
    "x-api-key": API_KEY
}

# -------------------------------------------------
# TTL 캐시 (5분)
# -------------------------------------------------
CACHE = {}
CACHE_TTL = 300


def cache_get(key):
    if key in CACHE:
        data, timestamp = CACHE[key]
        if time.time() - timestamp < CACHE_TTL:
            return data
    return None


def cache_set(key, value):
    CACHE[key] = (value, time.time())


# -------------------------------------------------
# 기본 API 호출 (sleep 제거)
# -------------------------------------------------
def safe_get(url, params=None):
    res = requests.get(url, headers=headers, params=params, timeout=5)
    res.raise_for_status()
    return res.json()


# -------------------------------------------------
# UID 캐싱
# -------------------------------------------------
@lru_cache(maxsize=256)
def get_uid(nickname):
    url = f"{BASE_URL}/v1/user/nickname"
    data = safe_get(url, params={"query": nickname})
    return data["user"]["userId"]


# -------------------------------------------------
# 시즌 통계
# -------------------------------------------------
def get_season_stats(uid):
    cache_key = f"stats_{uid}"

    cached = cache_get(cache_key)
    if cached:
        return cached

    url = f"{BASE_URL}/v2/user/stats/uid/{uid}/{CURRENT_SEASON}/3"
    data = safe_get(url)

    stats = data["userStats"][0]
    cache_set(cache_key, stats)

    return stats


# -------------------------------------------------
# 최근 경기
# -------------------------------------------------
def get_recent_games(uid, count=10):
    cache_key = f"recent_{uid}_{count}"

    cached = cache_get(cache_key)
    if cached:
        return cached

    url = f"{BASE_URL}/v1/user/games/uid/{uid}"
    data = safe_get(url)

    games = data["userGames"]
    rank_games = [g for g in games if g["matchingMode"] == 3][:count]

    cache_set(cache_key, rank_games)

    return rank_games


# -------------------------------------------------
# 점수 계산
# -------------------------------------------------
def calculate_score(stats, recent_games):

    total_games = stats["totalGames"]
    average_rank = stats["averageRank"]
    win_rate = stats["totalWins"] / total_games if total_games > 0 else 0
    top3 = stats.get("top3", 0)
    top5 = stats.get("top5", 0)
    top7 = stats.get("top7", 0)

    char_stats = stats["characterStats"]
    most_used = max(c["totalGames"] for c in char_stats)
    most_used_ratio = most_used / total_games if total_games > 0 else 0

    score = 0
    strengths = []
    major_risks = []
    minor_risks = []

    # 평균 등수
    if average_rank <= 4.0:
        score += 15
        strengths.append("평균등수 안정적")
    elif average_rank <= 4.3:
        score += 12
    elif average_rank <= 4.5:
        score += 8

    # 승률
    if win_rate >= 0.18:
        score += 20
        strengths.append("막금구 마무리력 좋음")
    elif win_rate >= 0.14:
        score += 14
    elif win_rate >= 0.10:
        score += 8
    elif total_games >= 50 and win_rate < 0.08:
        major_risks.append("낮은 승률")

    # TOP3
    if top3 >= 0.50:
        score += 15
        strengths.append("TOP3 비율 높음")
    elif top3 >= 0.40:
        score += 12
    elif top3 >= 0.30:
        score += 8
    elif top3 >= 0.20:
        score += 4

    # 숙련도
    if total_games >= 50:
        if most_used_ratio >= 0.40:
            score += 20
            strengths.append("주력 실험체 숙련도 높음")
        elif most_used_ratio >= 0.25:
            score += 15
        elif most_used_ratio >= 0.15:
            score += 8
        else:
            major_risks.append("주력 실험체 경험 낮음")
    else:
        score += 10

    # 최근 폼 (루프 통합)
    if recent_games:
        total_rank = 0
        total_damage = 0

        for g in recent_games:
            total_rank += g["gameRank"]
            total_damage += g["damageToPlayer"]

        avg_rank_recent = total_rank / len(recent_games)
        avg_damage_recent = total_damage / len(recent_games)

        if avg_rank_recent <= 4:
            score += 20
            strengths.append("최근 폼 좋음")
        elif avg_rank_recent <= 5:
            score += 12
        elif avg_rank_recent <= 6:
            score += 5

        if avg_damage_recent >= 15000:
            score += 10
            strengths.append("최근 평딜 높음")
        elif avg_damage_recent >= 11000:
            score += 6
        elif avg_damage_recent >= 9000:
            score += 3
        else:
            minor_risks.append("최근 평균 딜 낮음")

        if avg_rank_recent > 6 and avg_damage_recent < 7000:
            major_risks.append("최근 폼 급락")

    gap = top7 - top5
    if gap >= 0.25:
        score -= 10
        major_risks.append("초반 사출 잦음")
    elif gap >= 0.15:
        score -= 5
        minor_risks.append("초반 사출 경향")

    return max(score, 0), strengths[:3], major_risks, minor_risks


# -------------------------------------------------
# 다람쥐 결정 (70 / 50 기준)
# -------------------------------------------------
def decide_squirrel(score):

    if score >= 70:
        return "purple"
    elif score >= 50:
        return "green"
    else:
        return "orange"


# -------------------------------------------------
# 최종 평가
# -------------------------------------------------
def evaluate_player(nickname):

    cache_key = f"eval_{nickname}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    uid = get_uid(nickname)

    stats = get_season_stats(uid)
    recent = get_recent_games(uid, 10)

    total_games = stats["totalGames"]

    if total_games < 50:
        result = {
            "nickname": nickname,
            "status": "sample",
            "message": "표본 부족 (50판 미만)"
        }
        cache_set(cache_key, result)
        return result

    score, strengths, major_risks, minor_risks = calculate_score(stats, recent)

    squirrel = decide_squirrel(score)

    result = {
        "nickname": nickname,
        "score": score,
        "squirrel": squirrel,
        "strengths": strengths,
        "major_risks": major_risks,
        "minor_risks": minor_risks
    }

    cache_set(cache_key, result)

    return result
