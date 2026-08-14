/** ルーティング定義(3ルート)と共通レイアウト。 */

import { Link, Route, Routes } from "react-router-dom";
import { GithubIcon } from "./components/Icons";
import { ThemeToggle } from "./components/ThemeToggle";
import { AboutPage } from "./pages/AboutPage";
import { GameDetailPage } from "./pages/GameDetailPage";
import { ModelDetailPage } from "./pages/ModelDetailPage";
import { RankingPage } from "./pages/RankingPage";

const REPO_URL = "https://github.com/solidtnd/llm-reversi";

export function App() {
  return (
    <>
      <header className="topbar">
        <div className="shell topbar__inner">
          <Link className="mark" to="/">
            <span className="mark__glyph" aria-hidden="true" />
            LLMリバーシ対戦記録
          </Link>
          <span className="topbar__meta">ルールはアルゴリズム、着手はLLM</span>
          <nav className="topbar__actions">
            <ThemeToggle />
            <a
              className="icon-button"
              href={REPO_URL}
              target="_blank"
              rel="noreferrer"
              aria-label="GitHubリポジトリ"
            >
              <GithubIcon />
            </a>
          </nav>
        </div>
      </header>

      <main className="shell page">
        <Routes>
          <Route path="/" element={<RankingPage />} />
          <Route path="/about" element={<AboutPage />} />
          <Route path="/models/:modelId" element={<ModelDetailPage />} />
          <Route path="/games/:gameId" element={<GameDetailPage />} />
          <Route
            path="*"
            element={
              <p className="state">
                ページが見つかりません。
                <br />
                <Link to="/">ランキングへ戻る</Link>
              </p>
            }
          />
        </Routes>
      </main>

      <footer className="footer">
        <div className="shell">
          対局データは <span className="mono">data/</span> のJSONをそのまま読み込んで表示しています。
          {" · "}
          <Link to="/about">指標 · 対局条件について</Link>
        </div>
      </footer>
    </>
  );
}
