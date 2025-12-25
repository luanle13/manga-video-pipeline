from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
from jinja2 import Template
from sqlalchemy import select
from ..config import get_settings
from ..database import init_db, get_async_db, Manga, Video, PipelineRun
from sqlalchemy.ext.asyncio import AsyncSession


app = FastAPI(title="Manga Video Pipeline Dashboard", version="0.1.0")


# Pydantic models
class MangaResponse(BaseModel):
    id: int
    source: str
    source_id: str
    title: str
    cover_url: str | None = None
    trending_rank: int | None = None
    is_active: bool
    last_checked_at: str | None = None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class VideoResponse(BaseModel):
    id: int
    chapter_id: int
    language: str
    title: str
    description: str
    tags: dict | None = None
    script: str | None = None
    file_path: str
    duration_seconds: int | None = None
    is_uploaded: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class PipelineTaskResponse(BaseModel):
    id: int
    chapter_id: int
    status: str
    current_stage: str | None = None
    progress_percent: int
    error_message: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


@app.on_event("startup")
async def startup_event():
    """Initialize the database."""
    await init_db()


@app.get("/", response_class=HTMLResponse)
async def dashboard_home():
    """Main dashboard page."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Manga Video Pipeline Dashboard</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body>
        <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
            <div class="container-fluid">
                <a class="navbar-brand" href="/">Manga Video Pipeline</a>
            </div>
        </nav>
        
        <div class="container mt-4">
            <div class="row">
                <div class="col-md-12">
                    <h1>Manga Video Pipeline Dashboard</h1>
                    <p class="lead">Automated manga to video pipeline system</p>
                    
                    <div class="row">
                        <div class="col-md-4">
                            <div class="card">
                                <div class="card-body">
                                    <h5 class="card-title">Manga Discovery</h5>
                                    <p class="card-text">Discover trending manga from various sources</p>
                                    <a href="/discover" class="btn btn-primary">Discover Manga</a>
                                </div>
                            </div>
                        </div>
                        
                        <div class="col-md-4">
                            <div class="card">
                                <div class="card-body">
                                    <h5 class="card-title">Pipeline Status</h5>
                                    <p class="card-text">Monitor active pipeline tasks</p>
                                    <a href="/pipeline" class="btn btn-primary">View Tasks</a>
                                </div>
                            </div>
                        </div>
                        
                        <div class="col-md-4">
                            <div class="card">
                                <div class="card-body">
                                    <h5 class="card-title">Generated Videos</h5>
                                    <p class="card-text">View all generated videos</p>
                                    <a href="/videos" class="btn btn-primary">View Videos</a>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.get("/api/manga", response_model=List[MangaResponse])
async def get_manga():
    """Get all manga from the database."""
    async for db in get_async_db():
        stmt = select(Manga)
        result = await db.execute(stmt)
        manga = result.scalars().all()
        return manga


@app.get("/api/videos", response_model=List[VideoResponse])
async def get_videos():
    """Get all videos from the database."""
    async for db in get_async_db():
        stmt = select(Video)
        result = await db.execute(stmt)
        videos = result.scalars().all()
        return videos


@app.get("/api/pipeline-runs", response_model=List[PipelineTaskResponse])
async def get_pipeline_runs():
    """Get all pipeline runs from the database."""
    async for db in get_async_db():
        stmt = select(PipelineRun)
        result = await db.execute(stmt)
        runs = result.scalars().all()
        return runs


@app.get("/discover", response_class=HTMLResponse)
async def discover_page():
    """Manga discovery page."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Discover Manga - Manga Video Pipeline Dashboard</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body>
        <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
            <div class="container-fluid">
                <a class="navbar-brand" href="/">Manga Video Pipeline</a>
                <div class="navbar-nav">
                    <a class="nav-link" href="/">Dashboard</a>
                    <a class="nav-link" href="/discover">Discover</a>
                    <a class="nav-link" href="/pipeline">Pipeline</a>
                    <a class="nav-link" href="/videos">Videos</a>
                </div>
            </div>
        </nav>
        
        <div class="container mt-4">
            <h1>Discover Trending Manga</h1>
            <div id="manga-list">
                <!-- Manga list will be loaded here -->
                <p>Loading manga...</p>
            </div>
        </div>
        
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
        <script>
            // Load manga via API
            fetch('/api/manga')
                .then(response => response.json())
                .then(data => {
                    const mangaList = document.getElementById('manga-list');
                    mangaList.innerHTML = '';
                    
                    if (data.length === 0) {
                        mangaList.innerHTML = '<p>No manga found. Run discovery to find trending manga.</p>';
                    } else {
                        data.forEach(manga => {
                            const mangaCard = document.createElement('div');
                            mangaCard.className = 'card mb-3';
                            mangaCard.innerHTML = `
                                <div class="row g-0">
                                    <div class="col-md-2">
                                        <img src="${manga.cover_url}" class="img-fluid rounded-start" alt="${manga.title}">
                                    </div>
                                    <div class="col-md-10">
                                        <div class="card-body">
                                            <h5 class="card-title">${manga.title}</h5>
                                            <p class="card-text">Source: ${manga.source}</p>
                                            <p class="card-text"><small class="text-muted">Trending Rank: ${manga.trending_rank || 'N/A'}</small></p>
                                        </div>
                                    </div>
                                </div>
                            `;
                            mangaList.appendChild(mangaCard);
                        });
                    }
                })
                .catch(error => {
                    console.error('Error loading manga:', error);
                    document.getElementById('manga-list').innerHTML = '<p>Error loading manga.</p>';
                });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.get("/pipeline", response_class=HTMLResponse)
