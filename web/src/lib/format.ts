/** 表示用の整形ヘルパ。 */

export function percent(value: number, digits = 0): string {
  return `${(value * 100).toFixed(digits)}%`;
}

export function points(value: number): string {
  return Number.isInteger(value) ? value.toFixed(0) : value.toFixed(1);
}

/** ミリ秒を「1.2秒」「840ms」のように読みやすくする。 */
export function duration(ms: number): string {
  if (ms <= 0) return "—";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}秒`;
}

/** トークン数などの整数に桁区切りを入れる。 */
export function count(value: number): string {
  return value.toLocaleString("en-US");
}

/**
 * USD建ての金額。桁が小さい概算値(1局分など)でも0にならないよう、
 * 大きさに応じて小数点以下の桁数を変える。
 */
export function usd(value: number): string {
  if (value >= 1) return `$${value.toFixed(2)}`;
  if (value >= 0.01) return `$${value.toFixed(3)}`;
  return `$${value.toFixed(4)}`;
}

/** 石数差(±付き)。0は「±0」と表示する。 */
export function stoneDiff(value: number): string {
  const rounded = Number(value.toFixed(2));
  if (rounded > 0) return `+${rounded}`;
  if (rounded < 0) return `${rounded}`;
  return "±0";
}

/** ISO8601をローカル時刻の「2026-01-10 12:34」形式にする。 */
export function dateTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  const pad = (value: number) => String(value).padStart(2, "0");
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ` +
    `${pad(date.getHours())}:${pad(date.getMinutes())}`
  );
}

/** 対局IDの末尾6桁(短縮表示用)。 */
export function shortGameId(gameId: string): string {
  const [, suffix] = gameId.split("-");
  return suffix ?? gameId;
}
