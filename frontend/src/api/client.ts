export class ApiError extends Error {
  status: number
  body: unknown

  constructor(status: number, body: unknown) {
    const message = typeof body === 'object' && body && 'detail' in body ? String(body.detail) : `API error ${status}`
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}

interface RequestOptions {
  body?: unknown
  params?: Record<string, string>
  signal?: AbortSignal
}

export async function request<T>(method: string, path: string, opts?: RequestOptions): Promise<T> {
  let url = `/api${path}`

  if (opts?.params) {
    const qs = new URLSearchParams(opts.params)
    url += `?${qs.toString()}`
  }

  const headers: Record<string, string> = {}
  const fetchOpts: RequestInit = {
    method,
    headers,
    credentials: 'same-origin',
    signal: opts?.signal,
  }

  if (opts?.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    fetchOpts.body = JSON.stringify(opts.body)
  }

  // Add Authorization header from localStorage as fallback (cookie is primary)
  const token = localStorage.getItem('vttd_auth_token')
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const res = await fetch(url, fetchOpts)

  if (!res.ok) {
    let body: unknown
    try {
      body = await res.json()
    } catch {
      body = { detail: res.statusText }
    }

    if (res.status === 401) {
      localStorage.removeItem('vttd_auth_token')
      localStorage.removeItem('vttd_auth_user')
    }

    throw new ApiError(res.status, body)
  }

  return (await res.json()) as T
}

/** Upload a file via FormData (for settings upload-reddit-cache). */
export async function uploadFile<T>(
  path: string,
  formData: FormData,
): Promise<T> {
  const url = `/api${path}`

  const headers: Record<string, string> = {}
  const token = localStorage.getItem('vttd_auth_token')
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const res = await fetch(url, {
    method: 'POST',
    headers,
    credentials: 'same-origin',
    body: formData,
  })

  if (!res.ok) {
    let body: unknown
    try {
      body = await res.json()
    } catch {
      body = { detail: res.statusText }
    }

    if (res.status === 401) {
      localStorage.removeItem('vttd_auth_token')
      localStorage.removeItem('vttd_auth_user')
    }

    throw new ApiError(res.status, body)
  }

  return (await res.json()) as T
}
