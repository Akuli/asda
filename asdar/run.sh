#!/bin/bash
set -ex

# usage:
#   ./run.sh                    runs all examples
#   ./run.sh examples/hello     runs examples/hello.asda

( cd .. && python3 -m asdac --always-recompile examples/*.asda )
rm -rf zig-cache
zig build run -Dfile=../asda-compiled/examples/hello.asdac

ok=0
fail=0

run()
{
    local name=$1
    set +e
    if zig-cache/o/*/asdar "../asda-compiled/$name.asdac"; then
        ((ok++))
    else
        ((fail++))
    fi
    set -e
}

if [ $# = 0 ]; then
    for file in ../examples/*.asda; do
        name_wo_examples="$(basename "$file" | sed 's/\..*$//')"
        if [ "$name_wo_examples" != "while" ]; then
            run "examples/$name_wo_examples"
        fi
    done
else
    for name in "$@"; do
        run "$name"
    done
fi

set +x
echo ""
echo "==================="
echo "ran $((ok+fail)) files: $ok ok, $fail failed"
