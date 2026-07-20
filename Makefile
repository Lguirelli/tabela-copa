PYTHON ?= python
COMPETITION ?= world_cup_2026

.PHONY: install test integrity audit completeness update validate analyze train simulate all all-competitions clean-cache

install:
	$(PYTHON) -m pip install -r requirements.txt
	$(PYTHON) -m pip install -e .

test:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m pytest -p no:cacheprovider
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) scripts/validate_repository.py
	$(PYTHON) scripts/testes/test_integridade_dados.py

integrity:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) scripts/validate_repository.py

audit:
	$(PYTHON) -m sports_engine.cli audit

completeness:
	$(PYTHON) -m sports_engine.cli completeness --competition $(COMPETITION)

update:
	$(PYTHON) -m sports_engine.cli enrich --competition $(COMPETITION)

validate:
	$(PYTHON) -m sports_engine.cli validate --competition $(COMPETITION)

analyze:
	$(PYTHON) -m sports_engine.cli patterns --competition $(COMPETITION)
	$(PYTHON) -m sports_engine.cli feedback --competition $(COMPETITION)
	$(PYTHON) -m sports_engine.cli features --competition $(COMPETITION)

train:
	$(PYTHON) -m sports_engine.cli recalibrate --competition $(COMPETITION)

simulate:
	$(PYTHON) -m sports_engine.cli simulate --competition $(COMPETITION)

all:
	$(PYTHON) -m sports_engine.cli run-all --competition $(COMPETITION)

all-competitions:
	$(PYTHON) -m sports_engine.cli run-registry

clean-cache:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache
