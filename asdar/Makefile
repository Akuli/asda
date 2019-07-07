CFLAGS += -std=c99 -Wall -Wextra -Wpedantic -Wno-unused-parameter -Wconversion -Werror=incompatible-pointer-types -Werror=implicit-function-declaration
CFLAGS += -Werror=stack-usage=16384   # BUFSIZ is 8192 on my system
CFLAGS += -g
LDFLAGS += -lgmp

SRC := $(filter-out src/main.c, $(wildcard src/*.c src/objects/*.c))
TESTS_SRC = $(wildcard tests/test_*.c tests/objects/test_*.c)
OBJ := $(SRC:src/%.c=obj/%.o)
HEADERS := $(wildcard src/*.h src/objects/*.h)

IWYU ?= iwyu

all: asdar

obj/%.o: src/%.c $(HEADERS)
	mkdir -p $(@D) && $(CC) -c -o $@ $< $(CFLAGS)

asdar: src/main.c $(OBJ) $(HEADERS)
	$(CC) $(CFLAGS) $< $(OBJ) -o $@ $(LDFLAGS)

tests/runcalls.h: $(TESTS_SRC) tests/create_runcalls.sh
	sh tests/create_runcalls.sh $(TESTS_SRC) > tests/runcalls.h

testrunner: $(TESTS_SRC) $(OBJ) tests/main.c $(wildcard tests/util.*) tests/runcalls.h
	$(CC) $(CFLAGS) tests/main.c tests/util.c $(TESTS_SRC) -I. $(OBJ) -o $@ $(LDFLAGS)

.PHONY: test
test: testrunner
	./testrunner

.PHONY: clean
clean:
	git clean -fXd

.PHONY: iwyu.% iwyu.objects/%
iwyu.%:
	@ $(IWYU) -Xiwyu --no_fwd_decl $(shell echo $@ | sed 's:^iwyu\.:src/:') || true
iwyu.objects/%:
	@ $(IWYU) -Xiwyu --no_fwd_decl $(shell echo $@ | sed 's:^iwyu\.:src/:') || true

IWYU_TARGETS := $(SRC:src/%=iwyu.%) $(HEADERS:src/%=iwyu.%)

.PHONY: iwyu
iwyu: $(IWYU_TARGETS)

.PHONY: help
help:
	@echo "Commands:"
	@echo "  make                   Compile all files that need compiling"
	@echo "  make iwyu              Run IWYU for all .c and .h files"
	@echo "  make iwyu.FILENAME     Run IWYU for one file. The FILENAME should"
	@echo "                         be e.g. 'main.c' or 'objects/int.h'."
