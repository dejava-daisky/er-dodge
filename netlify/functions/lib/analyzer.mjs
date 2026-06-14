const BASE_URL = "https://open-api.bser.io";
const REQUEST_INTERVAL_MS = 1100;
const REQUEST_TIMEOUT_MS = 10000;
let currentSeasonIdCache = null;

export class AnalyzerError extends Error {}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function safeGet(path, params = {}) {
  const apiKey = process.env.ER_API_KEY;
  if (!apiKey) {
    throw new AnalyzerError("서버에 API 키가 설정되지 않았습니다.");
  }

  const url = new URL(path, BASE_URL);
  Object.entries(params).forEach(([key, value]) => {
    url.searchParams.set(key, String(value));
  });

  let response;
  try {
    response = await fetch(url, {
      headers: { "x-api-key": apiKey },
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });
  } catch (error) {
    if (error?.name === "TimeoutError") {
      throw new AnalyzerError(
        "전적 서버 응답이 지연되고 있습니다. 잠시 후 다시 시도해 주세요.",
      );
    }
    throw new AnalyzerError("전적 서버에 연결하지 못했습니다.");
  } finally {
    await delay(REQUEST_INTERVAL_MS);
  }

  if (response.status === 403 || response.status === 429) {
    throw new AnalyzerError("조회 요청이 많습니다. 잠시 후 다시 시도해 주세요.");
  }
  if (response.status === 404) {
    throw new AnalyzerError("플레이어 또는 전적을 찾을 수 없습니다.");
  }
  if (response.status >= 500) {
    throw new AnalyzerError("전적 서버에 일시적인 문제가 발생했습니다.");
  }

  let data;
  try {
    data = await response.json();
  } catch {
    throw new AnalyzerError("전적 서버가 올바르지 않은 응답을 보냈습니다.");
  }

  if (!response.ok || (data.code != null && data.code !== 200)) {
    throw new AnalyzerError("전적을 조회하지 못했습니다. 닉네임을 확인해 주세요.");
  }
  return data;
}

async function getUid(nickname) {
  const data = await safeGet("/v1/user/nickname", { query: nickname });
  const uid = data.user?.userId ?? data.user?.uid;
  if (!uid) {
    throw new AnalyzerError("해당 닉네임의 플레이어를 찾을 수 없습니다.");
  }
  return uid;
}

async function getGames(uid) {
  const data = await safeGet(`/v1/user/games/uid/${uid}`);
  if (!Array.isArray(data.userGames)) {
    throw new AnalyzerError("경기 기록을 불러오지 못했습니다.");
  }
  return data.userGames;
}

function getRankSeasonFromGames(games) {
  const game = games.find(
    (item) => Number(item.matchingMode) === 3 && Number(item.seasonId) > 0,
  );
  return game ? Number(game.seasonId) : null;
}

async function getCurrentSeasonId() {
  if (currentSeasonIdCache != null) return currentSeasonIdCache;

  const data = await safeGet("/v2/data/Season");
  if (!Array.isArray(data.data)) {
    throw new AnalyzerError("현재 시즌 정보를 불러오지 못했습니다.");
  }

  const current = data.data.find((season) => Number(season.isCurrent) === 1);
  const seasonId = Number(current?.seasonID ?? current?.seasonId);
  if (!Number.isInteger(seasonId) || seasonId <= 0) {
    throw new AnalyzerError("현재 시즌 정보를 찾을 수 없습니다.");
  }

  currentSeasonIdCache = seasonId;
  return currentSeasonIdCache;
}

async function getSeasonStats(uid, seasonId) {
  const data = await safeGet(`/v2/user/stats/uid/${uid}/${seasonId}/3`);
  if (!Array.isArray(data.userStats) || !data.userStats.length) {
    throw new AnalyzerError("해당 시즌의 랭크 통계를 찾을 수 없습니다.");
  }
  return data.userStats[0];
}

