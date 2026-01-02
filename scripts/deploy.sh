#!/bin/bash

set -e

# Manga Video Pipeline Deployment Script

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

function log() {
    echo -e "${GREEN}[INFO]$(date '+%Y-%m-%d %H:%M:%S')${NC} $1"
}

function warn() {
    echo -e "${YELLOW}[WARN]$(date '+%Y-%m-%d %H:%M:%S')${NC} $1"
}

function error() {
    echo -e "${RED}[ERROR]$(date '+%Y-%m-%d %H:%M:%S')${NC} $1"
}

function health_check() {
    log "Performing health check..."
    sleep 10  # Give services time to start
    
    for i in {1..10}; do
        if curl -f http://localhost:8000/health >/dev/null 2>&1; then
            log "Health check passed"
            return 0
        fi
        warn "Health check attempt $i failed, retrying in 10 seconds..."
        sleep 10
    done
    
    error "Health check failed after 10 attempts"
    return 1
}

function backup_database() {
    log "Backing up database..."
    if [ -f "./data/manga_pipeline.db" ]; then
        timestamp=$(date +"%Y%m%d_%H%M%S")
        backup_file="./data/backups/manga_pipeline_backup_${timestamp}.db"
        mkdir -p ./data/backups
        cp ./data/manga_pipeline.db "$backup_file"
        log "Database backed up to $backup_file"
    else
        warn "Database file not found, skipping backup"
    fi
}

function check_prerequisites() {
    log "Checking prerequisites..."
    
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        error "Docker Compose is not installed"
        exit 1
    fi
    
    log "Prerequisites check passed"
}

function deploy() {
    log "Starting deployment process..."
    
    # Pull latest code
    log "Pulling latest code..."
    git pull origin main || {
        error "Failed to pull latest code"
        exit 1
    }
    
    # Backup database
    backup_database
    
    # Stop existing containers
    log "Stopping existing containers..."
    docker-compose -f docker-compose.prod.yml down || true
    
    # Build new images
    log "Building new images..."
    docker-compose -f docker-compose.prod.yml build --no-cache
    
    # Start services
    log "Starting services..."
    docker-compose -f docker-compose.prod.yml up -d
    
    # Verify deployment
    if health_check; then
        log "Deployment successful!"
        return 0
    else
        error "Deployment failed health check, rolling back..."
        rollback
        exit 1
    fi
}

function rollback() {
    error "Rolling back to previous version..."
    
    # Bring down current deployment
    docker-compose -f docker-compose.prod.yml down || true
    
    # Restore last known good backup
    if [ -f "./data/backups/manga_pipeline_backup_*.db" ]; then
        latest_backup=$(ls -t ./data/backups/manga_pipeline_backup_*.db | head -n1)
        if [ -n "$latest_backup" ]; then
            log "Restoring from backup: $latest_backup"
            cp "$latest_backup" ./data/manga_pipeline.db
        fi
    fi
    
    # Start previous version
    log "Restarting previous version..."
    docker-compose -f docker-compose.prod.yml up -d
    
    # Verify rollback
    if health_check; then
        log "Rollback successful"
    else
        error "Rollback failed"
        exit 1
    fi
}

function main() {
    log "Starting Manga Video Pipeline deployment"
    
    check_prerequisites
    deploy
    
    log "Deployment process completed"
}

# Handle script arguments
case "${1:-}" in
    rollback)
        rollback
        ;;
    backup)
        backup_database
        ;;
    *)
        main
        ;;
esac