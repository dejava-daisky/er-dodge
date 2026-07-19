import http from "node:http";
import fs from "node:fs/promises";
import fsSync from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";

import analyzeHandler from "./netlify/functions/analyze.mjs";
import analyzeMeHandler from "./netlify/functions/analyze-me.mjs";
import feedbackHandler from "./netlify/functions/analyze-feedback.mjs";
import ocrHandler from "./netlify/functions/ocr.mjs";
import patchCharactersHandler from "./netlify/functions/patch-characters.mjs";
import patchCharacterHandler from "./netlify/functions/patch-character.mjs";
import { resetDakggStatsCache } from "./netlify/functions/lib/dakgg-stats.mjs";
import { resetPatchCache } from "./netlify/functions/lib/patches.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PUBLIC_DIR = path.join(__dirname, "public");

function loadDotEnv() {
  const envPath = path.join(__dirname, ".env");
  if (!fsSync.existsSync(envPath)) return;
  const text = fsSync.readFileSync(envPath, "utf8");
  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const separator = trimmed.indexOf("=");
    if (separator <= 0) continue;
    const key = trimmed.slice(0, separator).trim();
    let value = trimmed.slice(separator + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    if (!process.env[key]) process.env[key] = value;
  }
}

loadDotEnv();

const PORT = Number(process.env.PORT || 8888);
const HOST = process.env.HOST || "0.0.0.0";
const SIX_HOURS_MS = 6 * 60 * 60 * 1000;
const REFRESH_INTERVAL_MS = Number(process.env.STATS_REFRESH_INTERVAL_MS || SIX_HOURS_MS);
const REFRESH_ON_START = String(process.env.STATS_REFRESH_ON_START || "false").toLowerCase() === "true";

let refreshRunning = null;
let lastRefresh = null;

const API_ROUTES = new Map([
  ["POST /api/analyze", analyzeHandler],
  ["POST /analyze", analyzeHandler],
  ["POST /api/analyze/me", analyzeMeHandler],
  ["POST /analyze/me", analyzeMeHandler],
  ["POST /api/analyze/feedback", feedbackHandler],
  ["POST /analyze/feedback", feedbackHandler],
  ["POST /api/ocr", ocrHandler],
  ["GET /api/patches/characters", patchCharactersHandler],
  ["GET /api/patches/character", patchCharacterHandler],
]);

const MIME_TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
  ".ico": "image/x-icon",
  ".svg": "image/svg+xml",
  ".gz": "application/gzip",
};

function sendJson(res, status, body) {
  res.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store",
  });
  res.end(JSON.stringify(body));
}

function sendText(res, status, text) {
  res.writeHead(status, { "content-type": "text/plain; charset=utf-8" });
  res.end(text);
}

function isPathInside(parent, child) {
  const relative = path.relative(parent, child);
  return relative && !relative.startsWith("..") && !path.isAbsolute(relative);
}

function makeRequest(req, url) {
  const headers = new Headers();
  for (const [key, value] of Object.entries(req.headers)) {
    if (Array.isArray(value)) value.forEach((item) => headers.append(key, item));
    else if (value != null) headers.set(key, value);
  }
  const init = {
    method: req.method,
    headers,
  };
  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = req;
    init.duplex = "half";
  }
  return new Request(url, init);
}

async function writeWebResponse(res, response) {
  res.writeHead(response.status, Object.fromEntries(response.headers.entries()));
  if (!response.body) {
    res.end();
    return;
  }
  const buffer = Buffer.from(await response.arrayBuffer());
  res.end(buffer);
}

function runCommand(command, args, options = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd: __dirname,
      env: process.env,
      windowsHide: true,
      ...options,
    });
    let stdout = "";
    let stderr = "";
    child.stdout?.on("data", (chunk) => {
      stdout += chunk;
    });
    child.stderr?.on("data", (chunk) => {
      stderr += chunk;
    });
    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) resolve({ stdout, stderr });
      else reject(new Error(`${command} exited ${code}\n${stderr || stdout}`));
    });
  });
}