async def pipeline_page():
    """Pipeline tasks page."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Pipeline Tasks - Manga Video Pipeline Dashboard</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body>
        <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
            <div class="container-fluid">
                <a class="navbar-brand" href="/">Manga Video Pipeline</a>
                <div class="navbar-nav">
                    <a class="nav-link" href="/">Dashboard</a>
                    <a class="nav-link" href="/discover">Discover</a>
                    <a class="nav-link" href="/pipeline">Pipeline</a>
                    <a class="nav-link" href="/videos">Videos</a>
                </div>
            </div>
        </nav>
        
        <div class="container mt-4">
            <h1>Active Pipeline Tasks</h1>
            <div id="tasks-list">
                <!-- Tasks will be loaded here -->
                <p>Loading tasks...</p>
            </div>
        </div>
        
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
        <script>
            // Load tasks via API
            fetch('/api/pipeline-runs')
                .then(response => response.json())
                .then(data => {
                    const tasksList = document.getElementById('tasks-list');
                    tasksList.innerHTML = '';
                    
                    if (data.length === 0) {
                        tasksList.innerHTML = '<p>No active pipeline tasks.</p>';
                    } else {
                        data.forEach(task => {
                            const taskCard = document.createElement('div');
                            taskCard.className = 'card mb-3';
                            
                            // Calculate progress bar color based on status
                            let progressBarClass = 'bg-success';
                            if (task.status === 'failed') progressBarClass = 'bg-danger';
                            else if (task.status === 'pending') progressBarClass = 'bg-warning';
                            else if (task.status === 'running') progressBarClass = 'bg-info';
                            
                            taskCard.innerHTML = `
                                <div class="card-body">
                                    <h5 class="card-title">Pipeline Run for Chapter ${task.chapter_id}</h5>
                                    <p class="card-text">
                                        <strong>Status:</strong> <span class="badge bg-${progressBarClass.replace('bg-', '')}">${task.status}</span><br>
                                        <strong>Progress:</strong> ${task.progress_percent}%<br>
                                        <strong>Stage:</strong> ${task.current_stage || 'N/A'}
                                    </p>
                                    <div class="progress">
                                        <div class="progress-bar" role="progressbar" style="width: ${task.progress_percent}%" aria-valuenow="${task.progress_percent}" aria-valuemin="0" aria-valuemax="100">
                                            ${task.progress_percent}%
                                        </div>
                                    </div>
                                    ${task.error_message ? `<p class="card-text mt-2"><strong>Error:</strong> ${task.error_message}</p>` : ''}
                                </div>
                            `;
                            tasksList.appendChild(taskCard);
                        });
                    }
                })
                .catch(error => {
                    console.error('Error loading tasks:', error);
                    document.getElementById('tasks-list').innerHTML = '<p>Error loading tasks.</p>';
                });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.get("/videos", response_class=HTMLResponse)
async def videos_page():
    """Generated videos page."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Generated Videos - Manga Video Pipeline Dashboard</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body>
        <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
            <div class="container-fluid">
                <a class="navbar-brand" href="/">Manga Video Pipeline</a>
                <div class="navbar-nav">
                    <a class="nav-link" href="/">Dashboard</a>
                    <a class="nav-link" href="/discover">Discover</a>
                    <a class="nav-link" href="/pipeline">Pipeline</a>
                    <a class="nav-link" href="/videos">Videos</a>
                </div>
            </div>
        </nav>
        
        <div class="container mt-4">
            <h1>Generated Videos</h1>
            <div id="videos-list">
                <!-- Videos will be loaded here -->
                <p>Loading videos...</p>
            </div>
        </div>
        
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
        <script>
            // Load videos via API
            fetch('/api/videos')
                .then(response => response.json())
                .then(data => {
                    const videosList = document.getElementById('videos-list');
                    videosList.innerHTML = '';
                    
                    if (data.length === 0) {
                        videosList.innerHTML = '<p>No videos generated yet.</p>';
                    } else {
                        data.forEach(video => {
                            const videoCard = document.createElement('div');
                            videoCard.className = 'card mb-3';
                            videoCard.innerHTML = `
                                <div class="card-body">
                                    <h5 class="card-title">${video.title}</h5>
                                    <p class="card-text">${video.description}</p>
                                    <p class="card-text">
                                        <strong>Language:</strong> ${video.language}<br>
                                        <strong>Duration:</strong> ${video.duration_seconds ? video.duration_seconds + ' seconds' : 'N/A'}<br>
                                        <strong>File:</strong> ${video.file_path.split('/').pop()}
                                    </p>
                                    <div class="mb-2">
                                        <strong>Upload Status:</strong><br>
                                        <span class="badge ${video.is_uploaded ? 'bg-success' : 'bg-secondary'}">Uploaded: ${video.is_uploaded ? 'Yes' : 'No'}</span>
                                    </div>
                                </div>
                            `;
                            videosList.appendChild(videoCard);
                        });
                    }
                })
                .catch(error => {
                    console.error('Error loading videos:', error);
                    document.getElementById('videos-list').innerHTML = '<p>Error loading videos.</p>';
                });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


# Mount static files if needed
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except:
    # Static directory might not exist yet
    pass