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

if ! alembic upgrade head; then
    echo ""
    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    echo "!! MIGRATION FAILED — the deploy is being aborted."
    echo "!! Render will keep serving the PREVIOUS build until this is fixed."
    echo "!! Revision history:"
    alembic history --verbose 2>&1 | head -40 || true
    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    exit 1
fi

echo "--- revision after upgrade ---"
alembic current

echo "=== Build Complete ==="
