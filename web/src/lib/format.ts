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
