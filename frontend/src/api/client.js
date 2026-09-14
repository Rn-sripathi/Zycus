// The only module that knows how to reach the backend.

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })

  if (!response.ok) {
    let detail = `Request failed (${response.status})`
    try {
      const body = await response.json()
      if (body?.detail) detail = body.detail
    } catch {
      // Response wasn't JSON; keep the status-based message.
    }
    throw new Error(detail)
  }

  return response.json()
}

export const getHealth = () => request('/api/health')
export const getPlaybook = () => request('/api/playbook')
export const getSamples = () => request('/api/samples')

export const reviewContract = (contractText, label = '') =>
  request(`/api/review?label=${encodeURIComponent(label)}`, {
    method: 'POST',
    body: JSON.stringify({ contract_text: contractText }),
  })

// History. These return empty / throw only when persistence is switched off.
export const listReviews = (limit = 25) => request(`/api/reviews?limit=${limit}`)
export const getReview = (id) => request(`/api/reviews/${id}`)

export const deleteReview = async (id) => {
  const response = await fetch(`/api/reviews/${id}`, { method: 'DELETE' })
  if (!response.ok && response.status !== 404) {
    throw new Error(`Could not delete review (${response.status})`)
  }
}

// Upload is multipart, so it bypasses the JSON helper above.
export const uploadContract = async (file) => {
  const form = new FormData()
  form.append('file', file)

  const response = await fetch('/api/extract', { method: 'POST', body: form })
  if (!response.ok) {
    let detail = `Could not read that file (${response.status})`
    try {
      const body = await response.json()
      if (body?.detail) detail = body.detail
    } catch {
      // Response wasn't JSON; keep the status-based message.
    }
    throw new Error(detail)
  }

  return response.json()
}
