# this Makefile is meant to be used as a convenient way to compile
# everything and run all tests, and not much else

all: asdar/asdar asdar-tests asdac-tests
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
	python3 -m pytest asdac-tests
