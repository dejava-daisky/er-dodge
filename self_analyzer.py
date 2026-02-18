from analyzer import (
    get_uid,
    get_recent_games,
    get_season_stats,
    calc_score_and_comment
)
from collections import Counter

def evaluate_self_player(nickname):
    uid = get_uid(nickname)
    if not uid:
        return {"status": "닉네임 없음"}

    games = get_recent_games(uid, 50)
    if not games:
        return {"status": "전적 없음"}

    season_id = next((g["seasonId"] for g in games if g.get("seasonId")), None)
    stats = get_season_stats(uid, season_id)

    score, strength, weakness = calc_score_and_comment(stats)

    # 모스트 캐릭터
    chars = [g["characterNum"] for g in games if g.get("characterNum")]
    counter = Counter(chars)
    most_char, most_cnt = counter.most_common(1)[0]

    # 최근 10판 평균 등수
    recent_ranks = [g["gameRank"] for g in games[:10] if g.get("gameRank")]
    recent_avg_rank = sum(recent_ranks) / len(recent_ranks) if recent_ranks else 0

    season_avg_rank = stats.get("averageRank", 0)

    # 퍼센트 변환 (장인 비교용 더미 기준)
    percent_rank = min(100, int((3.2 / season_avg_rank) * 100)) if season_avg_rank else 0
    percent_damage = min(100, int(stats.get("averageDamage",0) / 18000 * 100))
    percent_team = min(100, int((stats.get("averageKill",0)+stats.get("averageAssist",0)) / 12 * 100))

    return {
        "nickname": nickname,
        "score": score,
        "games": stats.get("totalGames", 0),
        "mostChar": most_char,
        "mostCharGames": most_cnt,
        "strength": strength,
        "weakness": weakness,
        "recentAvgRank": round(recent_avg_rank,2),
        "seasonAvgRank": season_avg_rank,
        "percentRank": percent_rank,
        "percentDamage": percent_damage,
        "percentTeam": percent_team
    }
