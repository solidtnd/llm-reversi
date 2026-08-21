/** 対局詳細: 棋譜リプレイ + 手ごとの生ログパネル。 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Board } from "../components/Board";
import { MoveLogPanel } from "../components/MoveLogPanel";
import { ProviderBadge } from "../components/ProviderBadge";
import { ReplayControls } from "../components/ReplayControls";
import { useGame } from "../lib/api";
import { INITIAL_BOARD, countStones } from "../lib/board";
import { count, dateTime, duration, usd } from "../lib/format";
import { PRICING_AS_OF, estimateUsd } from "../lib/pricing";
import {
  COLOR_LABELS,
  FORFEIT_REASON_LABELS,
  type Color,
  type GameRecord,
  type Move,
} from "../lib/types";

const PLAY_INTERVAL_MS = 700;

interface Frame {
  board: string;
  move: Move | null;
}

export function GameDetailPage() {
  const { gameId = "" } = useParams();
  const { data, error, loading } = useGame(gameId);
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);

  const frames: Frame[] = useMemo(() => {
    if (!data) return [{ board: INITIAL_BOARD, move: null }];
    return [
      { board: INITIAL_BOARD, move: null },
      ...data.moves.map((move) => ({ board: move.board_after, move })),
    ];
  }, [data]);

  const lastIndex = frames.length - 1;
  const clamp = useCallback(
    (value: number) => Math.max(0, Math.min(lastIndex, value)),
    [lastIndex],
  );

  // 初期盤面は全対局で同一なので、開いた直後は最終盤面を見せる
  // (棋譜を追いたい場合は矢印・スライダーで戻す)。lastIndexは棋譜の読み込み完了で確定する。
  useEffect(() => {
    setIndex(lastIndex);
    setPlaying(false);
  }, [gameId, lastIndex]);

  useEffect(() => {
    if (!playing) return;
    if (index >= lastIndex) {
      setPlaying(false);
      return;
    }
    const timer = window.setTimeout(() => setIndex((current) => clamp(current + 1)), PLAY_INTERVAL_MS);
    return () => window.clearTimeout(timer);
  }, [playing, index, lastIndex, clamp]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) return;
      if (event.key === "ArrowLeft") setIndex((current) => clamp(current - 1));
      else if (event.key === "ArrowRight") setIndex((current) => clamp(current + 1));
      else if (event.key === "Home") setIndex(0);
      else if (event.key === "End") setIndex(lastIndex);
      else if (event.key === " ") {
        event.preventDefault();
        setPlaying((current) => !current);
      } else return;
      if (event.key !== " ") setPlaying(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [clamp, lastIndex]);

  if (loading) return <p className="state">棋譜を読み込み中…</p>;
  if (error || !data) {
    return (
      <p className="state">
        棋譜を読み込めませんでした。{error?.message}
        <br />
        <Link to="/">ランキングへ戻る</Link>
      </p>
    );
  }

  const frame = frames[clamp(index)];
  const move = frame.move;
  const stones = countStones(frame.board);
  const turnColor: Color | null = move ? move.player : "black";

  return (
    <>
      <p className="breadcrumb">
        <Link to="/">ランキング</Link> /{" "}
        <Link to={`/models/${encodeURIComponent(data.players.black.id)}`}>
          {data.players.black.display_name}
        </Link>{" "}
        対{" "}
        <Link to={`/models/${encodeURIComponent(data.players.white.id)}`}>
          {data.players.white.display_name}
        </Link>
      </p>

      <header>
        <p className="eyebrow">対局詳細 · {dateTime(data.started_at)}</p>
        <h1>{resultHeadline(data)}</h1>
        <p className="lede">{resultDetail(data)}</p>
      </header>

      <section className="section">
        <div className="players">
          {(["black", "white"] as Color[]).map((color) => {
            const player = data.players[color];
            return (
              <div
                key={color}
                className={`player${turnColor === color ? " player--turn" : ""}`}
              >
                <div className="player__side">
                  <span
                    className={`scoreline__disc scoreline__disc--${color}`}
                    aria-hidden="true"
                  />
                  {color === "black" ? "先手 · 黒" : "後手 · 白"}
                </div>
                <Link className="player__name" to={`/models/${encodeURIComponent(player.id)}`}>
                  {player.display_name}
                </Link>
                <ProviderBadge provider={player.provider} />
                <div className="muted mono" style={{ fontSize: 12, marginTop: 6 }}>
                  {player.model}
                  {Object.keys(player.config).length > 0
                    ? ` · ${JSON.stringify(player.config)}`
                    : ""}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section className="section replay">
        <div>
          <Board
            board={frame.board}
            legalMoves={move?.legal_moves ?? []}
            playedPosition={move?.type === "move" ? move.position : null}
            illegalPosition={move?.forfeit_reason === "illegal_move" ? move.position : null}
          />
          <div className="scoreline">
            <span className="scoreline__side">
              <span className="scoreline__disc scoreline__disc--black" aria-hidden="true" />
              {stones.black}
            </span>
            <span className="scoreline__side">
              <span className="scoreline__disc scoreline__disc--white" aria-hidden="true" />
              {stones.white}
            </span>
            <span className="muted" style={{ fontSize: 12 }}>
              {move
                ? `${move.turn}手目まで`
                : "開始局面"}
            </span>
          </div>
          <ReplayControls
            index={clamp(index)}
            lastIndex={lastIndex}
            playing={playing}
            onChange={(next) => {
              setPlaying(false);
              setIndex(clamp(next));
            }}
            onTogglePlay={() => {
              // 既定表示が最終盤面なので、終端から再生した場合は頭から流す
              if (!playing && index >= lastIndex) setIndex(0);
              setPlaying((current) => !current);
            }}
            label={move ? `${move.turn}手目 / 全${data.moves.length}手` : `開始局面 / 全${data.moves.length}手`}
          />
        </div>

        <MoveLogPanel move={move} players={data.players} />
      </section>

      <section className="section">
        <div className="section__head">
          <h2>この対局の記録</h2>
          <span className="section__note mono">{data.game_id}</span>
        </div>
        <div className="rows card" style={{ padding: "4px 16px" }}>
          <div className="rows__row">
            <span className="rows__key">開始 / 終了</span>
            <span className="rows__value mono">
              {dateTime(data.started_at)} → {dateTime(data.ended_at)}
            </span>
          </div>
          <div className="rows__row">
            <span className="rows__key">手数</span>
            <span className="rows__value mono">
              {data.moves.length}手(うちパス {data.moves.filter((m) => m.type === "pass").length}回)
            </span>
          </div>
          <div className="rows__row">
            <span className="rows__key">平均応答時間</span>
            <span className="rows__value mono">
              黒 {duration(averageResponse(data, "black"))} / 白{" "}
              {duration(averageResponse(data, "white"))}
            </span>
          </div>
          <div className="rows__row">
            <span className="rows__key">使用トークン</span>
            <span className="rows__value mono">
              {(["black", "white"] as Color[]).map((color) => {
                const tokens = totalTokens(data, color);
                return (
                  <span key={color} style={{ display: "block" }}>
                    {COLOR_LABELS[color]} 入力 {count(tokens.prompt)} / 出力{" "}
                    {count(tokens.completion)}
                  </span>
                );
              })}
            </span>
          </div>
          <div className="rows__row">
            <span className="rows__key">概算利用料</span>
            <span className="rows__value">
              <span className="mono">
                {(["black", "white"] as Color[]).map((color) => {
                  const tokens = totalTokens(data, color);
                  const cost = estimateUsd(
                    data.players[color].id,
                    tokens.prompt,
                    tokens.completion,
                  );
                  return (
                    <span key={color} style={{ display: "block" }}>
                      {COLOR_LABELS[color]} {cost === null ? "—(単価不明)" : usd(cost)}
                    </span>
                  );
                })}
              </span>
              <span className="muted" style={{ fontSize: 12 }}>
                {PRICING_AS_OF}時点の単価による概算(単価はモデル詳細ページに記載)。
                リトライで失敗した呼び出し分のトークンは記録に含まれない。
              </span>
            </span>
          </div>
        </div>
      </section>
    </>
  );
}

function resultHeadline(game: GameRecord): string {
  if (game.result.winner === "draw") return "引き分け";
  const winner = game.players[game.result.winner];
  return `${winner.display_name} の勝ち`;
}

function resultDetail(game: GameRecord): string {
  const { result } = game;
  if (result.reason === "forfeit") {
    const lastMove = game.moves[game.moves.length - 1];
    const reason = lastMove?.forfeit_reason
      ? FORFEIT_REASON_LABELS[lastMove.forfeit_reason]
      : "不明";
    const loser = result.winner === "black" ? "white" : "black";
    return `${game.players[loser as Color].display_name}(${COLOR_LABELS[loser as Color]})の反則負け · 理由: ${reason}。反則負けは石数ではなく反則そのもので決着するため、石数は記録しません。`;
  }
  const score = result.score;
  return score
    ? `石数 ${score.black} - ${score.white} で決着(黒 - 白)。`
    : "石数で決着。";
}

/** その対局でその色が使ったトークン数の合計(`usage`がnullの手は加算しない)。 */
function totalTokens(game: GameRecord, color: Color): { prompt: number; completion: number } {
  let prompt = 0;
  let completion = 0;
  for (const move of game.moves) {
    if (move.player !== color || !move.usage) continue;
    prompt += move.usage.prompt_tokens;
    completion += move.usage.completion_tokens;
  }
  return { prompt, completion };
}

function averageResponse(game: GameRecord, color: Color): number {
  const times = game.moves
    .filter((move) => move.player === color && move.type !== "pass")
    .map((move) => move.response_time_ms);
  if (times.length === 0) return 0;
  return times.reduce((total, value) => total + value, 0) / times.length;
}
