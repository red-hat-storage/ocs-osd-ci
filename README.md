# CI test runner for OCS on OpenShift Dedicated

[![Check python code](https://github.com/alfonsomthd/ocs-osd-ci/actions/workflows/main.yaml/badge.svg)](https://github.com/alfonsomthd/ocs-osd-ci/actions/workflows/main.yaml)

## Installation

Inline comment shows how to override defaults.
```
make install  # PY_BIN=python3.9 VENV=venv39
```

## Development

Install the app for development (it also creates the *.env* file if it doesn't exist):
```
make install APP_ENV=dev
```

You have to provide the values for the required variables in the *.env* file.

Run sanity checks:
```
make check
```
