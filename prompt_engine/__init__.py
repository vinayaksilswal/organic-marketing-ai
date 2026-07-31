"""Prompt Engine package.

Deterministic prompt generation, versioning and validation for video creatives
and social captions.

IMPORTANT — keep this module free of heavy imports.

database.py imports prompt_engine.db_models at the end of the module so that
BusinessProfile.prompt_versions can resolve its relationship target from every
entry point. Importing any submodule executes this file first, so anything
imported here is dragged into every process that touches the database —
including the Alembic migration runner.

When this file imported `.router`, that chain was:

    alembic/env.py -> database -> prompt_engine/__init__ -> router
                   -> routers.auth, services.*, fastapi, httpx

which pulled 36 framework modules into the migration process and re-entered
`database` while it was still initialising. The deploy died on SQLAlchemy
MissingGreenlet (sync migration code attempting async IO) and Render kept
serving the previous build.

The application imports `prompt_engine.router` directly, so nothing needed the
re-export here.
"""

__all__ = ["db_models"]
