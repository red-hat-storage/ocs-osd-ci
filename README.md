# CI test runner for OCS on OpenShift Dedicated

## Installation

Inline comment shows how to override defaults.
```
make install  # PY_BIN=python3.9 VENV=venv39
```

## Development

Install development dependencies and set up pre-commit hook:
```
make install APP_ENV=dev
```

Run sanity checks:
```
make check
```
