VENV := venv
BIN=$(VENV)/bin

install:
	python3 -m venv $(VENV)
	$(BIN)/pip install -U pip
	$(BIN)/pip install -r requirements.txt

install-dev: install
	$(BIN)/pip install -U tox
	echo "make check" > .git/hooks/pre-commit
	chmod +x .git/hooks/pre-commit

check:
	$(BIN)/tox -e format,lint

format:
	$(BIN)/tox -e format

format-fix:
	$(BIN)/tox -e format-fix

lint:
	$(BIN)/tox -e lint

run-chaos:
	$(BIN)/python -m src.cli.chaos
