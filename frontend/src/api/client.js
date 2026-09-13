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

export const reviewContract = (contractText) =>
  request('/api/review', {
    method: 'POST',
    body: JSON.stringify({ contract_text: contractText }),
  })
