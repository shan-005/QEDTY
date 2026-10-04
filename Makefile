.PHONY: \
	clean \
	install \
	sync \
	test \
	test-unit \
	test-integration \
	test-security \
	test-benchmark \
	coverage \
	coverage-100 \
	lint \
	format \
	typecheck \
	security \
	audit \
	build \
	package-check \
	check \
	release-check \
	bench \
	tree \
	policy-tree \
	policy-files \
	policy-check

PYTHONPATH := src

TREE_EXCLUDE := '__pycache__|venv|.venv|env|*.pyc|*.pyo|.pytest_cache|.mypy_cache|.ruff_cache|.git|node_modules|*.egg-info|target|data|build|dist|htmlcov'

# ============================================================
# ENVIRONMENT
# ============================================================

sync:
	uv sync --all-groups

install:
	uv sync --all-groups

# ============================================================
# CLEAN
# ============================================================

clean:
	find src -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find tests -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".hypothesis" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

	rm -rf \
		htmlcov \
		coverage.xml \
		coverage.json \
		.pytest_cache \
		.mypy_cache \
		.ruff_cache \
		.coverage

	find . -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete 2>/dev/null || true

	@echo "All test/build caches cleaned"

# ============================================================
# TESTING
# ============================================================

test:
	PYTHONPATH=$(PYTHONPATH) pytest -v --tb=short

test-unit:
	PYTHONPATH=$(PYTHONPATH) pytest -v -m unit --tb=short

test-integration:
	PYTHONPATH=$(PYTHONPATH) pytest -v -m integration --tb=short

test-security:
	PYTHONPATH=$(PYTHONPATH) pytest -v -m security --tb=short

test-benchmark:
	PYTHONPATH=$(PYTHONPATH) pytest -v -m benchmark --tb=short

# ============================================================
# COVERAGE
# ============================================================

coverage: clean
	PYTHONPATH=$(PYTHONPATH) pytest \
		--cov=seraph \
		--cov-report=term-missing \
		--cov-report=html \
		--cov-report=xml \
		--cov-report=json \
		--cov-fail-under=0

coverage-100: clean
	PYTHONPATH=$(PYTHONPATH) pytest \
		--cov=seraph \
		--cov-report=term-missing \
		--cov-report=html \
		--cov-report=xml \
		--cov-report=json \
		--cov-fail-under=100

# ============================================================
# CODE QUALITY
# ============================================================

lint:
	ruff check src tests

format:
	ruff format --check src tests

typecheck:
	PYTHONPATH=$(PYTHONPATH) mypy src/

security:
	bandit -r src

audit:
	pip-audit --desc

# ============================================================
# PACKAGING
# ============================================================

build: clean
	python -m build

