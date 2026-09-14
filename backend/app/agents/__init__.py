"""Model-backed steps.

Each module here is one job, one prompt and one JSON schema. They are the only
place in the codebase that talks to a model, and they never decide their own
confidence -- ``tools.hitl`` does that from the evidence they return.

- ``rule_matcher`` which playbook rules govern which clauses (one batched call)
- ``compliance``   does this clause breach this rule, and what wording says so
- ``redliner``     replacement text for a clause, covering every rule it breaches

Prompts and schemas live in ``app.llm.prompts``; the client wrapper that owns
timeouts, retries and JSON parsing lives in ``app.llm.client``.
"""
