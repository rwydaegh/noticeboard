export async function request<T>(path: string): Promise<T> {
  const response = await fetch("/api" + path);
  if (!response.ok) throw Error("Request failed.");
  return response.json();
}
