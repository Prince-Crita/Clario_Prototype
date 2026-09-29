"""Cross-cutting building blocks with no knowledge of Clario features.

Rules (enforced by import-linter): `clario.core` imports nothing else from `clario` and no web
framework. Everything here is plain Python + SQLAlchemy + stdlib, reusable by every layer.
"""
