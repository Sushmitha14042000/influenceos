const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

async function parseResponse(response) {
  const contentType = response.headers.get('content-type') || ''
  const data = contentType.includes('application/json') ? await response.json() : await response.text()
  if (!response.ok) {
    const detail = typeof data === 'object' && data && 'detail' in data ? data.detail : data
    throw new Error(String(detail || 'Request failed'))
  }
  return data
}

export async function get(path) {
  const response = await fetch(`${API_BASE}${path}`)
  return parseResponse(response)
}

export async function postForm(path, formFields = {}) {
  const form = new FormData()
  Object.entries(formFields).forEach(([key, value]) => {
    form.append(key, value)
  })

  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    body: form
  })
  return parseResponse(response)
}

export async function postFile(path, file) {
  const form = new FormData()
  form.append('file', file)

  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    body: form
  })
  return parseResponse(response)
}
