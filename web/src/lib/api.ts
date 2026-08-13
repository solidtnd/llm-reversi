/**
 * `data/`配下のJSON取得ラッパ。
 *
 * - `ranking.json`は起動時に1回だけfetchし、全画面で共有する(モジュールレベルでキャッシュ)。
 * - 個別対局JSONは対局詳細ページを開いたときに初めてfetchする(全件の事前ロードはしない)。
 */

import { useEffect, useState } from "react";
import type { GameRecord, Ranking } from "./types";

const DATA_BASE = `${import.meta.env.BASE_URL.replace(/\/?$/, "/")}data`;

/** engineが生成する`game_id`の形式(`{UTC時刻}-{6桁hex}`)。URL経由の値を検証するために使う。 */
const GAME_ID_PATTERN = /^\d{8}T\d{12}-[0-9a-f]{6}$/;

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`${url} を読み込めませんでした (HTTP ${response.status})`);
  }
  return (await response.json()) as T;
}

let rankingPromise: Promise<Ranking> | null = null;

export function fetchRanking(): Promise<Ranking> {
  rankingPromise ??= getJson<Ranking>(`${DATA_BASE}/ranking.json`);
  return rankingPromise;
}

const gameCache = new Map<string, Promise<GameRecord>>();

export function fetchGame(gameId: string): Promise<GameRecord> {
  if (!GAME_ID_PATTERN.test(gameId)) {
    return Promise.reject(new Error(`対局IDの形式が不正です: ${gameId}`));
  }
  const cached = gameCache.get(gameId);
  if (cached) return cached;
  const promise = getJson<GameRecord>(`${DATA_BASE}/games/${gameId}.json`);
  gameCache.set(gameId, promise);
  return promise;
}

export interface AsyncState<T> {
  data: T | null;
  error: Error | null;
  loading: boolean;
}

function useAsync<T>(load: () => Promise<T>, key: string): AsyncState<T> {
  const [state, setState] = useState<AsyncState<T>>({
    data: null,
    error: null,
    loading: true,
  });

  useEffect(() => {
    let active = true;
    setState({ data: null, error: null, loading: true });
    load().then(
      (data) => {
        if (active) setState({ data, error: null, loading: false });
      },
      (error: unknown) => {
        if (active) {
          setState({
            data: null,
            error: error instanceof Error ? error : new Error(String(error)),
            loading: false,
          });
        }
      },
    );
    return () => {
      active = false;
    };
    // loadは呼び出し側で毎回生成されるため、keyで依存を表現する
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return state;
}

/** `ranking.json`を読み込む。 */
export function useRanking(): AsyncState<Ranking> {
  return useAsync(fetchRanking, "ranking");
}

/** 個別対局の棋譜JSONを読み込む。 */
export function useGame(gameId: string): AsyncState<GameRecord> {
  return useAsync(() => fetchGame(gameId), `game:${gameId}`);
}
