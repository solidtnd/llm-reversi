/** provider(OpenAI/Anthropic/Gemini)ごとのバッジ。 */

const PROVIDER_LABELS: Record<string, string> = {
  openai: "OpenAI",
  anthropic: "Anthropic",
  gemini: "Gemini",
};

export function providerLabel(provider: string): string {
  return PROVIDER_LABELS[provider] ?? provider;
}

interface Props {
  provider: string;
}

/**
 * 色は必ずラベル文字と併記する(色だけで識別させない)。
 * datavizスキルの検証済みパレットのうち、明度コントラストが3:1未満のスロットを
 * 含むため、テキストによる救済が必須。
 */
export function ProviderBadge({ provider }: Props) {
  const known = provider in PROVIDER_LABELS;
  return (
    <span className={`badge badge--${known ? provider : "unknown"}`}>
      <span className="badge__dot" aria-hidden="true" />
      {providerLabel(provider)}
    </span>
  );
}
