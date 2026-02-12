import requests
import time
import statistics
import json
import os
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("ER_API_KEY")
BASE_URL = "https://open-api.bser.io"

headers = {
    "x-api-key": API_KEY
}

# -----------------------------
# 기본 API 함수
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
    games = data["userGames"]

    for g in games:
        if g["matchingMode"] == 3 and g["seasonId"] > 0:
            return g["seasonId"]

    raise Exception("랭크 시즌 찾기 실패")


def get_season_stats(uid, season_id):
    url = f"{BASE_URL}/v2/user/stats/uid/{uid}/{season_id}/3"
    data = safe_get(url)
    return data["userStats"][0]


def get_recent_games(uid, count=10):
    url = f"{BASE_URL}/v1/user/games/uid/{uid}"
    data = safe_get(url)
    games = data["userGames"]
    rank_games = [g for g in games if g["matchingMode"] == 3]
    return rank_games[:count]


# -----------------------------
# 점수 계산
# -----------------------------

def calculate_score(stats, recent_games):

    total_games = stats["totalGames"]
    average_rank = stats["averageRank"]
    win_rate = stats["totalWins"] / total_games
    top3 = stats.get("top3", 0)

    char_stats = stats["characterStats"]
    most_used = max(c["totalGames"] for c in char_stats)
    most_used_ratio = most_used / total_games

    score = 0
    breakdown = {}

    # 평균 등수 (15)
    rank_score = 0
    if average_rank <= 4.0:
        rank_score = 15
    elif average_rank <= 4.5:
        rank_score = 10
    elif average_rank <= 5.0:
        rank_score = 5
    breakdown["평균 등수"] = (rank_score, 15)
    score += rank_score

    # 승률 (20)
    win_score = 0
    if win_rate >= 0.18:
        win_score = 20
    elif win_rate >= 0.14:
        win_score = 14
    elif win_rate >= 0.10:
        win_score = 8
    breakdown["승률"] = (win_score, 20)
    score += win_score

    # top3 (15)
    top3_score = 0
    if top3 >= 0.50:
        top3_score = 15
    elif top3 >= 0.40:
        top3_score = 12
    elif top3 >= 0.30:
        top3_score = 8
    elif top3 >= 0.20:
        top3_score = 4
    breakdown["상위권 전환력"] = (top3_score, 15)
    score += top3_score

    # 실험체 집중도 (20)
    focus_score = 0
    if total_games >= 50:
        if most_used_ratio >= 0.4:
            focus_score = 20
        elif most_used_ratio >= 0.25:
            focus_score = 15
        elif most_used_ratio >= 0.15:
            focus_score = 8
    else:
        focus_score = 10
    breakdown["실험체 숙련도"] = (focus_score, 20)
    score += focus_score

    # 최근 폼 (30)
    form_score = 0
    if recent_games:
        avg_rank_recent = sum(g["gameRank"] for g in recent_games) / len(recent_games)
        avg_damage_recent = sum(g["damageToPlayer"] for g in recent_games) / len(recent_games)

        # 최근 평균 등수 (20)
        if avg_rank_recent <= 4:
            form_score += 20
        elif avg_rank_recent <= 5:
            form_score += 12
        elif avg_rank_recent <= 6:
            form_score += 5

        # 최근 평균 딜 (10)
        if avg_damage_recent >= 11000:
            form_score += 10
        elif avg_damage_recent >= 9500:
            form_score += 6
        elif avg_damage_recent >= 8000:
            form_score += 3

    breakdown["최근 폼"] = (form_score, 30)
    score += form_score

    # 가장 취약한 항목
    weakest = min(
        breakdown.items(),
        key=lambda x: x[1][0] / x[1][1]
    )[0]

    comment_map = {
        "평균 등수": "평균 등수 낮음",
        "승률": "승률 낮음",
        "상위권 전환력": "상위권 전환율 낮음",
        "실험체 숙련도": "실험체 숙련도 낮음",
        "최근 폼": "최근 폼 불안정"
    }

    comment = comment_map.get(weakest, "")

    return score, comment


# -----------------------------
# 경고 생성
# -----------------------------

def generate_warnings(stats, recent_games):

    warnings = []

    total_games = stats["totalGames"]
    win_rate = stats["totalWins"] / total_games
    top3 = stats.get("top3", 0)
    top5 = stats.get("top5", 0)
    top7 = stats.get("top7", 0)

    # 승률 위험
    if total_games >= 50 and win_rate < 0.08:
        warnings.append("낮은 승률")

    # 조기사망 패턴
    if total_games >= 50 and (top7 - top5) >= 0.25 and top3 <= 0.30:
        warnings.append("중반 탈락 빈번")

    # 최근 폼 급락
    if recent_games:
        avg_rank_recent = sum(g["gameRank"] for g in recent_games) / len(recent_games)
        avg_damage_recent = sum(g["damageToPlayer"] for g in recent_games) / len(recent_games)

        if avg_rank_recent > 6 and avg_damage_recent < 7000:
            warnings.append("최근 폼 급락")

    # 실험체 숙련도 낮음
    char_stats = stats["characterStats"]
    most_used = max(c["totalGames"] for c in char_stats)
    if total_games >= 50 and most_used < 10:
        warnings.append("주력 실험체 경험 부족")

    return warnings


# -----------------------------
# 등급
# -----------------------------

def grade(score):
    if score >= 85:
        return "🟢 최고 좋음"
    elif score >= 70:
        return "🔵 좋음"
    elif score >= 50:
        return "🟡 보통"
    elif score >= 35:
        return "🟠 나쁨"
    else:
        return "🔴 닷지 권장"


# -----------------------------
# 최종 평가 함수
# -----------------------------

def evaluate_player(nickname):

    uid = get_uid(nickname)
    season = get_rank_season_from_games(uid)
    stats = get_season_stats(uid, season)
    recent = get_recent_games(uid)
    
    score, comment = calculate_score(stats, recent)
    warnings = generate_warnings(stats, recent)

    total_games = stats["totalGames"]

    # 50판 미만이면 표본 부족 처리
    if total_games < 50:
        warnings.append("표본 부족 (50판 미만)")
        final_grade = "⚪ 표본 부족"
    else:
        final_grade = grade(score)

    return {
        "nickname": nickname,
        "score": score,
        "grade": final_grade,
        "comment": comment,
        "warnings": warnings,
        "total_games": total_games
        }



# -----------------------------
# CLI 테스트용
# -----------------------------

def run():
    nick1 = input("팀원1 닉네임: ")
    nick2 = input("팀원2 닉네임: ")

    p1 = evaluate_player(nick1)
    p2 = evaluate_player(nick2)

    for p in [p1, p2]:
        print(f"\n{p['nickname']}: {p['score']}점 → {p['grade']} ({p['comment']})")
        if p["warnings"]:
            print("경고:", ", ".join(p["warnings"]))


if __name__ == "__main__":

    run()
