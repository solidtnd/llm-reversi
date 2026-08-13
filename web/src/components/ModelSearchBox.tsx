/** モデル名・provider名での絞り込み入力(ランキング表で使用)。 */

interface Props {
  value: string;
  onChange: (value: string) => void;
  resultCount: number;
  totalCount: number;
}

export function ModelSearchBox({ value, onChange, resultCount, totalCount }: Props) {
  return (
    <div className="filters">
      <label className="field">
        <span className="field__label">絞り込み</span>
        <input
          type="search"
          value={value}
          placeholder="モデル名 / provider名"
          onChange={(event) => onChange(event.target.value)}
        />
      </label>
      <span className="muted" role="status">
        {resultCount === totalCount
          ? `${totalCount}モデル`
          : `${resultCount} / ${totalCount}モデルを表示`}
      </span>
    </div>
  );
}
