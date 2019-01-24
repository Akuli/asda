#!/bin/bash

rm -rvf asda-compiled

for file in *.asda; do
    PYTHONPATH=.. python3 -m asdac $file
done

for file in asda-compiled/*.asdac; do
    if [ $file != asda-compiled/while.asdac ]; then
        PYTHONPATH=.. python3 -m pyasda $file
    fi
done

# python fails when infinite output is piped to head, that's why stderr
# goes to devnull
PYTHONPATH=.. python3 -m pyasda asda-compiled/while.asdac 2>/dev/null | head