function recentRankGames(games, seasonId, count = 20) {
  return games
    .filter(
      (game) =>
        Number(game.matchingMode) === 3 &&
        Number(game.seasonId) === Number(seasonId),
    )
    .slice(0, count);
}

function formatIngameSeason(seasonId) {
  const internalId = Number(seasonId);
  if (!Number.isInteger(internalId)) return "시즌 정보 없음";

  // Open API counts nine legacy seasons before the current in-game numbering.
  const internalSeason = Math.floor(internalId / 2) + 1;
  const ingameSeason = internalSeason - 9;
  if (ingameSeason <= 0) return `레거시 시즌 (ID ${internalId})`;
  return `${internalId % 2 === 0 ? "프리시즌" : "시즌"} ${ingameSeason}`;
}

function scoutingActivity(game) {
  return [
    "useSecurityConsole",
    "addSurveillanceCamera",
    "addTelephotoCamera",
    "removeSurveillanceCamera",
    "removeTelephotoCamera",
  ].reduce((sum, field) => sum + (Number(game[field]) || 0), 0);
}

function validateStats(stats) {
  if (!Number.isFinite(Number(stats?.totalGames)) || Number(stats.totalGames) <= 0) {
    throw new AnalyzerError("분석할 수 있는 랭크 전적이 없습니다.");
  }
  if (!Array.isArray(stats.characterStats) || !stats.characterStats.length) {
    throw new AnalyzerError("캐릭터 통계가 없어 분석할 수 없습니다.");
  }
  if (stats.averageRank == null || stats.totalWins == null) {
    throw new AnalyzerError("분석에 필요한 통계가 부족합니다.");
  }
}

