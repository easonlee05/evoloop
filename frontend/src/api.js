const API_BASE = import.meta.env.VITE_API_BASE || '';
const DEFAULT_TIMEOUT_MS = 12000;

async function fetchWithTimeout(url, options = {}, timeoutMs = DEFAULT_TIMEOUT_MS) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

export function apiUrl(path) {
  return `${API_BASE}${path}`;
}

export async function apiGet(path, fallback) {
  try {
    const res = await fetchWithTimeout(apiUrl(path));
    if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`);
    return await res.json();
  } catch (error) {
    console.warn(error);
    return fallback;
  }
}

export async function apiUpload(path, file, fallback) {
  try {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetchWithTimeout(apiUrl(path), {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) throw new Error(`UPLOAD ${path} failed: ${res.status}`);
    return await res.json();
  } catch (error) {
    console.warn(error);
    return fallback;
  }
}

export async function apiPost(path, body, fallback) {
  try {
    const res = await fetchWithTimeout(apiUrl(path), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {}),
    });
    if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`);
    return await res.json();
  } catch (error) {
    console.warn(error);
    return fallback;
  }
}

export async function apiPut(path, body, fallback) {
  try {
    const res = await fetchWithTimeout(apiUrl(path), {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {}),
    });
    if (!res.ok) throw new Error(`PUT ${path} failed: ${res.status}`);
    return await res.json();
  } catch (error) {
    console.warn(error);
    return fallback;
  }
}

export async function apiDelete(path, fallback) {
  try {
    const res = await fetchWithTimeout(apiUrl(path), { method: 'DELETE' });
    if (!res.ok) throw new Error(`DELETE ${path} failed: ${res.status}`);
    return await res.json();
  } catch (error) {
    console.warn(error);
    return fallback;
  }
}

export { API_BASE };
