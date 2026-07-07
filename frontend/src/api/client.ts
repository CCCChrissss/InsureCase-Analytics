export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api";

export function apiPath(path: string, params: Record<string, string | number | null | undefined> = {}): string {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== "") {
      query.set(key, String(value));
    }
  });
  const queryString = query.toString();
  return queryString ? `${path}?${queryString}` : path;
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    throw new Error(`API ${response.status}: ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export async function apiGetOptional<T>(path: string): Promise<T | null> {
  const response = await fetch(`${API_BASE}${path}`);
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`API ${response.status}: ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}
