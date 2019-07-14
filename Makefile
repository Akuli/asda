PYTHON ?= python3   # see README

EXAMPLES := $(wildcard examples/*.asda)

all: asdar/asdar asdar-tests asdac-tests example-tests
	@echo ""
	@echo ""
	@echo "--------------------"
	@echo "All the stuff has been compiled and tested successfully."

asdar/asdar:
	$(MAKE) -C asdar asdar

.PHONY: asdar-tests
asdar-tests:
	$(MAKE) -C asdar test

.PHONY: asdac-tests
asdac-tests:
	$(PYTHON) -m pytest

.PHONY: compile-examples    # the compiler avoids compiling when not necessary
compile-examples:
	$(PYTHON) -m asdac $(EXAMPLES)

example-tests: compile-examples asdar/asdar
	bash test-examples.sh $(EXAMPLES)
