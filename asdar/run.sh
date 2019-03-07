#!/bin/bash
set -e

(cd .. && python3 -m asdac examples/*.asda)

echo "running zig build..."
zig build

ok=0
fail=0
for file in ../asda-compiled/examples/*; do
    case "$file" in
    */while.asdac)
        ;;
    *)
        printf "\n*** %s ***\n\n" "$file"
        set +e
        if zig-cache/asdar "$file"; then
            ((ok++))
        else
            ((fail++))
        fi
        set -e
    esac
done

echo ""
echo "==================="
echo "ran $((ok+fail)) files: $ok ok, $fail failed"
