
.phony: test test-flake8 test-git-fat

PYTHON ?= python
ROOT := $(shell git rev-parse --show-toplevel)

test: test-flake8 test-git-fat

FLAKE8 ?= flake8
test-flake8:
	find . -iname '*.py' -not -path "./venv/*" | xargs $(FLAKE8) --config=tests/flake8.cfg

COVERAGE ?= coverage
test-git-fat:
	cd $(ROOT)
	rm -f .coverage
	$(PYTHON) tests/test_git_fat.py
	$(COVERAGE) combine
