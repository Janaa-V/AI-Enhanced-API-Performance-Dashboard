// Settings read once at startup, so a missing or wrong value fails loudly instead of
// surfacing later as a confusing network error.

export function parseApiUrl(raw: string | undefined): string {
  if (!raw) {
    throw new Error('VITE_API_URL is not set. Copy frontend/.env.example to frontend/.env.')
  }
  let url: URL
  try {
    url = new URL(raw)
  } catch {
    throw new Error(`VITE_API_URL is not a valid URL: ${raw}`)
  }
  if (url.protocol !== 'http:' && url.protocol !== 'https:') {
    throw new Error(`VITE_API_URL must start with http:// or https://: ${raw}`)
  }
  // No trailing slash, so paths join as `${API_URL}/metrics`.
  return url.href.replace(/\/+$/, '')
}

export const API_URL = parseApiUrl(import.meta.env.VITE_API_URL)
