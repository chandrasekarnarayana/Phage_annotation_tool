# Contributing

Contributions should keep the repository professional, modular, and
reproducible.

## Before changing code

Read the module docstring, nearby tests, and architecture guardrails. Prefer the
existing patterns unless there is a strong reason to introduce a new one.

## Pull request checklist

- The change is scoped to one responsibility.
- New files have clear names and module docstrings.
- Public functions and classes have useful docstrings.
- No Python file exceeds the 300-line soft limit.
- Core/headless modules do not import Qt.
- Tests cover behavior, not only implementation details.
- Documentation is updated when user-visible behavior changes.

## Review priorities

Reviewers should prioritize correctness, data safety, reproducibility,
performance, and user workflow clarity.