function calculateScore(stats, recentGames) {
  validateStats(stats);

  const totalGames = Number(stats.totalGames);
  const averageRank = Number(stats.averageRank);
  const winRate = Number(stats.totalWins) / totalGames;
  const top3 = Number(stats.top3) || 0;
  const mostUsed = Math.max(
    ...stats.characterStats.map((character) => Number(character.totalGames) || 0),
  );
  const mostUsedRatio = mostUsed / totalGames;
  const breakdown = new Map();
  let score = 0;

  const rankScore =
    averageRank <= 3.3 ? 15 : averageRank <= 3.8 ? 12 : averageRank <= 4.3 ? 8 : averageRank <= 4.8 ? 4 : 0;
  const rankRule =
    rankScore === 15
      ? "3.3위 이하"
      : rankScore === 12
        ? "3.8위 이하"
        : rankScore === 8
          ? "4.3위 이하"
          : rankScore === 4
            ? "4.8위 이하"
            : "4.8위 초과";
  breakdown.set("평균 순위", [rankScore, 15, `${averageRank.toFixed(2)}위 · ${rankRule}`]);
  score += rankScore;

  const winScore =
    winRate >= 0.22 ? 15 : winRate >= 0.18 ? 12 : winRate >= 0.14 ? 8 : winRate >= 0.1 ? 4 : 0;
  const winRule =
    winScore === 15
      ? "22% 이상"
      : winScore === 12
        ? "18% 이상"
        : winScore === 8
          ? "14% 이상"
          : winScore === 4
            ? "10% 이상"
            : "10% 미만";
  breakdown.set("승률", [winScore, 15, `${(winRate * 100).toFixed(1)}% · ${winRule}`]);
  score += winScore;

  const top3Score =
    top3 >= 0.6 ? 15 : top3 >= 0.5 ? 12 : top3 >= 0.4 ? 8 : top3 >= 0.3 ? 4 : 0;
  const top3Rule =
    top3Score === 15
      ? "60% 이상"
      : top3Score === 12
        ? "50% 이상"
        : top3Score === 8
          ? "40% 이상"
          : top3Score === 4
            ? "30% 이상"
            : "30% 미만";
  breakdown.set("상위권 진입", [
    top3Score,
    15,
    `TOP 3 ${(top3 * 100).toFixed(1)}% · ${top3Rule}`,
  ]);
  score += top3Score;

  let focusScore = 3;
  if (totalGames >= 50) {
    focusScore =
      mostUsedRatio >= 0.25 && mostUsedRatio <= 0.45
        ? 10
        : mostUsedRatio > 0.45 && mostUsedRatio <= 0.6
          ? 8
          : mostUsedRatio > 0.6
            ? 5
            : mostUsedRatio >= 0.15
              ? 7
              : 4;
  }
  const focusDetail =
    totalGames < 50
      ? `${totalGames}판 · 50판 미만 표본`
      : mostUsedRatio > 0.6
        ? `${(mostUsedRatio * 100).toFixed(1)}% · 원챔 성향`
        : mostUsedRatio < 0.15
          ? `${(mostUsedRatio * 100).toFixed(1)}% · 이것저것 성향`
          : mostUsedRatio <= 0.25
            ? `${(mostUsedRatio * 100).toFixed(1)}% · 15~25% 구간`
            : mostUsedRatio <= 0.45
              ? `${(mostUsedRatio * 100).toFixed(1)}% · 권장 집중 구간`
              : `${(mostUsedRatio * 100).toFixed(1)}% · 45~60% 구간`;
  breakdown.set("캐릭터 집중도", [focusScore, 10, focusDetail]);
  score += focusScore;

  let averageRecentRank = null;
  let averageRecentDamage = null;
  let formScore = 0;
  let recentRankScore = 0;
  let recentDamageScore = 0;
  if (recentGames.length) {
    averageRecentRank =
      recentGames.reduce((sum, game) => sum + (Number(game.gameRank) || 9), 0) /
      recentGames.length;
    averageRecentDamage =
      recentGames.reduce((sum, game) => sum + (Number(game.damageToPlayer) || 0), 0) /
      recentGames.length;

    recentRankScore =
      averageRecentRank <= 3.3
        ? 20
        : averageRecentRank <= 4
          ? 15
          : averageRecentRank <= 4.7
            ? 9
            : averageRecentRank <= 5.3
              ? 4
              : 0;
    recentDamageScore =
      averageRecentDamage >= 13000
        ? 20
        : averageRecentDamage >= 11000
          ? 15
          : averageRecentDamage >= 9000
            ? 10
            : averageRecentDamage >= 7500
              ? 5
              : 0;
    formScore = recentRankScore + recentDamageScore;
  }
  const formDetail = recentGames.length
    ? `평균 ${averageRecentRank.toFixed(2)}위 +${recentRankScore}/20 · 피해량 ${Math.round(averageRecentDamage).toLocaleString("ko-KR")} +${recentDamageScore}/20`
    : "현재 시즌 최근 랭크 기록 없음";
  breakdown.set("최근 폼", [formScore, 40, formDetail]);
  score += formScore;

  let scoutingScore = 0;
  if (recentGames.length) {
    const averageScouting =
      recentGames.reduce((sum, game) => sum + scoutingActivity(game), 0) /
      recentGames.length;
    scoutingScore =
      averageScouting >= 6 ? 5 : averageScouting >= 4 ? 4 : averageScouting >= 2.5 ? 3 : averageScouting >= 1 ? 1 : 0;
  }
  const scoutingDetail = recentGames.length
    ? `경기당 평균 ${(
        recentGames.reduce((sum, game) => sum + scoutingActivity(game), 0) /
        recentGames.length
      ).toFixed(2)}회 · ${scoutingScore}점 구간`
    : "현재 시즌 최근 랭크 기록 없음";
  breakdown.set("시야·정찰 활동", [scoutingScore, 5, scoutingDetail]);
  score += scoutingScore;

  let penalties = 0;
  const penaltyReasons = [];
  if (totalGames >= 50) {
    if (winRate < 0.08) {
      penalties += 12;
      penaltyReasons.push("승률 8% 미만 -12");
    } else if (winRate < 0.1) {
      penalties += 7;
      penaltyReasons.push("승률 10% 미만 -7");
    }
  }
  if (recentGames.length) {
    if (recentGames.length >= 10) {
      if (averageRecentRank > 5.8) {
        penalties += 10;
        penaltyReasons.push(`최근 평균 ${averageRecentRank.toFixed(2)}위 -10`);
      } else if (averageRecentRank > 5.3) {
        penalties += 5;
        penaltyReasons.push(`최근 평균 ${averageRecentRank.toFixed(2)}위 -5`);
      }
      if (averageRecentDamage < 7000) {
        penalties += 8;
        penaltyReasons.push(
          `최근 피해량 ${Math.round(averageRecentDamage).toLocaleString("ko-KR")} -8`,
        );
      } else if (averageRecentDamage < 8000) {
        penalties += 4;
        penaltyReasons.push(
          `최근 피해량 ${Math.round(averageRecentDamage).toLocaleString("ko-KR")} -4`,
        );
      }
    }
    if (averageRank > 5.2 && averageRecentRank > 5.8) {
      penalties += 8;
      penaltyReasons.push("시즌·최근 평균 순위 동시 저조 -8");
    }
    if (
      recentGames.length >= 20 &&
      recentGames.slice(0, 20).filter((game) => (Number(game.gameRank) || 9) <= 3).length < 4
    ) {
      penalties += 5;
      const recentTop3Count = recentGames
        .slice(0, 20)
        .filter((game) => (Number(game.gameRank) || 9) <= 3).length;
      penaltyReasons.push(`최근 20경기 TOP 3 ${recentTop3Count}회 -5`);
    }
  }

  const baseScore = score;
  const rawPenalties = penalties;
  penalties = Math.min(penalties, 25);
  score = Math.max(0, score - penalties);
  if (penalties) {
    breakdown.set("위험 감점", [
      -penalties,
      25,
      `${penaltyReasons.join(" · ")}${rawPenalties > 25 ? " · 최대 -25 적용" : ""}${baseScore < penalties ? " · 최종 점수 0점 하한 적용" : ""}`,
    ]);
  }

  let weakest = null;
  let weakestRatio = Infinity;
  for (const [label, [value, maximum]] of breakdown) {
    const ratio = value / maximum;
    if (ratio < weakestRatio) {
      weakest = label;
      weakestRatio = ratio;
    }
  }

  const comments = {
    "평균 순위": "평균 순위가 아쉽습니다.",
    "승률": "승률이 낮습니다.",
    "상위권 진입": "상위권 진입 비율이 낮습니다.",
    "캐릭터 집중도": "캐릭터 사용 성향이 점수에 반영됐습니다.",
    "최근 폼": "최근 경기력이 불안합니다.",
    "시야·정찰 활동": "최근 시야·정찰 활동이 부족합니다.",
    "위험 감점": "닷지를 고려할 위험 지표가 감지됐습니다.",
  };
  const scoreBreakdown = [...breakdown].map(([label, [value, maximum, detail]]) => ({
    label,
    score: value,
    maxScore: maximum,
    isPenalty: label === "위험 감점",
    detail,
  }));
  let comment = score >= 80 ? "전반적인 지표가 안정적입니다." : comments[weakest];
  if (score < 80 && weakest === "캐릭터 집중도") {
    if (totalGames < 50) {
      comment = "표본이 적어 캐릭터 성향을 판단하기 어렵습니다.";
    } else if (mostUsedRatio > 0.6) {
      comment = "한 캐릭터를 고집하는 원챔 성향입니다.";
    } else if (mostUsedRatio < 0.15) {
      comment = "여러 캐릭터를 이것저것 사용하는 성향입니다.";
    }
  }
  return [score, comment, scoreBreakdown];
}

