CFLAGS += -std=c99 -Wall -Wextra -Wpedantic -Wno-unused-parameter -Wconversion -Werror=incompatible-pointer-types
CFLAGS += -g

SRC := $(filter-out main.c, $(wildcard *.c objects/*.c))
OBJ := $(SRC:%.c=obj/%.o)
HEADERS := $(wildcard *.h)

all: asdar

asdar: main.c $(OBJ) $(HEADERS)
	$(CC) $(CFLAGS) $< $(OBJ) -o $@ $(LDFLAGS)

obj/%.o: %.c $(HEADERS)
	mkdir -p $(@D) && $(CC) -c -o $@ $< $(CFLAGS)

.PHONY: clean
clean:
	rm -rvf asdar obj

.PHONY: iwyu
iwyu:
	for file in $(SRC) main.c; do iwyu -I. $$file; done || true
