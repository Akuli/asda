PYTHON ?= python3   # see README

EXAMPLES := $(wildcard examples/*.asda)

all: asdar/asdar asdar-tests asdac-tests example-tests
	@echo ""
	@echo ""
	@echo "--------------------"
	@echo "All the stuff has been compiled and tested successfully."

.PHONY: asdar/asdar   # because asdar/Makefile avoids unnecessary recompiling
asdar/asdar:
	$(MAKE) -C asdar asdar

.PHONY: asdar-tests
asdar-tests: asdar/asdar
	$(MAKE) -C asdar test

.PHONY: asdac-tests
asdac-tests:
	$(PYTHON) -m pytest

.PHONY: compile-examples   # because the compiler avoids unnecessary recompiling
compile-examples:
	$(PYTHON) -m asdac $(EXAMPLES)

example-tests: compile-examples asdar/asdar
	bash test-examples.sh $(EXAMPLES)