async function runPythonScript(args) {
  const candidates = [
    process.env.PYTHON_BIN,
    "python3",
    "python",
    "py",
  ].filter(Boolean);
  let lastError;
  for (const command of candidates) {
    try {
      const commandArgs = command === "py" ? ["-3", ...args] : args;
      return await runCommand(command, commandArgs);
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError || new Error("Python executable was not found.");
}

async function refreshDakggStats(reason = "scheduled") {
  if (refreshRunning) return refreshRunning;
  refreshRunning = (async () => {
    const startedAt = new Date().toISOString();
    console.log(`[refresh] DAK.GG stats started (${reason})`);
    const result = await runPythonScript(["scripts/collect_dakgg_stats.py"]);
    resetDakggStatsCache();
    lastRefresh = {
      ok: true,
      reason,
      startedAt,
      finishedAt: new Date().toISOString(),
      output: result.stdout.split(/\r?\n/).filter(Boolean).slice(-8),
    };
    console.log(`[refresh] DAK.GG stats finished (${reason})`);
    return lastRefresh;
  })()
    .catch((error) => {
      lastRefresh = {
        ok: false,
        reason,
        finishedAt: new Date().toISOString(),
        error: error.message,
      };
      console.warn("[refresh] DAK.GG stats failed:", error.message);
      throw error;
    })
    .finally(() => {
      refreshRunning = null;
    });
  return refreshRunning;
}

function scheduleStatsRefresh() {
  if (!Number.isFinite(REFRESH_INTERVAL_MS) || REFRESH_INTERVAL_MS <= 0) return;
  const tick = async () => {
    try {
      await refreshDakggStats("scheduled");
    } catch {
      // The lastRefresh object already carries the failure. Keep the server alive.
    } finally {
      setTimeout(tick, REFRESH_INTERVAL_MS).unref();
    }
  };
  setTimeout(tick, REFRESH_INTERVAL_MS).unref();
  if (REFRESH_ON_START) {
    setTimeout(() => tick(), 1000).unref();
  }
}

function checkAdminToken(req) {
  const token = process.env.ADMIN_REFRESH_TOKEN;
  if (!token) return false;
  const auth = req.headers.authorization || "";
  const bearer = auth.startsWith("Bearer ") ? auth.slice(7) : "";
  return bearer === token || req.headers["x-admin-token"] === token;
}

async function handleAdmin(req, res, url) {
  if (url.pathname === "/admin/refresh/stats" && req.method === "POST") {
    if (!checkAdminToken(req)) {
      return sendJson(res, 401, {
        error: "관리자 갱신 토큰이 필요합니다.",
        hint: "ADMIN_REFRESH_TOKEN을 설정하고 Authorization: Bearer 토큰으로 호출하세요.",
      });
    }
    try {
      const result = await refreshDakggStats("manual");
      return sendJson(res, 200, { refreshed: true, result });
    } catch (error) {
      return sendJson(res, 500, { refreshed: false, error: error.message });
    }
  }

  if (url.pathname === "/admin/refresh/patches" && req.method === "POST") {
    if (!checkAdminToken(req)) {
      return sendJson(res, 401, { error: "관리자 갱신 토큰이 필요합니다." });
    }
    resetPatchCache();
    return sendJson(res, 200, {
      refreshed: true,
      message: "패치 데이터 메모리 캐시를 비웠습니다. 데이터 파일 생성 작업은 별도 수집 스크립트가 필요합니다.",
    });
  }

  if (url.pathname === "/admin/refresh/status" && req.method === "GET") {
    return sendJson(res, 200, {
      running: Boolean(refreshRunning),
      lastRefresh,
      intervalMs: REFRESH_INTERVAL_MS,
    });
  }

  return false;
}

async function serveStatic(req, res, url) {
  const decodedPath = decodeURIComponent(url.pathname);
  const requested = decodedPath === "/" ? "/index.html" : decodedPath;
  const filePath = path.normalize(path.join(PUBLIC_DIR, requested));
  if (!isPathInside(PUBLIC_DIR, filePath) && filePath !== path.join(PUBLIC_DIR, "index.html")) {
    return sendText(res, 403, "Forbidden");
  }

  let target = filePath;
  if (!fsSync.existsSync(target)) {
    target = path.join(PUBLIC_DIR, "index.html");
  }
  try {
    const content = await fs.readFile(target);
    const ext = path.extname(target).toLowerCase();
    const isStaticAsset = target !== path.join(PUBLIC_DIR, "index.html");
    res.writeHead(200, {
      "content-type": MIME_TYPES[ext] || "application/octet-stream",
      "cache-control": isStaticAsset ? "public, max-age=3600" : "no-store",
    });
    res.end(content);
  } catch {
    sendText(res, 404, "Not Found");
  }
}

async function handleRequest(req, res) {
  const url = new URL(req.url || "/", `http://${req.headers.host || "localhost"}`);

  if (url.pathname === "/healthz") {
    return sendJson(res, 200, { ok: true, service: "er-dodge", lastRefresh });
  }

  const adminResult = await handleAdmin(req, res, url);
  if (adminResult !== false) return adminResult;

  const routeKey = `${req.method} ${url.pathname}`;
  const apiHandler = API_ROUTES.get(routeKey);
  if (apiHandler) {
    try {
      const response = await apiHandler(makeRequest(req, url));
      return writeWebResponse(res, response);
    } catch (error) {
      console.error("API handler failed:", error);
      return sendJson(res, 500, { error: "서버 처리 중 문제가 발생했습니다." });
    }
  }

  return serveStatic(req, res, url);
}

scheduleStatsRefresh();

http.createServer((req, res) => {
  handleRequest(req, res).catch((error) => {
    console.error("Unhandled request error:", error);
    sendJson(res, 500, { error: "서버 처리 중 문제가 발생했습니다." });
  });
}).listen(PORT, HOST, () => {
  console.log(`ER Dodge server listening on http://${HOST}:${PORT}`);
  console.log(`DAK.GG refresh interval: ${REFRESH_INTERVAL_MS}ms`);
});
