set -e
echo "// generated by $0"
grep -h '^TEST(' "$@" | sed 's/^TEST(\(.*\)).*$/RUN_TEST(\1);/g'