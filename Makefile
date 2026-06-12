.PHONY: install lint test run preprocess train

install:
	pip install -r requirements.txt

lint:
	ruff check src tests

test:
	pytest

run:
	uvicorn src.main:app --reload --port 8000

preprocess:
	bash scripts/run_preprocessing.sh

train:
	bash scripts/train_model.sh
