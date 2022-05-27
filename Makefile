PY_BIN := python3
VENV := venv
BIN_DIR=$(VENV)/bin
APP_ENV := production

install:
	$(PY_BIN) -m venv $(VENV)
	$(BIN_DIR)/pip install -U pip
	$(BIN_DIR)/pip install -r requirements.txt
    ifeq ("$(APP_ENV)", "dev")
		$(BIN_DIR)/pip install -U tox
		echo "make check" > .git/hooks/pre-commit
		chmod +x .git/hooks/pre-commit
		cp -n .env.example .env
    endif

install-consumer-addon:
	$(BIN_DIR)/python -m src.cli.consumer_addon

check:
	$(BIN_DIR)/tox

format:
	$(BIN_DIR)/tox -e format

format-fix:
	$(BIN_DIR)/tox -e format-fix

lint:
	$(BIN_DIR)/tox -e lint

run-chaos:
	./scripts/jenkins/run-chaos.sh
