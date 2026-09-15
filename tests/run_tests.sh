#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "=== JobHunt Test Runner ==="
echo ""

# Parse arguments
COVERAGE=false
MARKERS=""
VERBOSE=false
PARALLEL=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --coverage)
            COVERAGE=true
            shift
            ;;
        --marker|-m)
            MARKERS="$2"
            shift 2
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --parallel|-p)
            PARALLEL=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --coverage        Enable coverage reporting"
            echo "  --marker, -m M    Only run tests with the given marker"
            echo "  --verbose, -v     Verbose output"
            echo "  --parallel, -p    Run tests in parallel"
            echo "  --help, -h        Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Build pytest command
PYTEST_ARGS=()

if $COVERAGE; then
    echo "  [x] Coverage enabled"
    PYTEST_ARGS+=(--cov=. --cov-report=term --cov-report=html:coverage_report)
fi

if [[ -n "$MARKERS" ]]; then
    echo "  [x] Filtering by marker: $MARKERS"
    PYTEST_ARGS+=(-m "$MARKERS")
fi

if $VERBOSE; then
    PYTEST_ARGS+=(-v)
fi

if $PARALLEL; then
    echo "  [x] Parallel execution enabled"
    PYTEST_ARGS+=(-n auto)
fi

echo ""
echo "Running: pytest ${PYTEST_ARGS[*]}"
echo ""

# Execute
cd "$SCRIPT_DIR"
exec pytest "${PYTEST_ARGS[@]}" "$@"