function generateWarnings(stats, recentGames) {
  validateStats(stats);
  const warnings = [];
  const totalGames = Number(stats.totalGames);
  const winRate = Number(stats.totalWins) / totalGames;
  const top3 = Number(stats.top3) || 0;
  const top5 = Number(stats.top5) || 0;
  const top7 = Number(stats.top7) || 0;

  if (totalGames >= 50 && winRate < 0.08) warnings.push("낮은 승률");
  if (totalGames >= 50 && top7 - top5 >= 0.25 && top3 <= 0.3) {
    warnings.push("중반 탈락 빈번");
  }
  if (recentGames.length) {
    const averageRank =
      recentGames.reduce((sum, game) => sum + (Number(game.gameRank) || 9), 0) /
      recentGames.length;
    const averageDamage =
      recentGames.reduce((sum, game) => sum + (Number(game.damageToPlayer) || 0), 0) /
      recentGames.length;
    if (averageRank > 6) warnings.push("최근 평균 순위 위험");
    if (averageDamage < 7000) warnings.push("최근 피해량 부족");
    if (averageRank > 6 && averageDamage < 7000) warnings.push("최근 경기력 급락");
  }

  const mostUsed = Math.max(
    ...stats.characterStats.map((character) => Number(character.totalGames) || 0),
  );
  if (totalGames < 50) warnings.push("캐릭터 성향 데이터 부족");
  else if (mostUsed < 10) warnings.push("뚜렷한 주력 캐릭터 없음");
  return warnings;
}

