const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...init?.headers,
    },
    cache: "no-store",
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(payload.detail ?? "Request failed");
  }
  return response.json() as Promise<T>;
}

export async function apiWithEtag<T>(path: string): Promise<{ data: T; etag: string | null }> {
  const response = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!response.ok) throw new Error("Unable to load the current record");
  return { data: await response.json() as T, etag: response.headers.get("etag") };
}

export const workspacePath = (ay: string, customerId: string) =>
  `/api/assessment-years/${ay}/customers/${customerId}`;

export async function downloadApiFile(path: string): Promise<void> {
  const response = await fetch(`${API_URL}${path}`, { method: "POST" });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: "Download failed" }));
    throw new Error(payload.detail ?? "Download failed");
  }
  const disposition = response.headers.get("content-disposition") ?? "";
  const filename = disposition.match(/filename="([^"]+)"/)?.[1] ?? "tax-workpaper.pdf";
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a");
  anchor.href = url; anchor.download = filename; anchor.click();
  URL.revokeObjectURL(url);
}