package-check: build
	twine check dist/*

# ============================================================
# FULL LOCAL CHECK
# ============================================================

check: clean
	@echo ""
	@echo "============================================================"
	@echo " SERAPH GUARD — FULL ENGINEERING CHECK"
	@echo "============================================================"
	@echo ""

	@echo "------------------------------------------------------------"
	@echo "[1/8] PYTEST — FULL SUITE"
	@echo "------------------------------------------------------------"
	PYTHONPATH=$(PYTHONPATH) pytest -v --tb=short

	@echo ""
	@echo "------------------------------------------------------------"
	@echo "[2/8] COVERAGE — REPORT ONLY"
	@echo "------------------------------------------------------------"
	PYTHONPATH=$(PYTHONPATH) pytest \
		--cov=seraph \
		--cov-report=term-missing \
		--cov-report=xml \
		--cov-report=json \
		--cov-fail-under=0

	@echo ""
	@echo "------------------------------------------------------------"
	@echo "[3/8] RUFF"
	@echo "------------------------------------------------------------"
	ruff check src tests

	@echo ""
	@echo "------------------------------------------------------------"
	@echo "[4/8] FORMAT CHECK"
	@echo "------------------------------------------------------------"
	ruff format --check src tests

	@echo ""
	@echo "------------------------------------------------------------"
	@echo "[5/8] MYPY"
	@echo "------------------------------------------------------------"
	PYTHONPATH=$(PYTHONPATH) mypy src/

	@echo ""
	@echo "------------------------------------------------------------"
	@echo "[6/8] BANDIT"
	@echo "------------------------------------------------------------"
	bandit -r src

	@echo ""
	@echo "------------------------------------------------------------"
	@echo "[7/8] PIP AUDIT"
	@echo "------------------------------------------------------------"
	pip-audit --desc

	@echo ""
	@echo "------------------------------------------------------------"
	@echo "[8/8] PACKAGE BUILD CHECK"
	@echo "------------------------------------------------------------"
	rm -rf build dist *.egg-info
	python -m build
	twine check dist/*

	@echo ""
	@echo "============================================================"
	@echo " ALL ENGINEERING CHECKS PASSED"
	@echo "============================================================"

# ============================================================
# RELEASE CHECK
# ============================================================

release-check: clean
	@echo ""
	@echo "============================================================"
	@echo " SERAPH GUARD — RELEASE CHECK"
	@echo "============================================================"
	@echo ""

	PYTHONPATH=$(PYTHONPATH) pytest -v --tb=short

	PYTHONPATH=$(PYTHONPATH) pytest \
		--cov=seraph \
		--cov-report=term-missing \
		--cov-report=html \
		--cov-report=xml \
		--cov-report=json \
		--cov-fail-under=0

	ruff check src tests
	ruff format --check src tests
	PYTHONPATH=$(PYTHONPATH) mypy src/
	bandit -r src
	pip-audit --desc

	rm -rf build dist *.egg-info
	python -m build
	twine check dist/*

	@echo ""
	@echo "============================================================"
	@echo " RELEASE ENGINEERING CHECK PASSED"
	@echo "============================================================"

# ============================================================
# BENCHMARK
# ============================================================

bench:
	@if [ ! -f run_benchmark.sh ]; then \
		echo "run_benchmark.sh not found"; \
		exit 1; \
	fi
	@echo "Starting full benchmark..."
	PYTHONPATH=$(PYTHONPATH) bash run_benchmark.sh

# ============================================================
# TREE
# ============================================================

tree:
	@echo ""
	@echo "================ SERAPH PROJECT TREE ================"
	@tree -a -I $(TREE_EXCLUDE) --dirsfirst .
	@echo ""

# ============================================================
# POLICY TREE
# ============================================================

policy-tree:
	@echo ""
	@echo "================ SERAPH POLICY TREE ================"
	@if [ -d policies ]; then \
		tree -a --dirsfirst policies; \
	else \
		echo "policies/ directory does not exist"; \
		exit 1; \
	fi
	@echo ""

policy-files:
	@echo ""
	@echo "================ ALL POLICY FILES ================"
	@if [ -d policies ]; then \
		find policies -type f \( -name "*.yml" -o -name "*.yaml" \) -print | sort; \
	else \
		echo "policies/ directory does not exist"; \
		exit 1; \
	fi
	@echo ""

policy-check:
	@echo ""
	@echo "================ POLICY STRUCTURE ================"

	@if [ ! -d policies/builtin ]; then \
		echo "Missing: policies/builtin/"; \
		exit 1; \
	fi

	@if [ ! -d policies/auto-generated ]; then \
		echo "Missing: policies/auto-generated/"; \
		exit 1; \
	fi

	@echo ""
	@echo "Builtin policies:"
	@find policies/builtin -maxdepth 1 -type f \( -name "*.yml" -o -name "*.yaml" \) -print | sort

	@echo ""
	@echo "Auto-generated policies:"
	@find policies/auto-generated -maxdepth 1 -type f \( -name "*.yml" -o -name "*.yaml" \) -print | sort

	@echo ""
	@echo "Policies outside builtin/ and auto-generated/:"
	@find policies -type f \
		\( -name "*.yml" -o -name "*.yaml" \) \
		-not -path "policies/builtin/*" \
		-not -path "policies/auto-generated/*" \
		-print | sort || true

	@echo ""
	@echo "Policy structure inspection complete"