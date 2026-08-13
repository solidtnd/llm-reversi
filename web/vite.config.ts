import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // GitHub Pagesのプロジェクトページ(https://<user>.github.io/<repo>/)でも
  // そのまま動くよう、アセット参照を相対パスにする。HashRouterと組み合わせるため
  // リポジトリ名をビルド時に知る必要がない。
  base: "./",
  server: { open: false },
  build: { outDir: "dist", sourcemap: false },
});
