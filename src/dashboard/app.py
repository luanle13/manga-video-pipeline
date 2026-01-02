from __future__ import annotations
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import sys
import os

# Add the src directory to the path to import other modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# Create the FastAPI app
app = FastAPI(
    title="Manga Video Pipeline Dashboard",
    description="Dashboard for monitoring manga video pipeline processes",
    version="1.0.0"
)

# Set up Jinja2 templates
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

# Mount a static directory if needed (create it if it doesn't exist)
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Import routes after app is created to avoid circular imports
from . import routes

# Include the routes
app.include_router(routes.router)

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "dashboard"}