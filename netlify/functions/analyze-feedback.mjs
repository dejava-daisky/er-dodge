import { json, readJsonBody } from "./lib/http.mjs";

const DEFAULT_MODEL = "models/gemini-flash-lite-latest";

function finite(value) {
  return Number.isFinite(Number(value));
}

function niaTone(value) {
  return String(value || "")
    .trim()
    .replaceAll("확인됩니다.", "확인돼.")
    .replaceAll("부족합니다.", "부족해.")
    .replaceAll("있습니다.", "있어.")
    .replaceAll("없습니다.", "없어.")
    .replaceAll("합니다.", "해.")
    .replaceAll("습니다.", "어.")
    .replaceAll("보세요.", "봐.")
    .replaceAll("하세요.", "해.")
    .replaceAll("주세요.", "줘.")
    .replaceAll("됩니다.", "돼.");
}

function compactPlayerForAi(result) {
  const comparison = result?.comparison || {};
  return {
    nickname: result?.nickname,
    grade: result?.grade,
    score: result?.score,
    analysisStatus: result?.analysisStatus,
    comment: result?.comment,
    warnings: result?.warnings || [],
    metrics: result?.metrics || {},
    scoreBreakdown: result?.scoreBreakdown || [],
    tierComparison: {
      tierLabel: comparison?.tierLabel,
      sourcePatch: comparison?.sourcePatch,
      periodDays: comparison?.periodDays,
    },
    characterComparison: (comparison?.characters || []).slice(0, 5),
  };
}

function buildPrompt(result) {
  const payload = compactPlayerForAi(result);
  return `
[Role]
You are an Eternal Return ranked-match coach.

[Goal]
Return Korean JSON only. Give exactly one next-game action and zero to three major problems.

[Data rules]
- Use only the provided player data.
- Distinguish season totals from the recent ranked-game sample.
- Do not treat a season-level weakness as a current weakness if the recent metrics clearly improved.
- If the evidence is weak, say so in limitations or use insufficient_data.
- If there is no serious issue, use no_issue and still give one helpful next-game action.
- Do not force exactly three problems. Return only evidence-backed problems. If there are only one or two, return one or two.
- Do not add filler problems such as "additional sample needed" just to fill the list.
- Choose the next-game action from the largest meaningful deduction in scoreBreakdown.
- Do not default to vision, camera, console, or scouting advice unless 시야점수 is the largest or clearly tied largest problem.
- If the bigger issue is average rank, TOP3, win rate, character damage, or conversion after fights, the action must address routing, fight timing, disengage timing, finishing, or character execution instead of vision.
- Vision is only one possible cause. Do not use it as a generic explanation for every weak result.

[Nia tone rules for personal record analysis]
- 짧고 건조한 반말을 사용한다.
- 사용자의 전적을 함께 리플레이해 보는 게이머처럼 말한다.
- 수치를 그대로 반복하지 말고, 그 수치가 플레이에서 무엇을 의미하는지 설명한다.
- 반드시 관찰 → 해석 → 다음 판 행동 순서로 작성한다.
- 문제점을 말하고 끝내지 말고, 다음 경기에서 의식할 구체적인 행동을 제시한다.
- 한 번에 너무 많은 것을 고치게 하지 말고 가장 중요한 행동 1개를 먼저 제시한다.
- 사용자를 비난하거나 실력이 나쁘다고 단정하지 않는다.
- 표본이 부족하면 억지로 결론 내리지 않는다.
- 게임 용어는 자연스럽게 쓰되 모든 문장을 밈처럼 만들지 않는다.
- 존댓말, 장황한 상담체, 과장된 칭찬은 피한다.
- “낮습니다”, “부족합니다”처럼 현상만 말하고 끝내지 않는다.

[Sentence examples]
- “피해량은 충분한데 평균 순위가 낮아. 교전은 잘 열지만, 빠져나올 타이밍을 놓치는 것 같아. 다음 판에는 첫 교전이 끝난 뒤 바로 다음 동선을 정해.”
- “TOP3 진입은 자주 하는데 승리 전환이 적어. 후반까지 가는 힘은 있으니까, 마지막 교전 전에 팀원 위치와 탈출 경로를 한 번 확인해.”
- “승률과 평균 순위가 같이 낮아. 한 번의 실수보다 초반 운영부터 계속 손해를 보는 흐름에 가까워. 다음 판에는 첫 오브젝트 전까지 불필요한 교전을 피하는 것만 의식해.”
- “최근 피해량이 시즌 평균보다 떨어졌어. 캐릭터 숙련도 문제라기보다 최근 교전 진입이 늦어진 쪽에 가까워 보여. 다음 판에는 팀원이 먼저 맞기 전에 사거리 안으로 들어가.”
- “시야 활동이 같은 티어 평균보다 낮아. 교전 실력과 별개로 정보 없이 싸우는 판이 많다는 뜻이야. 이동할 때 카메라나 콘솔을 한 번 더 확인해.”
- “최근 기록이 시즌 전체보다 좋아졌어. 지금 바꾼 플레이는 효과가 있는 것 같아. 당장은 새 문제를 만들기보다 이 흐름을 10판 더 유지해.”

[Required JSON schema]
{
  "analysisStatus": "critical_issue | minor_issues | no_issue | insufficient_data",
  "primaryWeakness": null | {"title": "string", "observation": "string", "interpretation": "string"},
  "issues": [{"title": "string", "observation": "string", "interpretation": "string"}],
  "nextGameFeedback": {
    "message": "가장 먼저 바꿀 행동",
    "timing": "언제 실행할지",
    "reason": "그렇게 판단한 핵심 근거",
    "successCheck": "몇 경기 뒤 무엇을 확인할지"
  }
}

[Player data]
${JSON.stringify(payload, null, 2)}
`;
}

