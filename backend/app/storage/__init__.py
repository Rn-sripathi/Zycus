"""Persistence.

Every review and its findings are written to Postgres, giving the tool an audit
trail: what the agent concluded about which contract, when, and which findings it
declined to act on.

Persistence is optional and best-effort. With no DATABASE_URL the pool never opens
and the app behaves exactly as before; if a write fails, the reviewer still gets
the findings already on their screen. Losing the audit trail is bad, but losing
the review a human is mid-way through reading is worse.

- ``db``       pool lifecycle and schema application
- ``reviews``  save, list, fetch and delete reviews
"""
