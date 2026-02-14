from analyzer import (
    get_uid,
    get_season_stats,
    get_recent_games,
    calculate_score
)
from character_map import CHARACTER_MAP


# -----------------------------
# 최근 50경기 기반 실험체 분석
# -----------------------------
def analyze_team_synergy(uid, recent_games_count=50):

    games = get_recent_games(uid, recent_games_count)

    synergy = {}

    for game in games:
        rank = game["gameRank"]

        for member in game.get("teamUser", []):
            if member.get("userNum") == uid:
                continue

            char_code = member.get("characterNum")
            if not char_code:
                continue

            if char_code not in synergy:
                synergy[char_code] = {
                    "games": 0,
                    "total_rank": 0,
                    "wins": 0
                }

            synergy[char_code]["games"] += 1
            synergy[char_code]["total_rank"] += rank

            if rank == 1:
                synergy[char_code]["wins"] += 1

    result = []

    for char, data in synergy.items():
        if data["games"] < 5:
            continue

        avg_rank = data["total_rank"] / data["games"]
        win_rate = data["wins"] / data["games"]

        result.append({
            "character": CHARACTER_MAP.get(char, f"코드{char}"),
            "games": data["games"],
            "avg_rank": round(avg_rank, 2),
            "win_rate": round(win_rate * 100, 1)
        })

    if not result:
        return [], []

    # 평균등수 안정적 상위 2
    stable = sorted(result, key=lambda x: x["avg_rank"])[:2]

    # 승률 높은 상위 2
    high_win = sorted(result, key=lambda x: x["win_rate"], reverse=True)[:2]

    return stable, high_win


# -----------------------------
# 자화상 종합 분석
# -----------------------------
def evaluate_self_player(nickname):

    uid = get_uid(nickname)

    # 시즌은 analyzer 내부 로직과 동일하게 처리
    season_id = get_recent_games(uid)[0]["seasonId"]
    stats = get_season_stats(uid, season_id)
    recent = get_recent_games(uid, 10)

    score, strengths, major_risks, minor_risks = calculate_score(stats, recent)

    stable_chars, high_win_chars = analyze_team_synergy(uid)

    return {
        "nickname": nickname,
        "score": score,
        "strengths": strengths,
        "major_risks": major_risks,
        "minor_risks": minor_risks,
        "stable_chars": stable_chars,
        "high_win_chars": high_win_chars
    }
