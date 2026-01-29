let token = "";
export async function request<T>(
  path: string,
  method = "GET",
  payload?: unknown,
): Promise<T> {
  if (method !== "GET" && !token) {
    const r = await fetch("/auth/csrf");
    token = (await r.json()).csrfToken;
  }
  const response = await fetch("/api" + path, {
    method,
    headers: { "Content-Type": "application/json", "X-CSRFToken": token },
    ...(payload !== undefined ? { body: JSON.stringify(payload) } : {}),
  });
  if (!response.ok) {
    let msg = "Request failed.";
    try {
      const e = await response.json();
      msg = typeof e.detail === "string" ? e.detail : JSON.stringify(e.detail);
    } catch {}
    if (response.status === 401) msg = "Sign in to save work.";
    throw Error(msg);
  }
  return response.json();
}
export async function authenticate(username: string, password: string) {
  const r = await fetch("/auth/csrf");
  token = (await r.json()).csrfToken;
  const res = await fetch("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRFToken": token },
    body: JSON.stringify({ username, password }),
  });
  const body = await res.json();
  if (!res.ok) throw Error(body.detail);
  token = body.csrfToken;
  return body.user as string;
}
export async function signOut() {
  const r = await fetch("/auth/csrf");
  token = (await r.json()).csrfToken;
  await fetch("/auth/logout", {
    method: "POST",
    headers: { "X-CSRFToken": token },
  });
  token = "";
}
