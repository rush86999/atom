#!/bin/bash
# PostgreSQL Docker for Atom Production Orchestrator
echo "🗄️ DEPLOYING POSTGRESQL FOR ATOM ORCHESTRATION"

# PostgreSQL Config
docker run --rm -d \
  --name atom-postgres \
  -e POSTGRES_DB=atom_production \
  -e POSTGRES_USER=atom_user \
  -e POSTGRES_PASSWORD=atom_secure_2024 \
  -p 5432:5432 \
  postgres:15-alpine

echo "✅ PostgreSQL Active on port 5432"
echo "Database: atom_production"
echo "User: atom_user"
echo "Docker: atom-postgres"
