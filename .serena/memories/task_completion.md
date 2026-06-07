# Linkya — Task Completion

## Before committing any Python change

```bash
make lint
# → runs: flake8 backend-service/src nilm-service/src ha-ingest-service/src ha-publish-service/src
# → runs: isort --check-only --diff (same dirs)
# Both use || true — failures shown but don't block; fix them anyway.
```

Fix isort automatically:
```bash
isort backend-service/src nilm-service/src ha-ingest-service/src ha-publish-service/src
```

Fix flake8: resolve reported errors manually (no auto-fix tool).

## No test suite

No pytest, no test files. Verification = `make up` + manual exercise.

## Commit readiness checklist

- [ ] `make lint` clean (no real errors).
- [ ] `.env.example` in sync with `.env` if config keys added/removed.
- [ ] Docker images build: `make build` (dev).
- [ ] No `print()` added; logging uses correct library for the service.

## Schema changes

No migrations — coordinate deploy timing carefully. `make clean && make up` resets schema (data loss).
