import { analyzeNickname, cleanNickname } from "./lib/analyzer.mjs";
import { json, readJsonBody } from "./lib/http.mjs";

export default async (request) => {
  if (request.method !== "POST") return json({ error: "허용되지 않은 요청입니다." }, 405);
  const data = await readJsonBody(request);
  const [nickname, error] = cleanNickname(data?.nickname);
  if (error) return json({ error }, 400);
  return json({ result: await analyzeNickname(nickname) });
};
