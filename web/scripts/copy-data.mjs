/**
 * リポジトリ直下の `data/` を `web/public/data/` へコピーするビルド前処理。
 *
 * シンボリックリンクはOS間の差異・CI環境での扱いが面倒なため使わない
 * (docs/web/web-architecture.md「データ取り込み方式」)。`npm run dev` / `npm run build`
 * の前に自動実行される(package.jsonのpredev/prebuild)。
 */
import { cp, mkdir, rm, stat } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const webDir = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const source = resolve(webDir, "..", "data");
const target = resolve(webDir, "public", "data");

const exists = async (path) => {
  try {
    await stat(path);
    return true;
  } catch {
    return false;
  }
};

if (!(await exists(source))) {
  console.error(
    `data/ が見つかりません: ${source}\n` +
      "engine 側で対局を実行するか、engine/tests/generate_dummy_data.py でダミーデータを生成してください。",
  );
  process.exit(1);
}

await rm(target, { recursive: true, force: true });
await mkdir(dirname(target), { recursive: true });
await cp(source, target, { recursive: true });

console.log(`data/ をコピーしました: ${source} -> ${target}`);
