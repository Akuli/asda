set -e

for file in "$@"; do
    echo "Running $file"
    compiled=asda-compiled/"$file"c
    expectedfile=examples/output/"$(basename "$file" | cut -d. -f1)".txt
    diff -u \
        <(sed "s:EXAMPLESSLASH:$PWD/examples/:g" "$expectedfile") \
        <(asdar/asdar "$compiled" 2>&1)
done
