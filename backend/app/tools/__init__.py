"""Deterministic tools.

Every module here is plain Python: no model, no network, no API key. Each one is
callable on its own and unit-tested in isolation, which is why the test suite runs
offline in under a second.

These are not helpers around the model. Two of them overrule it:

- ``numeric_gate`` settles a rule by arithmetic before the model is asked at all,
  and that verdict is what the top confidence tier means.
- ``vagueness`` pulls confidence down when a clause defers its substance
  elsewhere, regardless of how sure the model claims to be.

- ``segmenter``    contract text  -> numbered clauses
- ``numeric_gate`` clause + rule  -> arithmetic verdict, or "not extractable"
- ``vagueness``    clause text    -> the hedging phrases it relies on
- ``hitl``         evidence       -> confidence tier, severity, who decides
"""
