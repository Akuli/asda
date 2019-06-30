CFLAGS += -std=c99 -Wall -Wextra -Wpedantic -Wno-unused-parameter -Wconversion -Werror=incompatible-pointer-types -Werror=implicit-function-declaration -Werror=stack-usage=2048
CFLAGS += -g
LDFLAGS += -lgmp

SRC := $(filter-out src/main.c, $(wildcard src/*.c src/objects/*.c))
OBJ := $(SRC:src/%.c=obj/%.o)
HEADERS := $(wildcard src/*.h src/objects/*.h)

IWYU ?= iwyu

all: asdar

asdar: src/main.c $(OBJ) $(HEADERS)
	$(CC) $(CFLAGS) $< $(OBJ) -o $@ $(LDFLAGS)

obj/%.o: src/%.c $(HEADERS)
	mkdir -p $(@D) && $(CC) -c -o $@ $< $(CFLAGS)

.PHONY: clean
clean:
	rm -rvf asdar obj

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
