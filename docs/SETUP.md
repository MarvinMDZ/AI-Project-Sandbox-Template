# Setup

Verified commands only. If it is not confirmed to work, it does not belong here.

## Requirements

Everything ships in the devcontainer (see `README.md`); `bash .devcontainer/healthcheck.sh`
confirms it. Outside it: Node 22, pnpm, Python 3, uv, git, gh.

## Install

```bash
pnpm install        # JS/TS
uv sync             # Python
```

## Run

```bash
# replace with the real command
```

## Validate

```bash
pnpm test
pnpm lint
uv run pytest
```

## Troubleshooting

Add an entry only after the fix is confirmed. Never store credentials here.
