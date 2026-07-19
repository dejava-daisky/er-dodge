import fs from "node:fs";
import path from "node:path";

const LOWER_IS_BETTER_KEYWORDS = [
  "쿨다운",
  "재사용 대기",
  "소모량",
  "소모 ",
  "시전 시간",
  "선딜",
  "후딜",
  "딜레이",
  "충전 시간",
  "필요한 시간",
  "대기 시간",
];

function dataFile(name) {
  const candidates = [
    path.join(process.cwd(), "data", name),
    path.join(process.cwd(), "PROD", "data", name),
    path.resolve(path.dirname(new URL(import.meta.url).pathname), "../../../data", name),
  ];
  return candidates.find((candidate) => fs.existsSync(candidate)) ?? candidates[0];
}

function readJson(name) {
  return JSON.parse(fs.readFileSync(dataFile(name), "utf8"));
}

function classifyChange(text) {
  if (!text.includes("→")) return null;
  const [beforeText, afterText] = text.split("→", 2);
  const before = [...beforeText.matchAll(/-?\d+(?:\.\d+)?/g)].map((match) => Number(match[0]));
  const after = [...afterText.matchAll(/-?\d+(?:\.\d+)?/g)].map((match) => Number(match[0]));
  if (!before.length || !after.length) return null;

  const count = Math.min(before.length, after.length);
  const directions = new Set();
  for (let index = 0; index < count; index += 1) {
    const left = before[before.length - count + index];
    const right = after[after.length - count + index];
    if (right > left) directions.add(1);
    else if (right < left) directions.add(-1);
  }
  if (!directions.size) return null;

  if (LOWER_IS_BETTER_KEYWORDS.some((keyword) => beforeText.includes(keyword))) {
    const reversed = [...directions].map((direction) => -direction);
    directions.clear();
    reversed.forEach((direction) => directions.add(direction));
  }
  if (directions.size === 1 && directions.has(1)) return "buff";
  if (directions.size === 1 && directions.has(-1)) return "nerf";
  return "adjustment";
}

function classifyPatch(changes) {
  const labels = new Set(changes.map((change) => classifyChange(change.text)).filter(Boolean));
  if (!labels.size) return "adjustment";
  if (labels.size === 1 && labels.has("buff")) return "buff";
  if (labels.size === 1 && labels.has("nerf")) return "nerf";
  return "adjustment";
}

let cache;

function buildCache() {
  if (cache) return cache;
  const manifest = readJson("character_manifest.json").characters ?? {};
  const patchNotes = readJson("character_patches.json");
  const byCharacter = new Map();

  for (const note of patchNotes) {
    for (const entry of note.characters ?? []) {
      const changes = (entry.changes ?? []).map((change, index) => ({
        target: change.target ?? "",
        text: change.text ?? "",
        orderIndex: index,
      }));
      const patch = {
        patchVersion: note.patch_version,
        patchSeries: note.patch_series,
        title: note.title,
        publishedAt: note.published_at,
        updatedAt: note.updated_at,
        url: note.url,
        comment: entry.comment ?? "",
        changes,
        trend: classifyPatch(changes),
      };
      if (!byCharacter.has(entry.character)) byCharacter.set(entry.character, []);
      byCharacter.get(entry.character).push(patch);
    }
  }

  for (const patches of byCharacter.values()) {
    patches.sort((left, right) => String(right.publishedAt).localeCompare(String(left.publishedAt)));
  }

  const names = [...new Set([...Object.keys(manifest), ...byCharacter.keys()])].sort((a, b) =>
    a.localeCompare(b, "ko"),
  );
  const characters = names.map((name) => {
    const patches = byCharacter.get(name) ?? [];
    const latestTrend = patches[0]?.trend ?? null;
    let trendStreak = latestTrend ? 1 : 0;
    if (latestTrend === "buff" || latestTrend === "nerf") {
      for (const patch of patches.slice(1)) {
        if (patch.trend !== latestTrend) break;
        trendStreak += 1;
      }
    }
    return {
      name,
      thumbnail: manifest[name]?.thumbnail ?? null,
      resource: manifest[name]?.resource ?? null,
      patchCount: patches.length,
      changeCount: patches.reduce((sum, patch) => sum + patch.changes.length, 0),
      latestPatchAt: patches[0]?.publishedAt ?? null,
      latestTrend,
      trendStreak,
    };
  });

  cache = { manifest, byCharacter, characters };
  return cache;
}

export function listCharacters() {
  return buildCache().characters;
}

export function characterDetail(name) {
  const { manifest, byCharacter, characters } = buildCache();
  const character = characters.find((item) => item.name === name);
  if (!character && !manifest[name]) return null;
  return {
    character: character ?? {
      name,
      thumbnail: manifest[name]?.thumbnail ?? null,
      resource: manifest[name]?.resource ?? null,
      latestTrend: null,
      trendStreak: 0,
    },
    patches: byCharacter.get(name) ?? [],
  };
}

export function resetPatchCache() {
  cache = null;
}
