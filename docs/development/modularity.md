# Modularity Rules

The codebase follows a 300-line soft limit for Python files. The limit is meant
to force clear module boundaries, not to encourage arbitrary splitting.

## File naming

File names should describe responsibility:

- `*_types.py` for dataclasses and type definitions;
- `*_serialization.py` for conversion to and from external schemas;
- `*_commands.py` for undoable command objects;
- `*_validators.py` for validation rules;
- `*_widgets.py` for Qt widget definitions;
- `*_services.py` for runtime coordination.

Avoid vague names such as `helpers.py` unless the helpers are local to one
module family and cannot be named more specifically.

## Splitting large files

When a file grows beyond the soft limit:

1. identify cohesive responsibility groups;
2. extract shared types before extracting behavior;
3. keep public compatibility modules small;
4. preserve existing imports when external callers depend on them;
5. add or update architecture tests when a new state-owner module is created.

## Docstrings and comments

Every source file should have a module docstring. Public classes and functions
should explain intent, parameters, return values, and side effects. Comments
should explain non-obvious control flow or performance choices, not repeat the
code line by line.

## GUI responsiveness

Do not put expensive computation in paint events, key handlers, or simple button
callbacks. Use workers, services, caches, or queued follow-up actions.
