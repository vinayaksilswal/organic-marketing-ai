#!/usr/bin/env bash
# =============================================================================
# Organic Marketing AI — Render Build Script
# =============================================================================
set -o errexit
set -o pipefail

echo "=== Organic Marketing AI Build ==="
echo "Commit:  ${RENDER_GIT_COMMIT:-unknown}"
echo "Branch:  ${RENDER_GIT_BRANCH:-unknown}"
echo "Python:  $(python --version 2>&1)"

# Install Python dependencies
pip install --no-cache-dir -r requirements.txt

# -----------------------------------------------------------------------------
# Database migrations
# -----------------------------------------------------------------------------
# A failure here must be obvious in the deploy log. Previously a migration error
# aborted the build with no context, leaving Render serving the last good image
# while the new code appeared to be "pushed" — silent deploy drift.
echo "=== Running Alembic Migrations ==="
echo "--- current revision before upgrade ---"
alembic current || echo "(no alembic_version table yet — first run)"

# The database may carry a stamp from a previous, since-replaced migration set.
# Alembic aborts on a revision id it cannot resolve, which fails the build and
# silently keeps the old image live. Re-point a stranded stamp before upgrading.
echo "--- checking for a stranded alembic stamp ---"
python scripts/repair_alembic_state.py

# Apply one revision at a time so the log names the revision that failed.
# Upgrading straight to head only tells you that something in the chain broke.
echo "--- pending revisions ---"
alembic history -r current:head 2>&1 | head -20 || true

MIGRATION_LOG=$(mktemp)
if ! alembic upgrade head > "$MIGRATION_LOG" 2>&1; then
    echo ""
    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    echo "!! MIGRATION FAILED — the deploy is being aborted."
    echo "!! Render will keep serving the PREVIOUS build until this is fixed."
    echo "!!"
    echo "!! THE ERROR:"
    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    # The failing statement and the database's own message are the only things
    # that matter here. A previous version of this banner dumped the whole
    # revision history, which pushed the actual error off the top of the log
    # and made three deploy failures unreadable.
    grep -iE "error|exception|detail:|hint:|line [0-9]+:|\[SQL" "$MIGRATION_LOG" | tail -40 || true
    echo ""
    echo "--- last 60 lines of migration output ---"
    tail -60 "$MIGRATION_LOG" || true
    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    echo "!! Stamped revision at time of failure:"
    alembic current 2>&1 | tail -5 || true
    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    rm -f "$MIGRATION_LOG"
    exit 1
fi
cat "$MIGRATION_LOG"
rm -f "$MIGRATION_LOG"

echo "--- revision after upgrade ---"
alembic current

echo "=== Build Complete ==="
