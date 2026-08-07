PYTHON ?= python
COMPETITION ?= world_cup_2026
MODE ?= daily
AS_OF ?=
NETWORK ?= 0

.PHONY: install test integrity audit completeness update validate analyze train simulate all all-competitions export-dashboard pipeline diagnose clean-cache

install:
<<<<<<< HEAD
=======
	$(PYTHON) -m pip install -r requirements.txt
>>>>>>> 0fb9a768f5f7adf18fc6e3a227415ccd8e396ee3
	$(PYTHON) -m pip install -e .

test: clean-cache
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m pytest -p no:cacheprovider
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) scripts/validate_repository.py
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) scripts/testes/test_integridade_dados.py

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

export-dashboard:
	$(PYTHON) scripts/export_model_dashboard.py

pipeline:
	@args="--mode $(MODE) --competition $(COMPETITION) --run-tests"; \
	if [ -n "$(AS_OF)" ]; then args="$$args --as-of $(AS_OF)"; fi; \
	if [ "$(NETWORK)" = "1" ]; then args="$$args --allow-network"; fi; \
	$(PYTHON) scripts/run_repository_pipeline.py $$args

diagnose:
	$(PYTHON) scripts/diagnose_github_actions.py

clean-cache:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache
