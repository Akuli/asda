set -e
echo "// generated by $0"
cd "$(dirname $0)"
printf '%s\n' test_*.c | sed 's/^test_\(.*\)\.c/RUN_TESTS(\1);/'