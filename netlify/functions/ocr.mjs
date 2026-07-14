import { json } from "./lib/http.mjs";

const ALLOWED_TYPES = new Set(["image/png", "image/jpeg", "image/webp"]);
const MAX_FILE_SIZE = Number(process.env.OCR_MAX_FILE_SIZE || 5 * 1024 * 1024);
const DEFAULT_MODEL = "models/gemini-flash-lite-latest";

async function runGeminiOcr(bytes, mimeType) {
  const apiKey = process.env.OCR_GEMINI_API_KEY || process.env.GEMINI_API_KEY;
  if (!apiKey) throw new Error("이미지 인식용 API 키가 설정되어 있지 않습니다.");
  const model = process.env.OCR_GEMINI_MODEL || process.env.GEMINI_MODEL || DEFAULT_MODEL;
  const base64 = Buffer.from(bytes).toString("base64");
  const response = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/${model}:generateContent?key=${encodeURIComponent(apiKey)}`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        contents: [
          {
            parts: [
              {
                text: "이터널 리턴 팀원/플레이어 입력 화면입니다. 입력칸 안이나 오른쪽 아래에 보이는 플레이어 닉네임만 추출하세요. EMPTY, PLAYER, TEAM, RANK, 물음표 아이콘, 버튼 텍스트는 무시하세요. 닉네임 하나만 출력하세요. 설명하지 마세요.",
              },
              {
                inline_data: {
                  mime_type: mimeType,
                  data: base64,
                },
              },
            ],
          },
        ],
        generationConfig: { temperature: 0 },
      }),
      signal: AbortSignal.timeout(Number(process.env.OCR_TIMEOUT_SECONDS || 25) * 1000),
    },
  );
  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new Error(`Gemini ${response.status}: ${body.slice(0, 300)}`);
  }
  const data = await response.json();
  return (data?.candidates?.[0]?.content?.parts?.map((part) => part.text || "").join("") || "").trim();
}

export default async (request) => {
  if (request.method !== "POST") return json({ error: "허용되지 않은 요청입니다." }, 405);

  let formData;
  try {
    formData = await request.formData();
  } catch {
    return json({
      success: false,
      code: "INVALID_FORM_DATA",
      message: "이미지를 읽지 못했어. 한 번만 다시 붙여넣어 봐.",
    }, 400);
  }

  const image = formData.get("image");
  if (!(image instanceof File)) {
    return json({
      success: false,
      code: "IMAGE_REQUIRED",
      message: "인식할 이미지가 필요해.",
    }, 400);
  }

  if (!ALLOWED_TYPES.has(image.type)) {
    return json({
      success: false,
      code: "UNSUPPORTED_IMAGE_TYPE",
      message: "PNG, JPG, WEBP 이미지만 사용할 수 있어.",
    }, 400);
  }

  if (image.size > MAX_FILE_SIZE) {
    return json({
      success: false,
      code: "IMAGE_TOO_LARGE",
      message: "이미지 크기는 5MB 이하여야 해.",
    }, 400);
  }

  try {
    const bytes = new Uint8Array(await image.arrayBuffer());
    const text = await runGeminiOcr(bytes, image.type);
    return json({ success: true, text, engine: "gemini" });
  } catch (error) {
    console.warn("OCR unavailable:", error.message);
    return json({
      success: false,
      code: "OCR_FAILED",
      message: "이미지를 읽지 못했어. 한 번만 다시 붙여넣어 봐.",
    }, 500);
  }
};
