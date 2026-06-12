import { json } from "./lib/http.mjs";
import { listCharacters } from "./lib/patches.mjs";

export default async (request) => {
  if (request.method !== "GET") return json({ error: "허용되지 않은 요청입니다." }, 405);
  return json({ characters: listCharacters() });
};
