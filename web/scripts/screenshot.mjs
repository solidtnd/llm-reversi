/**
 * デザイン確認用のスクリーンショット撮影スクリプト。
 *
 * 自動テスト(assertion付きe2e)ではなく、レイアウト崩れを目視確認するための
 * 撮影専用ツール。npm run build / CIには組み込まない
 * (docs/web/web-architecture.md「テスト方針」参照)。
 *
 * 使い方:
 *   npm run screenshot                    # 既定のビューポート・ルートを撮影
 *   npm run screenshot -- --dark          # ダークモードで撮影
 *   npm run screenshot -- --out <dir>     # 出力先を指定(既定: web/.tmp/screenshots)
 *
 * data/ から実際のモデルID・対局IDを取得して対局詳細・モデル詳細ページも撮影する。
 */
import { mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";
import { chromium } from "playwright";

const webDir = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2);
const dark = args.includes("--dark");
const outArgIndex = args.indexOf("--out");
const outDir = resolve(webDir, outArgIndex >= 0 ? args[outArgIndex + 1] : ".tmp/screenshots");
const port = 4173 + (dark ? 1 : 0);
const baseUrl = `http://localhost:${port}`;

const VIEWPORTS = [
  { name: "mobile-360", width: 360, height: 800 },
  { name: "mobile-390", width: 390, height: 844 },
  { name: "tablet-768", width: 768, height: 1024 },
  { name: "desktop-1280", width: 1280, height: 900 },
];

async function waitForServer(url, timeoutMs = 20000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(url);
      if (res.ok) return;
    } catch {
      // サーバ起動待ち
    }
    await new Promise((r) => setTimeout(r, 300));
  }
  throw new Error(`devサーバが起動しませんでした: ${url}`);
}

async function main() {
  await mkdir(outDir, { recursive: true });

  const server = spawn(
    "npm",
    ["run", "dev", "--", "--port", String(port), "--strictPort"],
    { cwd: webDir, shell: true, stdio: "ignore" },
  );

  try {
    await waitForServer(baseUrl);

    const rankingRes = await fetch(`${baseUrl}/data/ranking.json`);
    const ranking = await rankingRes.json();
    const modelId = ranking.models[0]?.id;
    const gameId = ranking.games[0]?.game_id;

    const routes = ["/", "/about"];
    if (modelId) routes.push(`/models/${encodeURIComponent(modelId)}`);
    if (gameId) routes.push(`/games/${encodeURIComponent(gameId)}`);

    const browser = await chromium.launch({ channel: "msedge" });
    const context = await browser.newContext({
      colorScheme: dark ? "dark" : "light",
    });
    const page = await context.newPage();

    for (const viewport of VIEWPORTS) {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      for (const route of routes) {
        await page.goto(`${baseUrl}/#${route}`, { waitUntil: "networkidle" });
        const slug = route === "/" ? "top" : route.replace(/[/#?]/g, "_");
        const fileName = `${viewport.name}${dark ? "-dark" : ""}${slug}.png`;
        await page.screenshot({
          path: resolve(outDir, fileName),
          fullPage: true,
        });
        console.log(`撮影: ${fileName}`);
      }
    }

    await browser.close();
    console.log(`保存先: ${outDir}`);
  } finally {
    server.kill();
  }
}

await main();
