# Contributing

Thanks for considering a contribution.

## Development setup

```bash
uv sync --extra dev
```

## Run checks

```bash
uv run ruff check .
uv run pytest
```

## What we accept

- Small, practical UX polish improvements
- Bug fixes with a clear repro and a test when feasible
- Documentation improvements (especially end-user focused)

## What we avoid

- Unnecessary abstractions / rewrites
- Changes to merge logic or GUI behavior without a strong reason

