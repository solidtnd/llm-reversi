/** 手ごとの生ログ(LLMの生応答・反則理由・トークン数・応答時間)を表示する。 */

import type { ReactNode } from "react";
import { duration } from "../lib/format";
import {
  COLOR_LABELS,
  FORFEIT_REASON_LABELS,
  RETRIED_LABELS,
  type Move,
  type PlayerInfo,
} from "../lib/types";

interface Props {
  move: Move | null;
  players: Record<"black" | "white", PlayerInfo>;
}

const MOVE_TYPE_LABELS: Record<Move["type"], string> = {
  move: "着手",
  pass: "パス(合法手なし)",
  forfeit: "反則負け",
};

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="rows__row">
      <span className="rows__key">{label}</span>
      <span className="rows__value">{children}</span>
    </div>
  );
}

export function MoveLogPanel({ move, players }: Props) {
  if (!move) {
    return (
      <div className="card" style={{ padding: 16 }}>
        <h2>開始局面</h2>
        <p className="muted" style={{ margin: "8px 0 0" }}>
          標準の初期配置です。1手進めるとLLMのやり取りが表示されます。
        </p>
      </div>
    );
  }

  const player = players[move.player];
  const usage = move.usage;

  return (
    <div className="card" style={{ padding: 16 }}>
      <div className="section__head" style={{ marginBottom: 14 }}>
        <h2>
          {move.turn}手目 · {COLOR_LABELS[move.player]}
        </h2>
        <span className="section__note">{player.display_name}</span>
      </div>

      {move.type === "forfeit" && (
        <p className="notice">
          反則負け:{" "}
          {move.forfeit_reason ? FORFEIT_REASON_LABELS[move.forfeit_reason] : "不明"}
          {move.forfeit_reason === "illegal_move" && move.position
            ? `(${move.position} は合法手ではない)`
            : null}
        </p>
      )}

      <div className="rows">
        <Row label="種別">{MOVE_TYPE_LABELS[move.type]}</Row>
        <Row label="着手">
          <span className="mono">{move.position ?? "—"}</span>
        </Row>
        <Row label="合法手">
          <span className="mono">
            {move.legal_moves.length > 0 ? move.legal_moves.join(" ") : "なし"}
          </span>
        </Row>
        <Row label="応答時間">
          <span className="mono">{duration(move.response_time_ms)}</span>
        </Row>
        <Row label="リトライ">{RETRIED_LABELS[move.retried]}</Row>
        <Row label="トークン">
          {usage ? (
            <span className="mono">
              入力 {usage.prompt_tokens} / 出力 {usage.completion_tokens}
            </span>
          ) : (
            <span className="muted">レスポンスに含まれず</span>
          )}
        </Row>
        {move.error_detail && (
          <Row label="エラー詳細">
            <span className="mono">{move.error_detail}</span>
          </Row>
        )}
      </div>

      {move.llm_raw_response ? (
        <details className="raw">
          <summary>LLMの生応答を表示</summary>
          <pre className="raw__body">{formatRaw(move.llm_raw_response)}</pre>
        </details>
      ) : (
        <p className="muted" style={{ fontSize: 12, marginBottom: 0 }}>
          生応答なし(パスまたはレスポンス受信前の失敗)
        </p>
      )}
    </div>
  );
}

/** JSONとして読めれば整形して見せる(読めなければそのまま)。 */
function formatRaw(raw: string): string {
  try {
    return JSON.stringify(JSON.parse(raw), null, 2);
  } catch {
    return raw;
  }
}
