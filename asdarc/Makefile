CFLAGS += -std=c99 -Wall -Wextra -Wpedantic -Wno-unused-parameter -Wconversion -Werror=incompatible-pointer-types -Werror=implicit-function-declaration -Werror=stack-usage=2048
CFLAGS += -g

SRC := $(filter-out main.c, $(wildcard *.c objects/*.c))
OBJ := $(SRC:%.c=obj/%.o)
HEADERS := $(wildcard *.h objects/*.h)

IWYU ?= iwyu

all: asdar

asdar: main.c $(OBJ) $(HEADERS)
	$(CC) $(CFLAGS) $< $(OBJ) -o $@ $(LDFLAGS)

obj/%.o: %.c $(HEADERS)
	mkdir -p $(@D) && $(CC) -c -o $@ $< $(CFLAGS)

.PHONY: clean
clean:
	rm -rvf asdar obj

.PHONY: iwyu.% iwyu.objects/%
iwyu.%:
	@ $(IWYU) -Xiwyu --no_fwd_decl $(shell echo $@ | sed 's/^iwyu\.//') || true
iwyu.objects/%:
	@ $(IWYU) -Xiwyu --no_fwd_decl $(shell echo $@ | sed 's/^iwyu\.//') || true

IWYU_TARGETS := $(SRC:%=iwyu.%) $(HEADERS:%=iwyu.%)

.PHONY: iwyu
iwyu: $(IWYU_TARGETS)

.PHONY: help
help:
	@echo "Commands:"
	@echo "  make                   Compile all files that need compiling"
	@echo "  make iwyu              Run IWYU for all .c and .h files"
	@echo "  make iwyu.FILENAME     Run IWYU for one file. The FILENAME should"
	@echo "                         end with '.c' or '.h'."
