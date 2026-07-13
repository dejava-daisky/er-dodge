import { json } from "./lib/http.mjs";
import { characterDetail } from "./lib/patches.mjs";

export default async (request) => {
  if (request.method !== "GET") return json({ error: "허용되지 않은 요청입니다." }, 405);
  const url = new URL(request.url);
  const pathName = decodeURIComponent(url.pathname.split("/").filter(Boolean).at(-1) || "");
  const name = (url.searchParams.get("name") || pathName)?.trim();
  if (!name) return json({ error: "캐릭터 이름이 필요합니다." }, 400);
  const detail = characterDetail(name);
  return detail
    ? json(detail)
    : json({ error: "캐릭터 패치 내역을 찾을 수 없습니다." }, 404);
};
