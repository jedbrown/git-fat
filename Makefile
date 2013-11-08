
.phony: test test-flake8 test-git-fat

FLAKE8 ?= flake8
PYTHON ?= python
ROOT := $(shell git rev-parse --show-toplevel)


test: test-flake8 test-git-fat

test-flake8:
	find . -iname '*.py' | xargs flake8 --config=tests/flake8.cfg

test-git-fat:
	cd $(ROOT)
	$(PYTHON) tests/test_git_fat.py
	coverage combine
	
