CFLAGS += -std=c99 -Wall -Wextra -Wpedantic -Wno-unused-parameter -Wconversion -Werror=incompatible-pointer-types -Werror=implicit-function-declaration
CFLAGS += -Werror=stack-usage=16384   # BUFSIZ is 8192 on my system
CFLAGS += -g
CFLAGS += -O3
LDFLAGS += -lgmp
IWYUFLAGS += -Xiwyu --no_fwd_decl

SRC := $(filter-out src/main.c, $(wildcard src/*.c src/objects/*.c))
OBJ := $(SRC:src/%.c=obj/%.o)
HEADERS := $(wildcard src/*.h src/objects/*.h)
TESTS_SRC := $(wildcard tests/*.c tests/objects/*.c)
TESTS_HEADERS := $(filter-out tests/runcalls.h, $(wildcard tests/*.h)) tests/runcalls.h

IWYU ?= iwyu

ifdef NDEBUG
	CFLAGS += -DNDEBUG
endif

all: asdar

.PHONY: clean
clean:
	git clean -fXd


obj/%.o: src/%.c $(HEADERS)
	mkdir -p $(@D) && $(CC) -c -o $@ $< $(CFLAGS)

asdar: src/main.c $(OBJ) $(HEADERS)
	$(CC) $(CFLAGS) $< $(OBJ) -o $@ $(LDFLAGS)


tests/runcalls.h: $(TESTS_SRC) tests/create_runcalls.sh
	sh tests/create_runcalls.sh $(TESTS_SRC) > tests/runcalls.h

testrunner: $(TESTS_SRC) $(OBJ) $(TESTS_HEADERS)
	$(CC) $(CFLAGS) $(TESTS_SRC) -I. $(OBJ) -o $@ $(LDFLAGS)

.PHONY: test
test: testrunner
	./testrunner


# passing headers as arguments to IWYU makes them get iwyued twice
.PHONY: iwyu
iwyu: tests/runcalls.h
	for file in $(SRC) $(TESTS_SRC); do \
		$(IWYU) $(IWYUFLAGS) -I. "$$file" 2>&1 || true; \
	done | grep --line-buffered -v '^(.* has correct #includes/fwd-decls)$$' | cat -s


ifdef FILE

COMPILED_FILE := ../asda-compiled/asdar/$(basename $(FILE)).asdac

../asda-compiled/asdar/%.asdac: $(FILE)
	(cd .. && python3 -m asdac asdar/$(shell echo $(notdir $@) | sed 's/c$$//'))

callgrind.out: $(COMPILED_FILE) asdar
	valgrind --tool=callgrind --callgrind-out-file=$@ ./asdar $<

graph.gv: callgrind.out
	gprof2dot $< --format=callgrind --output=$@

graph.png: graph.gv
	dot -Tpng $< -o $@

.PHONY: run
run: $(COMPILED_FILE) asdar
	bash -c 'time ./asdar $(COMPILED_FILE)'

else

.PHONY: graph.png
graph.png:
	@echo "Usage: make graph.png FILE=somefilenamehere.asda"
	@echo ""
	@exit 2

endif


# wrap the he
.PHONY: help
help:
	@echo "If you haven't read ./README.md yet, please read it. \
	Note that there are two READMEs, \
	./README.md for C interpreter stuff and ../README.md for general stuff." | fold -s
	@echo ""
	@echo "Commands:"
	@echo "  make"
	@echo "    Compile all files that need compiling."
	@echo "  make iwyu"
	@echo "    Run IWYU for all .c and .h files"
	@echo "  make testrunner"
	@echo "    Create ./testrunner executable that runs tests (useful for"
	@echo "    valgrinding, gdb-ing etc). './testrunner' runs all tests, and"
	@echo "    './testrunner TEST1 TEST2 TEST3' runs the given tests only."
	@echo "  make test"
	@echo "    Run all tests."
	@echo "  make graph.png FILE=something.asda"
	@echo "    Create an execution time graph of running the asda file. Open"
	@echo "    graph.png in your favorite image viewer after calling this."
	@echo "  make run FILE=something.asda"
	@echo "    Run the file and measure how long it takes."
	@echo "  make clean"
	@echo "    Removes graph.png, compiled files and other similar files."