function grade(score) {
  if (score >= 85) return "최고";
  if (score >= 70) return "좋음";
  if (score >= 50) return "보통";
  if (score >= 35) return "주의";
  return "닷지 권장";
}

function round(value, digits = 0) {
  const scale = 10 ** digits;
  return Math.round((value + Number.EPSILON) * scale) / scale;
}

export function cleanNickname(value) {
  if (typeof value !== "string") return [null, "닉네임은 문자열이어야 합니다."];
  const nickname = value.trim();
  if (!nickname) return [null, "닉네임을 입력해 주세요."];
  if ([...nickname].length > 30) return [null, "닉네임은 30자 이내로 입력해 주세요."];
  return [nickname, null];
}

export async function evaluatePlayer(nickname) {
  const uid = await getUid(nickname);
  const games = await getGames(uid);
  const season = getRankSeasonFromGames(games) ?? await getCurrentSeasonId();
  const stats = await getSeasonStats(uid, season);
  const recent = recentRankGames(games, season);
  const [score, comment, scoreBreakdown] = calculateScore(stats, recent);
  const totalGames = Number(stats.totalGames);
  const mostUsedGames = Math.max(
    ...stats.characterStats.map((character) => Number(character.totalGames) || 0),
  );

  return {
    nickname,
    score,
    grade: grade(score),
    comment,
    warnings: generateWarnings(stats, recent),
    scoreBreakdown,
    metrics: {
      seasonId: season,
      seasonLabel: formatIngameSeason(season),
      totalGames,
      winRate: round((Number(stats.totalWins) / totalGames) * 100, 1),
      averageRank: round(Number(stats.averageRank), 2),
      top3Rate: round((Number(stats.top3) || 0) * 100, 1),
      mainCharacterRate: round((mostUsedGames / totalGames) * 100, 1),
      recentGames: recent.length,
      recentAverageRank: recent.length
        ? round(recent.reduce((sum, game) => sum + (Number(game.gameRank) || 9), 0) / recent.length, 2)
        : null,
      recentAverageDamage: recent.length
        ? round(recent.reduce((sum, game) => sum + (Number(game.damageToPlayer) || 0), 0) / recent.length)
        : null,
      recentAverageScouting: recent.length
        ? round(recent.reduce((sum, game) => sum + scoutingActivity(game), 0) / recent.length, 2)
        : null,
    },
  };
}

export async function analyzeNickname(nickname) {
  try {
    return await evaluatePlayer(nickname);
  } catch (error) {
    if (!(error instanceof AnalyzerError)) console.error(error);
    return {
      nickname,
      error:
        error instanceof AnalyzerError
          ? error.message
          : "분석 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.",
    };
  }
}
