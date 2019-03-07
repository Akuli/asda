#!/bin/bash
set -e

# usage:
#   ./run.sh            runs all examples
#   ./run.sh hello      runs examples/hello.asda

#echo "running zig build..."
#zig build

ok=0
fail=0

run()
{
    local name=$1
    echo ""
    echo "*** $name ***"
    echo ""

    ( cd .. && python3 -m asdac "examples/$name.asda" )
    set +e
    if zig-cache/asdar "../asda-compiled/examples/$name.asdac"; then
        ((ok++))
    else
        ((fail++))
    fi
    set -e
}

if [ $# = 0 ]; then
    for file in ../examples/*.asda; do
        name="$(basename "$file" | sed -e 's/\..*$//')"
        if [ "$name" != "while" ]; then
            run "$name"
        fi
    done
else
    for file in "$@"; do
        run "$file"
    done
fi

echo ""
echo "==================="
echo "ran $((ok+fail)) files: $ok ok, $fail failed"