function extractJson(text) {
  const source = String(text || "").trim().replace(/^```(?:json)?/i, "").replace(/```$/i, "").trim();
  const start = source.indexOf("{");
  const end = source.lastIndexOf("}");
  if (start < 0 || end <= start) throw new Error("Gemini response did not contain JSON.");
  return JSON.parse(source.slice(start, end + 1));
}

async function callGemini(result) {
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) return null;
  const model = process.env.GEMINI_MODEL || DEFAULT_MODEL;
  const response = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/${model}:generateContent?key=${encodeURIComponent(apiKey)}`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        contents: [{ parts: [{ text: buildPrompt(result) }] }],
        generationConfig: {
          temperature: 0.25,
          responseMimeType: "application/json",
        },
      }),
      signal: AbortSignal.timeout(Number(process.env.GEMINI_TIMEOUT_SECONDS || 25) * 1000),
    },
  );
  if (!response.ok) throw new Error(`Gemini ${response.status}`);
  const data = await response.json();
  const text = data?.candidates?.[0]?.content?.parts?.map((part) => part.text || "").join("") || "";
  return extractJson(text);
}

function fallbackAnalysis(result) {
  const breakdown = Array.isArray(result?.scoreBreakdown) ? result.scoreBreakdown : [];
  const ranked = breakdown
    .map((item) => ({
      label: item.label || "지표",
      deduction: finite(item.deduction)
        ? Number(item.deduction)
        : Math.max(0, Number(item.maxScore || 0) - Number(item.score || 0)),
      detail: item.detail || "",
    }))
    .filter((item) => item.deduction >= 5)
    .sort((a, b) => b.deduction - a.deduction);
  const primary = ranked[0];
  const actionByLabel = {
    승률: "초반 손해를 줄이고 TOP3 이후 마무리 각을 먼저 봐.",
    TOP3: "첫 오브젝트 전까지 불필요한 교전은 한 번 참아.",
    평균순위: "첫 교전이 끝나면 바로 다음 동선을 정해.",
    시야점수: "이동 전에 카메라나 콘솔을 한 번 더 확인해.",
    "캐릭터 성과": "주력 캐릭터로 첫 교전 진입 타이밍을 한 박자 빠르게 잡아.",
  };
  const problemDetail = (item) => {
    const detail = item.detail ? ` 근거는 이거야. ${item.detail}` : "";
    const templates = {
      승률:
        `승률 감점이 제일 무겁게 잡혔어. 한두 판 실수보다, 초반 손해가 우승각까지 가는 판을 줄이는 흐름에 가까워.${detail} 다음 판엔 첫 오브젝트 전까지 불필요한 교전을 피하는 것만 먼저 의식해.`,
      TOP3:
        `TOP3 쪽에서 상위권 진입 흐름이 흔들려. 싸움을 못 한다기보다, 초중반에 체력이나 동선을 잃고 후반 선택지가 줄어드는 쪽일 수 있어.${detail} 다음 판엔 첫 오브젝트 전까지 무리한 교전을 한 번만 참아.`,
      평균순위:
        `평균순위가 무거워. 교전을 열었는지보다, 교전 이후 회복과 다음 동선에서 손해를 보는 흐름일 수 있어.${detail} 다음 판엔 첫 교전이 끝나면 파밍을 더 하기 전에 안전 구역과 다음 오브젝트부터 봐.`,
      시야점수:
        `시야 쪽에서 정보 없이 움직이는 판이 섞여 있어. 교전 실력 문제가 아니라, 싸우기 전에 필요한 정보를 덜 들고 들어가는 쪽에 가까워.${detail} 다음 판엔 이동 전에 카메라나 콘솔을 한 번만 더 확인해.`,
      "캐릭터 성과":
        `주력 캐릭터 성과가 같은 티어 기대값보다 낮게 잡혔어. 캐릭터를 못 한다고 단정할 건 아니고, 최근 교전에서 딜을 넣는 타이밍이나 진입 각이 늦는 흐름일 수 있어.${detail} 다음 판엔 팀원이 먼저 맞기 전에 사거리 안으로 들어가는지만 확인해.`,
    };
    return templates[item.label] || `${item.label}에서 크게 깎였어.${detail} 다음 판엔 이 지표 하나만 먼저 의식해.`;
  };
  return {
    nextAction: {
      message: primary ? (actionByLabel[primary.label] || `${primary.label}부터 하나만 의식해.`) : "지금 흐름은 크게 건드리지 말고 10판 더 유지해.",
      timing: "다음 랭크 경기",
      reason: primary ? `${primary.label} 감점이 제일 커. ${primary.detail}` : "뚜렷하게 큰 감점 항목은 없어.",
      successCheck: "다음 10경기 뒤 평균순위와 TOP3가 같이 좋아지는지 확인해.",
    },
    problems: ranked.slice(0, 3).map((item) => ({
      title: `${item.label} 점검`,
      detail: problemDetail(item),
    })),
  };
}

function compactFeedback(analysis, result) {
  if (!analysis) return fallbackAnalysis(result);
  const primary = analysis.primaryWeakness;
  const issues = Array.isArray(analysis.issues) ? analysis.issues : [];
  const problems = [];
  if (primary?.observation || primary?.interpretation) {
    problems.push({
      title: niaTone(primary.title || "핵심 문제"),
      detail: niaTone(primary.observation || primary.interpretation),
    });
  }
  for (const issue of issues) {
    if (problems.length >= 3) break;
    if (!issue?.observation && !issue?.interpretation) continue;
    problems.push({
      title: niaTone(issue.title || "점검 항목"),
      detail: niaTone(issue.observation || issue.interpretation),
    });
  }
  const next = analysis.nextGameFeedback || {};
  return {
    nextAction: {
      message: niaTone(next.message || "다음 판에서 확인할 행동을 하나 정해 봐."),
      timing: niaTone(next.timing || "다음 랭크 경기"),
      reason: niaTone(next.reason || "현재 지표에서 바로 확인 가능한 행동을 우선 추적해."),
      successCheck: niaTone(next.successCheck || "경기 후 실행했는지 보면 돼."),
    },
    problems,
  };
}

export default async (request) => {
  if (request.method !== "POST") return json({ error: "허용되지 않은 요청입니다." }, 405);
  const data = await readJsonBody(request);
  if (!data || typeof data.result !== "object") {
    return json({ error: "분석 결과 데이터가 필요합니다." }, 400);
  }
  if (data.result.error) {
    return json({ error: "오류 결과에는 피드백을 만들 수 없습니다." }, 400);
  }
  try {
    const analysis = await callGemini(data.result);
    return json({ feedback: compactFeedback(analysis, data.result) });
  } catch (error) {
    console.warn("Gemini feedback unavailable:", error.message);
    return json({ feedback: fallbackAnalysis(data.result) });
  }
};
