#!/bin/bash
# Database Backup Script
# Generated: 2025-11-01 14:12:23

BACKUP_DIR="./backups"
DATE=$(date +%Y%m%d_%H%M%S)
DB_FILE="./data/atom_production.db"

echo "💾 Starting database backup..."

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup SQLite database
if [ -f "$DB_FILE" ]; then
    sqlite3 "$DB_FILE" ".backup $BACKUP_DIR/atom_backup_$DATE.db"
    echo "✅ Database backed up to: $BACKUP_DIR/atom_backup_$DATE.db"
else
    echo "❌ Database file not found: $DB_FILE"
    exit 1
fi

# Backup configuration files
tar -czf "$BACKUP_DIR/config_backup_$DATE.tar.gz" \
    .env.production \
    oauth_production_config.json

echo "✅ Configuration files backed up"

# Clean up old backups (keep last 7 days)
find "$BACKUP_DIR" -name "*.db" -mtime +7 -delete
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +7 -delete

echo "🧹 Old backups cleaned up"
echo "🎉 Backup completed successfully"
