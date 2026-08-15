export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${await response.text()}`);
  }
  return (await response.json()) as T;
}

export type Provider = {
  id: string;
  name: string;
  models: string[];
  configured: boolean;
  default: string;
  env_key: string | null;
  api_base?: string;
};

export type RunSummary = {
  id: string;
  status: string;
  iterations: number;
  best_score: number | null;
  latency_seconds: number;
  tokens: number;
  started_at: number | null;
  specification_id: string;
  convergence: number | null;
  failure: string | null;
};
