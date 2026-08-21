/** ルーティング定義と共通レイアウト。 */

import { useEffect } from "react";
import { Link, NavLink, Route, Routes, useLocation, useNavigationType } from "react-router-dom";
import { GithubIcon } from "./components/Icons";
import { ThemeToggle } from "./components/ThemeToggle";
import { AboutPage } from "./pages/AboutPage";
import { GameDetailPage } from "./pages/GameDetailPage";
import { ModelDetailPage } from "./pages/ModelDetailPage";
import { RankingPage } from "./pages/RankingPage";

const REPO_URL = "https://github.com/solidtnd/llm-reversi";

/**
 * ページ遷移のたびに先頭までスクロールする。
 *
 * react-routerはSPA内の遷移でスクロール位置を維持するため、対局詳細を下まで
 * スクロールしてからランキングへ戻ると、戻り先も途中から表示されてしまう。
 * ブラウザの戻る/進む(popstate)はブラウザ自身が位置を復元するので対象外にする。
 */
function ScrollToTop() {
  const { pathname, search } = useLocation();
  const navigationType = useNavigationType();

  useEffect(() => {
    if (navigationType === "POP") return;
    window.scrollTo(0, 0);
  }, [pathname, search, navigationType]);

  return null;
}

export function App() {
  return (
    <>
      <ScrollToTop />
      <header className="topbar">
        <div className="shell topbar__inner">
          <Link className="mark" to="/">
            <span className="mark__glyph" aria-hidden="true" />
            LLMリバーシ対戦記録
          </Link>
          <nav className="topbar__actions">
            <NavLink className="topbar__link" to="/about">
              {/* 狭い画面ではヘッダーのタイトルが折り返すため、ラベルを短くする */}
              <span className="topbar__link-long">指標 · 対局条件について</span>
              <span className="topbar__link-short">指標について</span>
            </NavLink>
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
