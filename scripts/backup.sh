#!/bin/bash

set -e

# Manga Video Pipeline Backup Script

# Configuration
BACKUP_DIR="./data/backups"
DB_FILE="./data/manga_pipeline.db"
MAX_BACKUPS=7

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

function log() {
    echo -e "${GREEN}[INFO]$(date '+%Y-%m-%d %H:%M:%S')${NC} $1"
}

function error() {
    echo -e "${RED}[ERROR]$(date '+%Y-%m-%d %H:%M:%S')${NC} $1"
}

function create_backup() {
    log "Starting backup process..."
    
    # Create backup directory if it doesn't exist
    mkdir -p "$BACKUP_DIR"
    
    # Generate timestamp
    timestamp=$(date +"%Y%m%d_%H%M%S")
    
    # Create backup file name
    backup_file="$BACKUP_DIR/manga_pipeline_backup_${timestamp}.db"
    
    # Check if database file exists
    if [ ! -f "$DB_FILE" ]; then
        error "Database file $DB_FILE does not exist"
        exit 1
    fi
    
    # Create backup
    log "Creating backup: $backup_file"
    cp "$DB_FILE" "$backup_file"
    
    # Compress the backup
    log "Compressing backup..."
    gzip "$backup_file"
    backup_file="${backup_file}.gz"
    
    log "Backup created: $backup_file"
    
    # Cleanup old backups (keep last 7)
    cleanup_old_backups
}

function cleanup_old_backups() {
    log "Cleaning up old backups (keeping last $MAX_BACKUPS)..."
    
    # Count total backups
    total_backups=$(find "$BACKUP_DIR" -name "manga_pipeline_backup_*.db.gz" | wc -l)
    
    if [ "$total_backups" -gt "$MAX_BACKUPS" ]; then
        # Calculate how many to delete
        delete_count=$((total_backups - MAX_BACKUPS))
        
        # Get the oldest backups to delete
        backups_to_delete=$(find "$BACKUP_DIR" -name "manga_pipeline_backup_*.db.gz" -type f | sort | head -n "$delete_count")
        
        # Delete old backups
        for backup in $backups_to_delete; do
            log "Deleting old backup: $backup"
            rm "$backup"
        done
        
        log "Cleaned up $delete_count old backups"
    else
        log "No old backups to clean up"
    fi
}

function list_backups() {
    log "Listing existing backups:"
    if [ -d "$BACKUP_DIR" ]; then
        ls -la "$BACKUP_DIR"/*.gz 2>/dev/null || echo "No backups found"
    else
        echo "No backup directory found"
    fi
}

function restore_backup() {
    if [ $# -eq 0 ]; then
        error "Usage: $0 restore <backup_file>"
        exit 1
    fi
    
    backup_to_restore="$1"
    
    if [ ! -f "$backup_to_restore" ]; then
        error "Backup file $backup_to_restore does not exist"
        exit 1
    fi
    
    log "Restoring from $backup_to_restore"
    
    # Stop any running services that might be using the database
    log "Stopping services (if running)..."
    docker-compose -f docker-compose.prod.yml stop || true
    
    # Decompress the backup
    log "Decompressing backup..."
    gunzip -k "$backup_to_restore"
    
    # Extract the file name without .gz extension
    uncompressed_backup="${backup_to_restore%.gz}"
    
    # Copy to database location
    log "Restoring database..."
    cp "$uncompressed_backup" "$DB_FILE"
    
    # Remove the decompressed file (keep the original compressed one)
    rm "$uncompressed_backup"
    
    log "Database restored successfully"
}

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Handle script arguments
case "${1:-}" in
    create|backup)
        create_backup
        ;;
    list)
        list_backups
        ;;
    restore)
        restore_backup "$2"
        ;;
    clean)
        cleanup_old_backups
        ;;
    *)
        echo "Usage: $0 {create|list|restore|clean}"
        echo "  create/backup - Create a new backup"
        echo "  list - List existing backups"
        echo "  restore <backup_file> - Restore from a backup file"
        echo "  clean - Clean up old backups (keeping last 7)"
        exit 1
        ;;
esac