#!/bin/bash
set -e

if [ $# -gt 1 ] || ([ $# -eq 1 ] && [ "$1" != "--valgrind" ]); then
	echo "Usage: $0 [--valgrind]" 2>&1
	exit 1
fi

valgrind=''
if [ "$1" = "--valgrind" ]; then
	valgrind='valgrind -q --show-leak-kinds=all --leak-check=full'
fi

for file in examples/*.asda; do
    echo "Running $file"
    compiled=asda-compiled/"$file"c
    expectedfile=examples/output/"$(basename "$file" | cut -d. -f1)".txt
    diff -u \
        <(sed "s:EXAMPLESSLASH:$PWD/examples/:g" "$expectedfile") \
        <($valgrind asdar/asdar "$compiled" 2>&1)
done
