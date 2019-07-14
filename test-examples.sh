set -e

for file in "$@"; do
    if [ "$file" = "examples/while.asda" ]; then
        continue
    fi
    echo "Running $file"
    compiled=asda-compiled/"$file"c
    diff -u examples/output/"$(basename "$file" | cut -d. -f1)".txt <(asdar/asdar "$compiled")
done
