CFLAGS += -std=c99 -Wall -Wextra -Wpedantic -Wno-unused-parameter -Wconversion -Werror=incompatible-pointer-types -Werror=implicit-function-declaration
CFLAGS += -Werror=stack-usage=16384   # BUFSIZ is 8192 on my system
CFLAGS += -g
LDFLAGS += -lgmp
IWYUFLAGS += -Xiwyu --no_fwd_decl

SRC := $(filter-out src/main.c, $(wildcard src/*.c src/objects/*.c))
OBJ := $(SRC:src/%.c=obj/%.o)
HEADERS := $(wildcard src/*.h src/objects/*.h)
TESTS_SRC := $(wildcard tests/*.c tests/objects/*.c)
TESTS_HEADERS := $(filter-out tests/runcalls.h, $(wildcard tests/*.h)) tests/runcalls.h

IWYU ?= iwyu

all: asdar

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

.PHONY: clean
clean:
	git clean -fXd

# passing headers as arguments to IWYU makes them get iwyued twice
.PHONY: iwyu
iwyu: tests/runcalls.h
	for file in $(SRC) $(TESTS_SRC); do \
		$(IWYU) $(IWYUFLAGS) -I. "$$file" 2>&1 || true; \
	done | grep --line-buffered -v '^(.* has correct #includes/fwd-decls)$$' | cat -s

.PHONY: help
help:
	@echo "Commands:"
	@echo "  make                   Compile all files that need compiling"
	@echo "  make iwyu              Run IWYU for all .c and .h files (see README)"
	@echo "  make test              Run tests"
	@echo "  make testrunner        Create ./testrunner executable that runs"
	@echo "                         tests (useful for valgrinding, gdb-ing etc)"
