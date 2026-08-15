const TOKEN_KEY = "actuate_console_token";

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) || "";
}

export function setToken(token: string) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers || {}),
    },
    ...init,
  });
  if (response.status === 401) {
    window.dispatchEvent(new Event("actuate-auth"));
    throw new Error("401 Unauthorized — set the console token in Settings.");
  }
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
