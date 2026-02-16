import os
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import requests

try:
    # 로컬에서는 .env가 있을 수 있으니(렌더에서는 환경변수)
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass


BASE_URL = "https://open-api.bser.io"
API_KEY = os.getenv("ER_API_KEY")

DEFAULT_TIMEOUT = 8
DEFAULT_RETRIES = 3
BACKOFF_BASE = 0.6


class ERAPIError(Exception):
    pass


def _build_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "accept": "application/json",
        "x-api-key": API_KEY or "",
    })
    return s


_SESSION = _build_session()


def _unwrap_payload(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    문서 기준:
    - 일반적으로 code/message/data 래퍼가 있음
    - 일부 엔드포인트는 data 대신 리소스별 키(userGames, userStats 등)를 최상위에 둘 수 있음
    따라서:
    - code가 있고 data가 있으면 data 우선
    - 그 외에는 원문 그대로 반환
    """
    if not isinstance(raw, dict):
        return {}

    # 래퍼 형태: {"code":200,"message":"Success","data":{...}}
    if "code" in raw and "data" in raw and isinstance(raw.get("data"), dict):
        return raw["data"]

    # 래퍼인데 data가 리스트/값인 경우도 있어 raw 유지
    return raw


def api_get(path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if not API_KEY:
        raise ERAPIError("ER_API_KEY 환경변수가 설정되어 있지 않습니다.")

    url = BASE_URL + path
    last_err = None

    for attempt in range(DEFAULT_RETRIES):
        try:
            r = _SESSION.get(url, params=params, timeout=DEFAULT_TIMEOUT)

            # 레이트리밋/권한 문제: 문서에서 403/429가 발생 가능 :contentReference[oaicite:8]{index=8}
            if r.status_code in (403, 429):
                retry_after = r.headers.get("Retry-After")
                wait = float(retry_after) if retry_after and retry_after.isdigit() else (BACKOFF_BASE * (2 ** attempt))
                time.sleep(wait)
                continue

            if r.status_code != 200:
                # 가능한 경우 본문 메시지까지 포함
                try:
                    j = r.json()
                except Exception:
                    j = {"raw": r.text[:200]}
                raise ERAPIError(f"API FAIL {r.status_code} {path} {j}")

            raw = r.json()

            # code가 있지만 성공이 아닐 수도 있음
            if isinstance(raw, dict) and "code" in raw and raw.get("code") != 200:
                raise ERAPIError(f"API WRAP FAIL {raw.get('code')} {path} {raw.get('message')}")

            return raw

        except Exception as e:
            last_err = e
            time.sleep(BACKOFF_BASE * (2 ** attempt))

    raise ERAPIError(f"API GET 재시도 실패: {path} ({last_err})")


# -----------------------
# UID 조회 (v1)
# -----------------------
def get_uid(nickname: str) -> Optional[str]:
    """
    /v1/user/nickname?query={nickname}
    문서 상 userNum 기반이 아니라 UID(userId)를 사용해야 함 :contentReference[oaicite:9]{index=9}
    """
    nickname = (nickname or "").strip()
    if not nickname:
        return None

    raw = api_get("/v1/user/nickname", {"query": nickname})
    payload = _unwrap_payload(raw)

    # 응답이 {"user": {...}} 형태로 오거나, 래퍼 data 안에 있을 수 있음
    user = payload.get("user") if isinstance(payload, dict) else None
    if not isinstance(user, dict):
        # 어떤 경우는 최상위에 user가 있을 수 있음
        user = raw.get("user") if isinstance(raw, dict) else None

    if not isinstance(user, dict):
        return None

    # 최신 문서 흐름: UID(userId) 요구. 보통 uid 키가 옴.
    uid = user.get("uid") or user.get("userId")
    if isinstance(uid, str) and uid.strip():
        return uid.strip()

    # 혹시 레거시 응답이 남아있는 경우를 위한 보완(하지만 주로 막혀 있음)
    legacy = user.get("userNum")
    if legacy is not None:
        return str(legacy)

    return None


# 기존 코드 호환
def get_user_uid(nickname: str) -> Optional[str]:
    return get_uid(nickname)


# -----------------------
# 최근 경기 목록 (v1)
# -----------------------
def get_recent_games(uid: str, limit: int = 20) -> List[Dict[str, Any]]:
    uid = (uid or "").strip()
    if not uid:
        return []

    raw = api_get(f"/v1/user/games/uid/{uid}")
    payload = _unwrap_payload(raw)

    # 어떤 엔드포인트는 userGames라는 리소스 키를 최상위에 둘 수 있음 :contentReference[oaicite:10]{index=10}
    games = None
    if isinstance(payload, dict):
        games = payload.get("userGames") or payload.get("games")
    if games is None and isinstance(raw, dict):
        games = raw.get("userGames") or raw.get("games")

    if not isinstance(games, list):
        return []

    # 최신순 가정, limit 적용
    return [g for g in games if isinstance(g, dict)][: max(0, int(limit))]


def _infer_season_id_from_games(games: List[Dict[str, Any]]) -> Optional[int]:
    if not games:
        return None
    sid = games[0].get("seasonId")
    try:
        return int(sid)
    except Exception:
        return None


# -----------------------
# 시즌 통계 (v2)
# -----------------------
def get_season_stats(uid: str, season_id: int, matching_mode: int = 3) -> Optional[Dict[str, Any]]:
    """
    /v2/user/stats/uid/{userId}/{seasonId}/{matchingMode}
    seasonId/matchingMode는 문서 기준을 따라야 함. :contentReference[oaicite:11]{index=11}
    """
    uid = (uid or "").strip()
    if not uid:
        return None

    raw = api_get(f"/v2/user/stats/uid/{uid}/{int(season_id)}/{int(matching_mode)}")
    payload = _unwrap_payload(raw)

    stats_list = None
    if isinstance(payload, dict):
        stats_list = payload.get("userStats")
    if stats_list is None and isinstance(raw, dict):
        stats_list = raw.get("userStats")

    if not isinstance(stats_list, list) or not stats_list:
        return None

    first = stats_list[0]
    return first if isinstance(first, dict) else None


def get_total_games(uid: str) -> int:
    """
    기존 analyzer.py는 season=3, mode=3 하드코딩이었는데(시즌이 바뀌면 바로 0판으로 보임),
    최근 게임의 seasonId를 따라가도록 수정.
    """
    games = get_recent_games(uid, limit=1)
    season_id = _infer_season_id_from_games(games)
    if season_id is None:
        return 0
    stats = get_season_stats(uid, season_id, matching_mode=3)
    if not stats:
        return 0
    try:
        return int(stats.get("totalGames", 0))
    except Exception:
        return 0


# -----------------------
# 점수 계산 (호환: games-only / (stats,recent) 둘 다 지원)
# -----------------------
def calculate_score(
    a: Union[List[Dict[str, Any]], Dict[str, Any], None],
    b: Optional[List[Dict[str, Any]]] = None
) -> Union[int, Tuple[int, List[str], List[str], List[str]]]:
    """
    - 기존 evaluate_player: calculate_score(games) -> int
    - self_analyzer: calculate_score(stats, recent) -> (score, strengths, major_risks, minor_risks)
      :contentReference[oaicite:12]{index=12}
    """
    # 형태1: games-only
    if isinstance(a, list) and b is None:
        games = a
        ranks = [g.get("gameRank") for g in games if g.get("gameRank")]
        ranks = [int(x) for x in ranks if isinstance(x, (int, float, str)) and str(x).isdigit()]
        if not ranks:
            return 0
        avg_rank = sum(ranks) / len(ranks)
        score = int(100 - avg_rank * 6)
        return max(0, min(score, 100))

    # 형태2: stats + recent
    stats = a if isinstance(a, dict) else {}
    recent = b if isinstance(b, list) else []

    strengths: List[str] = []
    major_risks: List[str] = []
    minor_risks: List[str] = []

    total_games = int(stats.get("totalGames", 0) or 0)
    wins = int(stats.get("wins", 0) or 0)
    top3 = int(stats.get("top3", 0) or 0)

    # 평균 등수
    avg_rank = stats.get("averageRank")
    try:
        avg_rank_f = float(avg_rank)
    except Exception:
        avg_rank_f = None

    score = 0

    if avg_rank_f is not None:
        if avg_rank_f <= 4.0:
            score += 15
            strengths.append("시즌 평균 등수가 낮아 안정적입니다.")
        elif avg_rank_f <= 4.3:
            score += 12
            strengths.append("시즌 평균 등수가 준수한 편입니다.")
        elif avg_rank_f <= 4.5:
            score += 8
            minor_risks.append("시즌 평균 등수가 약간 높습니다.")
        else:
            major_risks.append("시즌 평균 등수가 높아 기복이 큽니다.")

    # 승률
    win_rate = (wins / total_games) if total_games > 0 else 0.0
    if win_rate >= 0.18:
        score += 20
        strengths.append("승률이 높아 마무리 교전에 강합니다.")
    elif win_rate >= 0.14:
        score += 14
        strengths.append("승률이 준수합니다.")
    elif win_rate >= 0.10:
        score += 8
        minor_risks.append("승률이 약간 낮습니다.")
    else:
        major_risks.append("승률이 낮아 후반 마무리가 불안정할 수 있습니다.")

    # TOP3 비율
    top3_rate = (top3 / total_games) if total_games > 0 else 0.0
    if top3_rate >= 0.55:
        score += 15
        strengths.append("TOP3 비율이 높아 상위권 전환이 좋습니다.")
    elif top3_rate >= 0.45:
        score += 10
    elif top3_rate >= 0.35:
        score += 6
        minor_risks.append("TOP3 비율이 아주 높지는 않습니다.")
    else:
        major_risks.append("TOP3 비율이 낮아 상위권 유지가 어렵습니다.")

    # 실험체 숙련도(원트릭 성향) - characterStats 사용
    # 50판 이상 + 특정 실험체 usages 비율 40% 이상 :contentReference[oaicite:13]{index=13}
    if total_games >= 50:
        char_stats = stats.get("characterStats", [])
        if isinstance(char_stats, list) and char_stats:
            max_usage = 0
            max_char = None
            for cs in char_stats:
                if not isinstance(cs, dict):
                    continue
                usages = cs.get("usages")
                try:
                    u = int(usages)
                except Exception:
                    continue
                if u > max_usage:
                    max_usage = u
                    max_char = cs.get("characterCode")

            if max_usage / total_games >= 0.4:
                score += 10
                strengths.append("특정 실험체 숙련도가 높아 역할 수행이 안정적입니다.")
            elif max_char is not None:
                minor_risks.append("주력 실험체 비중이 분산되어 적응형일 수 있습니다.")

    # 최근 20경기 폼(평균 등수만 반영, 딜량은 정보만 수집) :contentReference[oaicite:14]{index=14}
    recent20 = recent[:20]
    recent_ranks = []
    recent_dmg = []
    for g in recent20:
        if not isinstance(g, dict):
            continue
        r = g.get("gameRank")
        if isinstance(r, (int, float)):
            recent_ranks.append(float(r))
        d = g.get("damageToPlayer")
        if isinstance(d, (int, float)):
            recent_dmg.append(float(d))

    if recent_ranks:
        r_avg = sum(recent_ranks) / len(recent_ranks)
        if r_avg <= 3.6:
            score += 15
            strengths.append("최근 20경기 폼이 매우 좋습니다.")
        elif r_avg <= 4.1:
            score += 10
        elif r_avg <= 4.6:
            score += 6
            minor_risks.append("최근 폼이 아주 안정적이진 않습니다.")
        else:
            major_risks.append("최근 20경기에서 하락세가 보입니다.")

    if recent_dmg:
        d_avg = sum(recent_dmg) / len(recent_dmg)
        # 점수에는 반영하지 않고 해석 문장만
        if d_avg >= 22000:
            strengths.append("최근 교전 기여(딜량)가 높은 편입니다.")
        elif d_avg <= 12000:
            minor_risks.append("최근 교전 기여(딜량)가 낮은 편일 수 있습니다.")

    # 표본 경고
    if total_games < 50:
        minor_risks.append("50판 미만이라 표본이 부족합니다.")

    # 점수 상한/하한
    score = max(0, min(int(score), 100))

    return score, strengths, major_risks, minor_risks


# -----------------------
# 최종 평가(팀원 초상화)
# -----------------------
def evaluate_player(nickname: str) -> Dict[str, Any]:
    nickname = (nickname or "").strip()
    if not nickname:
        return {"status": "닉네임 없음"}

    try:
        uid = get_uid(nickname)
        if not uid:
            return {"status": "닉네임 없음"}

        games = get_recent_games(uid, limit=20)
        if not games:
            return {"status": "전적 없음"}

        # 최근게임 기반 기본 점수 (기존 로직 유지)
        score_int = calculate_score(games)  # type: ignore[arg-type]

        # 색상 판정
        color = "orange"
        if score_int >= 70:
            color = "purple"
        elif score_int >= 50:
            color = "green"

        # 전체 판수: 시즌 하드코딩 제거
        total_games = get_total_games(uid)

        warning = None
        if total_games < 50:
            warning = "*50판 이하라서 결과가 부정확할 수 도있어, 참고만해,!!*"

        return {
            "nickname": nickname,
            "uid": uid,
            "score": int(score_int),
            "color": color,
            "recentGames": len(games),
            "totalGames": int(total_games),
            "warning": warning,
        }

    except ERAPIError as e:
        # 사용자에게는 과도한 내부 정보 대신, 검색 실패 사유를 “문장”처럼 짧게
        return {"status": f"검색 실패: {e}"}
    except Exception:
        return {"status": "검색 실패"}


# main.py 호환
analyze_player = evaluate_player
