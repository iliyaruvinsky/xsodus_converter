"""FastAPI application entry point."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from ..version import __version__
from .api.routes import router
from .database import init_db

logger = logging.getLogger(__name__)


def _validate_required_files():
    """Validate that all required catalog files exist at startup.

    Fails loudly if critical files are missing to prevent silent failures
    during conversion operations.
    """
    # Calculate catalog path from this file's location
    catalog_data_path = Path(__file__).parent.parent / "catalog" / "data"

    required_files = [
        ("functions.yaml", "Function catalog for legacy helper rewrites"),
        ("patterns.yaml", "Pattern catalog for expression rewrites"),
    ]

    missing = []
    for filename, description in required_files:
        filepath = catalog_data_path / filename
        if not filepath.exists():
            missing.append(f"  - {filename}: {description}")
            logger.error(f"MISSING REQUIRED FILE: {filepath}")

    if missing:
        error_msg = (
            "\n" + "=" * 60 + "\n"
            "STARTUP VALIDATION FAILED - MISSING REQUIRED FILES\n"
            "=" * 60 + "\n"
            f"Catalog directory: {catalog_data_path}\n\n"
            "Missing files:\n" + "\n".join(missing) + "\n\n"
            "These files are required for SQL conversion to work.\n"
            "Please restore them from git or recreate them.\n"
            "=" * 60
        )
        logger.critical(error_msg)
        raise RuntimeError(error_msg)

    logger.info(f"Startup validation passed: all {len(required_files)} catalog files present")


# Validate required files exist BEFORE starting server
_validate_required_files()

# Initialize database on startup
init_db()

app = FastAPI(
    title="XML to SQL Converter",
    description="Convert SAP HANA calculation view XML definitions into Snowflake SQL artifacts",
    version=__version__,
)

# CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes (must be before static file mount to take precedence)
app.include_router(router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/api/version")
async def get_version():
    """Get application version."""
    return {"version": __version__}


# Serve static files (React build) if they exist
# Calculate path: from src/xml_to_sql/web/main.py -> project root -> web_frontend/dist
_project_root = Path(__file__).parent.parent.parent.parent
frontend_build_path = _project_root / "web_frontend" / "dist"

if frontend_build_path.exists() and (frontend_build_path / "index.html").exists():
    # Mount static files - this will serve index.html for "/" and other static assets
    # API routes under "/api" will still work because they're more specific
    app.mount("/", StaticFiles(directory=str(frontend_build_path), html=True), name="static")
else:
    # Fallback: serve a simple message if frontend not built
    @app.get("/")
    async def root():
        return {
            "message": "XML to SQL Converter API",
            "docs": "/docs",
            "note": f"Frontend not built. Expected at: {frontend_build_path}. Run 'npm run build' in web_frontend directory.",
        }
