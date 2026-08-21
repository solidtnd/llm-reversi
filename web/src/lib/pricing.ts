/**
 * モデル別のAPI単価表(100万トークンあたりUSD)。
 *
 * `data/`配下のJSONは金額を持たず、トークン数だけを持つ(docs/shared/log-schema.md)。
 * 表示用の金額はこの単価表と掛けてWeb側で算出する。engine側で算出すると、単価改定の
 * たびに集計をやり直して`data/`をコミットし直すことになるため。
 *
 * 値は docs/engine/models.md の調査結果(各社の公式pricingページ調べ)をそのまま
 * 転記している。**単価は変わるため、表示する際は必ず`PRICING_AS_OF`(調査時点)と
 * 公式ページへのリンクを併記する。**
 */

/** 単価表の調査時点。表示に必ず添える。 */
export const PRICING_AS_OF = "2026年8月";

export interface ModelPrice {
  /** 入力(prompt)100万トークンあたりUSD */
  input: number;
  /** 出力(completion)100万トークンあたりUSD */
  output: number;
}

/** provider別の公式料金ページ(単価の一次情報)。 */
export const PRICING_URLS: Record<string, string> = {
  openai: "https://openai.com/api/pricing/",
  anthropic: "https://www.anthropic.com/pricing",
  gemini: "https://ai.google.dev/gemini-api/docs/pricing",
};

/** `ranking.json`の`models[].id`(= engineの`models.yaml`のid)をキーにする。 */
const PRICES: Record<string, ModelPrice> = {
  "gpt-4o-mini": { input: 0.15, output: 0.6 },
  "gpt-4o": { input: 2.5, output: 10.0 },
  "gpt-5.6-luna": { input: 0.2, output: 1.2 },
  "gpt-5.6-terra": { input: 2.0, output: 12.0 },
  "gpt-5.6-sol": { input: 5.0, output: 30.0 },
  "claude-haiku-4-5": { input: 1.0, output: 5.0 },
  "claude-sonnet-4-5": { input: 3.0, output: 15.0 },
  "claude-sonnet-5": { input: 2.0, output: 10.0 },
  "claude-opus-5": { input: 5.0, output: 25.0 },
  "gemini-3.1-flash-lite": { input: 0.25, output: 1.5 },
  "gemini-3.5-flash": { input: 1.5, output: 9.0 },
  "gemini-2.5-flash": { input: 0.3, output: 2.5 },
};

/** 単価が分からないモデル(単価表に載せる前に対戦したモデル等)はnullを返す。 */
export function priceOf(modelId: string): ModelPrice | null {
  return PRICES[modelId] ?? null;
}

/** トークン数から概算のAPI利用料(USD)を求める。単価不明ならnull。 */
export function estimateUsd(
  modelId: string,
  promptTokens: number,
  completionTokens: number,
): number | null {
  const price = priceOf(modelId);
  if (!price) return null;
  return (promptTokens * price.input + completionTokens * price.output) / 1_000_000;
}

/**
 * 金額が概算にとどまる理由。トークン数の記録側の制約なので、料金を出す画面には
 * この注記を必ず添える(docs/shared/log-schema.mdの`tokens`の項と対応)。
 */
export const ESTIMATE_CAVEAT =
  "リトライで失敗した呼び出し分のトークンは記録に残らないため含まれていません。" +
  "キャッシュ割引・バッチ割引・無料枠も考慮していないため、実際の請求額とは一致しません。";
