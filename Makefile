PYTHON ?= python3
TEST_PYTHON ?= .test-venv/bin/python
SDK_ROOT ?= ..
RELEASE_DIR ?= dist
RELEASE_CLASS ?= development
PROFILE ?= lite
GATE_ARGS ?=

.PHONY: test test-bootstrap verify-sdk gate package clean-test

test:
	TEST_PYTHON="$(TEST_PYTHON)" ./scripts/test_all.sh

test-bootstrap:
	$(PYTHON) -m venv .test-venv
	.test-venv/bin/pip install --disable-pip-version-check -r tests/requirements.txt

verify-sdk:
	./scripts/verify_industrial_gateway.sh "$(SDK_ROOT)"
	./scripts/verify_overlay.sh "$(SDK_ROOT)"

gate:
	$(PYTHON) ./scripts/check_release_gates.py \
		--release-class "$(RELEASE_CLASS)" --profile "$(PROFILE)" $(GATE_ARGS)

package:
	./scripts/package_source_release.sh "$(RELEASE_DIR)"

clean-test:
	@echo "Remove .test-venv manually if a clean test environment is required."
