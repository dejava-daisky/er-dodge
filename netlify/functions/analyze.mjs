import { analyzeNickname, cleanNickname } from "./lib/analyzer.mjs";
import { json, readJsonBody } from "./lib/http.mjs";

export default async (request) => {
  if (request.method !== "POST") return json({ error: "허용되지 않은 요청입니다." }, 405);
  const data = await readJsonBody(request);
  if (!data || !Array.isArray(data.nicknames) || data.nicknames.length < 1 || data.nicknames.length > 2) {
    return json({ error: "팀원 닉네임을 한 명 또는 두 명 입력해 주세요." }, 400);
  }

  const nicknames = [];
  for (const value of data.nicknames) {
    const [nickname, error] = cleanNickname(value);
    if (error) return json({ error: "닉네임을 올바르게 입력해 주세요." }, 400);
    nicknames.push(nickname);
  }
  if (nicknames.length === 2 && nicknames[0].toLocaleLowerCase() === nicknames[1].toLocaleLowerCase()) {
    return json({ error: "서로 다른 두 닉네임을 입력해 주세요." }, 400);
  }

  const results = [];
  for (const nickname of nicknames) {
    results.push(await analyzeNickname(nickname));
  }
  return json({ results });
};
