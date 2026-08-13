/** 手送り・自動再生の操作。キーボード操作はGameDetailPage側で受ける。 */

interface Props {
  index: number;
  lastIndex: number;
  playing: boolean;
  onChange: (index: number) => void;
  onTogglePlay: () => void;
  /** 表示用のラベル(例: 「12手目 / 全60手」)。 */
  label: string;
}

export function ReplayControls({
  index,
  lastIndex,
  playing,
  onChange,
  onTogglePlay,
  label,
}: Props) {
  const atStart = index <= 0;
  const atEnd = index >= lastIndex;

  return (
    <div>
      <div className="controls">
        <button
          type="button"
          className="controls__button"
          onClick={() => onChange(0)}
          disabled={atStart}
          aria-label="開始局面へ"
        >
          |◀
        </button>
        <button
          type="button"
          className="controls__button"
          onClick={() => onChange(index - 1)}
          disabled={atStart}
          aria-label="1手戻る"
        >
          ◀
        </button>
        <button type="button" className="controls__button controls__button--primary" onClick={onTogglePlay}>
          {playing ? "停止" : "自動再生"}
        </button>
        <button
          type="button"
          className="controls__button"
          onClick={() => onChange(index + 1)}
          disabled={atEnd}
          aria-label="1手進む"
        >
          ▶
        </button>
        <button
          type="button"
          className="controls__button"
          onClick={() => onChange(lastIndex)}
          disabled={atEnd}
          aria-label="最終局面へ"
        >
          ▶|
        </button>
        <span className="controls__turn">{label}</span>
      </div>
      <input
        className="controls__slider"
        type="range"
        min={0}
        max={lastIndex}
        step={1}
        value={index}
        aria-label="手数"
        onChange={(event) => onChange(Number(event.target.value))}
      />
      <p className="muted" style={{ fontSize: 12, margin: "4px 0 0" }}>
        ←→キーで1手ずつ、Home/Endで最初と最後、スペースで自動再生を切り替えます。
      </p>
    </div>
  );
}
