let csrf = "";
export async function api(path, options = {}) {
  const form = options.body instanceof FormData;
  const response = await fetch("/api" + path, {
    ...options,
    credentials: "same-origin",
    headers: {
      ...(!form && options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.method && options.method !== "GET"
        ? { "X-CSRF-Token": csrf }
        : {}),
      ...options.headers,
    },
    body: options.body && !form ? JSON.stringify(options.body) : options.body,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok)
    throw new Error(
      data.error || `No se pudo completar la solicitud (${response.status}).`,
    );
  if (data.csrf) csrf = data.csrf;
  return data;
}
export const post = (path, body = {}) => api(path, { method: "POST", body });
