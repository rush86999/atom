# Skill Marketplace Guide

The Atom Skill Marketplace is a centralized hub for discovering, evaluating, and installing community skills. This guide covers everything you need to know about finding, installing, and contributing skills.

---

## Table of Contents

1. [Overview](#overview)
2. [Browsing the Marketplace](#browsing-the-marketplace)
3. [Skill Details](#skill-details)
4. [Rating Skills](#rating-skills)
5. [Installing Skills](#installing-skills)
6. [Skill Governance](#skill-governance)
7. [Publishing Skills](#publishing-skills)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)
10. [API Reference](#api-reference)

---

## Overview

The Skill Marketplace provides:

- **Discovery**: Search and browse skills by category, type, and popularity
- **Ratings**: Community-driven 1-5 star ratings with reviews
- **Installation**: One-click installation with automatic dependency management
- **Governance**: Maturity-based access control for security
- **Categories**: Organized by domain (data, automation, integration, etc.)
- **Local Storage**: PostgreSQL-based marketplace with Atom SaaS sync architecture (future)

**Architecture**:
```
Local PostgreSQL Marketplace (Primary)
  ├─ Search: Full-text search on skill_id and description
  ├─ Ratings: Community ratings stored locally
  ├─ Categories: Aggregated from skill metadata
  └─ Installation: Integrates with SkillRegistryService

Future: Atom SaaS API Sync (when available)
  └─ Sync skills, ratings, and categories with cloud marketplace
```

---

## Browsing the Marketplace

### Search Skills

Search by name, description, or category:

```bash
curl "http://localhost:8000/marketplace/skills?query=data&sort_by=relevance"
```

**Response**:
```json
{
  "skills": [
    {
      "id": "abc-123",
      "skill_id": "csv-data-processor",
      "skill_name": "CSV Data Processor",
      "skill_type": "python_code",
      "description": "Process CSV files with pandas",
      "category": "data",
      "tags": ["csv", "pandas", "data-processing"],
      "author": "community",
      "version": "1.0.0",
      "status": "Active",
      "avg_rating": 4.5,
      "rating_count": 12,
      "created_at": "2026-02-19T12:00:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20,
  "total_pages": 1,
  "source": "local"
}
```

**Search Implementation**:
- Uses PostgreSQL full-text search on `skill_id` and `description`
- Ranking by relevance (search term frequency)
- Case-insensitive matching
- Partial word matching supported

### Filter by Category

Available categories:

| Category | Description | Example Skills |
|----------|-------------|----------------|
| `data` | Data processing and analysis | CSV processor, JSON transformer |
| `automation` | Workflow automation | Task scheduler, batch processor |
| `integration` | Third-party integrations | Slack bot, GitHub integration |
| `communication` | Email, messaging, notifications | Email sender, SMS notifier |
| `analysis` | Data analysis and reporting | Sentiment analyzer, trend detector |
| `productivity` | Utility and productivity tools | File organizer, note taker |
| `scraping` | Web scraping and data extraction | HTML scraper, API fetcher |

```bash
curl "http://localhost:8000/marketplace/skills?category=data"
```

### Filter by Skill Type

- `prompt_only` - LLM prompt skills (no code execution)
- `python_code` - Python code skills (sandboxed)
- `nodejs_code` - Node.js code skills (sandboxed)

```bash
# Prompt-only skills (safe for all agents)
curl "http://localhost:8000/marketplace/skills?skill_type=prompt_only"

# Python code skills (require INTERN+)
curl "http://localhost:8000/marketplace/skills?skill_type=python_code"

# Node.js code skills (require INTERN+)
curl "http://localhost:8000/marketplace/skills?skill_type=nodejs_code"
```

### Sort Results

- `relevance` - Search relevance (default)
- `created` - Newest first
- `name` - Alphabetical
- `rating` - Highest rated
- `downloads` - Most downloaded

```bash
curl "http://localhost:8000/marketplace/skills?sort_by=rating"
curl "http://localhost:8000/marketplace/skills?sort_by=created"
curl "http://localhost:8000/marketplace/skills?sort_by=name"
```

### Pagination

Control page size and number:

```bash
# First page with 10 results
curl "http://localhost:8000/marketplace/skills?page=1&page_size=10"

# Second page with 50 results
curl "http://localhost:8000/marketplace/skills?page=2&page_size=50"
```

**Limits**:
- Default page size: 20
- Maximum page size: 100
- Recommended page size: 20-50 for performance

---

## Skill Details

Get detailed information about a specific skill:

```bash
curl "http://localhost:8000/marketplace/skills/{skill_id}"
```

**Response**:
```json
{
  "id": "abc-123",
  "skill_id": "csv-data-processor",
  "skill_name": "CSV Data Processor",
  "skill_type": "python_code",
  "description": "Process CSV files with pandas",
  "long_description": "This skill reads CSV files, performs data transformations, and exports results. Supports filtering, aggregation, and format conversion.",
  "category": "data",
  "tags": ["csv", "pandas", "data-processing", "export"],
  "author": "community-contributor",
  "version": "1.0.0",
  "created_at": "2026-02-19T12:00:00Z",
  "updated_at": "2026-02-19T14:30:00Z",
  "status": "Active",
  "sandbox_enabled": true,
  "security_scan_result": "LOW",
  "packages": ["pandas==2.0.0", "numpy>=1.24.0"],
  "node_packages": [],
  "avg_rating": 4.5,
  "rating_count": 12,
  "ratings": [
    {
      "user_id": "agent-123",
      "rating": 5,
      "comment": "Excellent skill, saved me hours of work!",
      "created_at": "2026-02-19T13:00:00Z"
    },
    {
      "user_id": "agent-456",
      "rating": 4,
      "comment": "Works well, but could use better error handling",
      "created_at": "2026-02-19T12:30:00Z"
    }
  ],
  "execution_count": 156,
  "installations": 42,
  "skill_source": "community"
}
```

**Field Descriptions**:

| Field | Description |
|-------|-------------|
| `id` | Internal database ID |
| `skill_id` | Unique skill identifier (used in API calls) |
| `skill_name` | Human-readable skill name |
| `skill_type` | prompt_only, python_code, or nodejs_code |
| `description` | Short description (1-2 sentences) |
| `category` | Skill category (data, automation, etc.) |
| `tags` | Array of tags for discovery |
| `packages` | Python package dependencies |
| `node_packages` | npm package dependencies |
| `avg_rating` | Average rating (1-5 stars) |
| `rating_count` | Number of ratings |
| `security_scan_result` | CRITICAL, HIGH, MEDIUM, LOW (from LLM scan) |
| `status` | Active, Untrusted, or Banned |
| `execution_count` | Total times skill has been executed |
| `installations` | Number of times skill has been installed |

---

## Rating Skills

Submit a rating (1-5 stars) with optional comment:

```bash
curl -X POST "http://localhost:8000/marketplace/skills/{skill_id}/rate" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "my-agent",
    "rating": 5,
    "comment": "Excellent skill, saved me hours!"
  }'
```

**Response**:
```json
{
  "success": true,
  "action": "created",
  "average_rating": 4.6,
  "rating_count": 13
}
```

### Rating Guidelines

| Stars | Description | When to Use |
|-------|-------------|-------------|
| **5 stars** | Perfect - works flawlessly | Well-documented, no bugs, excellent performance |
| **4 stars** | Good - minor issues | Works well with small bugs or documentation gaps |
| **3 stars** | Average - functional | Works but has significant issues or poor docs |
| **2 stars** | Poor - major issues | Barely functional, missing features |
| **1 star** | Broken - unusable | Crashes, dangerous, or doesn't work |

**Tips for Good Ratings**:
1. **Be specific**: Explain what worked or didn't work
2. **Include context**: Mention your use case and environment
3. **Update ratings**: Re-rate after skill updates
4. **Report issues**: Use comments to report bugs or security concerns

### Updating Ratings

Submit a new rating to update your previous rating:

```bash
curl -X POST "http://localhost:8000/marketplace/skills/{skill_id}/rate" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "my-agent",
    "rating": 4,
    "comment": "Updated after testing - reduced to 4 stars due to performance issue"
  }'
```

**Response**:
```json
{
  "success": true,
  "action": "updated",
  "average_rating": 4.5,
  "rating_count": 13
}
```

---

## Installing Skills

### Basic Installation

Install a skill with automatic dependency installation:

```bash
curl -X POST "http://localhost:8000/marketplace/skills/{skill_id}/install" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "my-agent",
    "auto_install_deps": true
  }'
```

**Response**:
```json
{
  "success": true,
  "skill_id": "csv-data-processor",
  "agent_id": "my-agent",
  "message": "Skill installed successfully",
  "packages_installed": [
    {
      "name": "pandas",
      "version": "2.0.0",
      "package_type": "python"
    },
    {
      "name": "numpy",
      "version": "1.24.0",
      "package_type": "python"
    }
  ],
  "vulnerabilities": [],
  "installation_time_seconds": 4.2
}
```

### Manual Dependency Installation

If `auto_install_deps=false`, install dependencies separately:

```bash
# 1. Check dependencies first
curl "http://localhost:8000/marketplace/skills/{skill_id}"

# 2. Note packages from response:
#    "packages": ["pandas==2.0.0", "numpy>=1.24.0"]
#    "node_packages": []

# 3. Install manually via auto-install API
curl -X POST "http://localhost:8000/auto-install/install" \
  -H "Content-Type: application/json" \
  -d '{
    "skill_id": "my-skill",
    "packages": ["pandas==2.0.0", "numpy>=1.24.0"],
    "package_type": "python",
    "agent_id": "my-agent"
  }'
```

### Installation Workflow

```
1. Request Installation
   ↓
2. Fetch Skill Metadata
   ↓
3. Governance Check
   ├─ STUDENT: Blocked from code skills
   ├─ INTERN: Requires approval
   └─ SUPERVISED/AUTONOMOUS: Allowed if package approved
   ↓
4. Install Python Packages (if any)
   ├─ Vulnerability scan (pip-audit)
   ├─ Dependency conflict detection
   └─ Docker image build
   ↓
5. Install npm Packages (if any)
   ├─ Vulnerability scan (npm audit)
   ├─ Script analysis (block malware)
   └─ Docker image build
   ↓
6. Create Skill Record
   ↓
7. Return Success
```

### Installation Errors

**Dependency Conflict**:
```json
{
  "success": false,
  "error": "Dependency conflicts detected",
  "conflicts": [
    {
      "package": "pandas",
      "conflicting_versions": ["==2.0.0", ">=1.21.0,<2.0.0"]
    }
  ]
}
```

**Solution**: Resolve version conflicts manually or contact skill author

**Vulnerabilities Found**:
```json
{
  "success": false,
  "error": "Vulnerabilities detected",
  "vulnerabilities": [
    {
      "package": "requests",
      "version": "2.20.0",
      "cve": "CVE-2019-11324",
      "severity": "HIGH"
    }
  ]
}
```

**Solution**: Update package to safe version or approve via governance

---

## Skill Governance

### Maturity Requirements

| Skill Type | Minimum Maturity | Notes |
|------------|------------------|-------|
| **prompt_only** | STUDENT | Safe for all agents |
| **python_code** | INTERN | Requires approval, runs in sandbox |
| **nodejs_code** | INTERN | Requires approval, runs in sandbox |

**Package Governance**:

| Agent Level | Python Packages | npm Packages |
|-------------|----------------|--------------|
| **STUDENT** | ❌ Blocked | ❌ Blocked |
| **INTERN** | ⚠️ Approval Required | ⚠️ Approval Required |
| **SUPERVISED** | ✅ If approved | ✅ If approved |
| **AUTONOMOUS** | ✅ If approved | ✅ If approved |

**Banned packages block all agents regardless of maturity.**

### Security Scanning

All marketplace skills are scanned before listing:

**Scan Types**:
1. **Code Patterns Analysis** - 21+ malicious patterns detected
   - Subprocess usage (arbitrary command execution)
   - eval/exec (code injection)
   - Network access (data exfiltration)
   - Base64 obfuscation (payload hiding)
   - File system access (container escape)

2. **Dependency Vulnerability Check**
   - Python: pip-audit (PyPI/GitHub advisories)
   - npm: npm audit (known vulnerabilities)

3. **LLM Semantic Analysis**
   - GPT-4 powered threat detection
   - Contextual understanding of malicious intent

**Security Levels**:

| Level | Description | Action |
|-------|-------------|--------|
| **CRITICAL** | Known malware or CVE | Auto-ban |
| **HIGH** | Suspicious patterns | Manual review required |
| **MEDIUM** | Minor concerns | Use with caution |
| **LOW** | No issues detected | Safe to use |

### Skill Status

| Status | Description | Can Execute? |
|--------|-------------|--------------|
| **Active** | Passed security scan, approved | ✅ Yes |
| **Untrusted** | Failed scan, pending review | ❌ No |
| **Banned** | Malicious or dangerous | ❌ No (permanent) |

**Promoting Skills**:
```bash
curl -X POST "http://localhost:8000/api/skills/{skill_id}/promote" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "Active",
    "reason": "Manual review completed - skill is safe"
  }'
```

---

## Publishing Skills

### Prepare Your Skill

Create a `SKILL.md` file with YAML frontmatter:

```yaml
---
name: "CSV Data Processor"
description: "Process CSV files with pandas and numpy"
category: data
skill_type: python_code
packages:
  - pandas==2.0.0
  - numpy>=1.24.0
tags:
  - csv
  - data-processing
  - pandas
  - export
author: "your-name"
version: "1.0.0"
---

This skill reads CSV files, performs transformations, and exports results.

## Usage

```python
import pandas as pd
import numpy as np

def process_csv(file_path, operations):
    """
    Process CSV file with specified operations.

    Args:
        file_path: Path to CSV file
        operations: List of operations (filter, aggregate, transform)

    Returns:
        Processed data
    """
    data = pd.read_csv(file_path)

    for op in operations:
        if op["type"] == "filter":
            data = data[data[op["column"]] == op["value"]]
        elif op["type"] == "aggregate":
            data = data.groupby(op["column"]).sum()

    return data.to_dict()
```

## Example

```python
result = process_csv(
    "/data/sales.csv",
    [
        {"type": "filter", "column": "region", "value": "West"},
        {"type": "aggregate", "column": "product"}
    ]
)
```
```

### Submit to Marketplace

1. **Use the skills import API**:
```bash
curl -X POST "http://localhost:8000/api/skills/import" \
  -H "Content-Type: application/json" \
  -d '{
    "source": "github_url",
    "url": "https://github.com/your-org/skills/blob/main/csv-processor/SKILL.md",
    "metadata": {
      "author": "your-name",
      "repository": "https://github.com/your-org/skills"
    }
  }'
```

2. **Wait for security scan** (automatic):
```bash
curl "http://localhost:8000/api/skills/csv-processor"
```

3. **Review scan results**:
```json
{
  "skill_id": "csv-processor",
  "status": "Untrusted",
  "security_scan_result": "LOW",
  "security_scan_details": {
    "malicious_patterns": [],
    "vulnerabilities": [],
    "recommendation": "Safe to promote to Active"
  }
}
```

4. **Promote to Active** (if scan passed):
```bash
curl -X POST "http://localhost:8000/api/skills/csv-processor/promote" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "Active",
    "reason": "Security scan passed, manual review completed"
  }'
```

### Skill Publishing Best Practices

**1. Clear Descriptions**
- Explain what the skill does in 1-2 sentences
- Provide usage examples
- Document all parameters
- Include error handling notes

**2. Minimal Dependencies**
- Only include necessary packages
- Use exact version pinning (`==`) for reproducibility
- Document why each package is needed

**3. Error Handling**
- Validate inputs
- Provide meaningful error messages
- Handle edge cases gracefully
- Log errors for debugging

**4. Testing**
- Test skill in sandbox before publishing
- Test with various input types
- Test error conditions
- Include test cases in documentation

**5. Documentation**
- Provide clear usage examples
- Document all parameters
- Explain error conditions
- Include troubleshooting section

---

## Best Practices

### Finding Quality Skills

**1. Check Ratings**
- Prefer skills with 4+ stars
- Look for multiple ratings (not just one)
- Read recent reviews

**2. Review Code**
- Inspect skill code before installation
- Check for suspicious patterns
- Verify dependencies are safe

**3. Verify Dependencies**
- Check for excessive or suspicious packages
- Look for outdated versions
- Verify package maintainers

**4. Test First**
- Run skills in development before production
- Test with representative data
- Monitor for performance issues

**5. Check Security**
- Review security scan results
- Look for HIGH or CRITICAL findings
- Check for known vulnerabilities

### Publishing Quality Skills

**1. Clear Naming**
- Use descriptive, concise names
- Avoid generic names (e.g., "data-processor")
- Include domain in name (e.g., "csv-data-processor")

**2. Proper Categorization**
- Choose most appropriate category
- Add relevant tags for discoverability
- Update category if skill evolves

**3. Version Management**
- Use semantic versioning (MAJOR.MINOR.PATCH)
- Update version for breaking changes
- Document version history

**4. Responsive Maintenance**
- Respond to rating comments
- Fix reported bugs quickly
- Update dependencies regularly

**5. Community Engagement**
- Encourage feedback via ratings
- Document known issues
- Provide support channels

---

## Troubleshooting

### Installation Fails

**Problem**: Installation fails with dependency conflict

**Solutions**:
1. Check skill's required packages:
   ```bash
   curl "http://localhost:8000/marketplace/skills/{skill_id}" | jq '.packages, .node_packages'
   ```

2. Verify compatibility with your existing packages:
   ```bash
   # Check Python packages
   pip-audit --requirement <(echo "pandas==2.0.0 numpy>=1.24.0")

   # Check npm packages
   npm audit --json
   ```

3. Contact skill author about the conflict:
   - Open issue on their repository
   - Request version compatibility update
   - Consider forking and fixing

### Skill Not Found

**Problem**: Skill appears in marketplace but installation fails

**Solutions**:
1. Verify skill status is "Active":
   ```bash
   curl "http://localhost:8000/marketplace/skills/{skill_id}" | jq '.status'
   ```

2. Check if packages are compatible with your system:
   ```bash
   # Python version compatibility
   python --version  # Should be 3.11+
   ```

3. Review error message for specific issue:
   ```bash
   curl "http://localhost:8000/auto-install/status/{skill_id}" | jq '.error'
   ```

### Ratings Not Showing

**Problem**: Your rating doesn't appear in skill details

**Solutions**:
1. Allow time for rating aggregation (usually <1 second)
2. Refresh skill details page:
   ```bash
   curl "http://localhost:8000/marketplace/skills/{skill_id}"
   ```

3. Check that rating was submitted successfully:
   ```bash
   # Submit rating again - will update if exists
   curl -X POST "http://localhost:8000/marketplace/skills/{skill_id}/rate" \
     -H "Content-Type: application/json" \
     -d '{"user_id": "my-agent", "rating": 5}'
   ```

### Search Returns No Results

**Problem**: Search queries return empty results

**Solutions**:
1. Check spelling of search terms
2. Try broader search terms:
   ```bash
   # Too specific
   curl "http://localhost:8000/marketplace/skills?query=csv-data-processor-with-pandas"

   # Better
   curl "http://localhost:8000/marketplace/skills?query=csv"
   ```

3. Browse by category instead:
   ```bash
   curl "http://localhost:8000/marketplace/skills?category=data"
   ```

4. Check if any skills are imported:
   ```bash
   curl "http://localhost:8000/api/skills/list?status=Active"
   ```

### Security Scan Blocks Installation

**Problem**: Skill blocked due to security scan

**Solutions**:
1. Review scan results:
   ```bash
   curl "http://localhost:8000/api/skills/{skill_id}" | jq '.security_scan_details'
   ```

2. Check for malicious patterns:
   - Subprocess usage
   - Network access
   - File system operations
   - Obfuscated code

3. Verify with skill author:
   - Open security issue on repository
   - Request code review
   - Consider alternative skill

4. Manual approval (if safe):
   ```bash
   curl -X POST "http://localhost:8000/api/skills/{skill_id}/promote" \
     -H "Content-Type: application/json" \
     -d '{"status": "Active", "reason": "Manual review completed - no actual threat"}'
   ```

---

## API Reference

### Search Skills

```bash
GET /marketplace/skills
```

**Query Parameters**:
- `query`: Search string (optional)
- `category`: Filter by category (optional)
- `skill_type`: prompt_only, python_code, nodejs_code (optional)
- `sort_by`: relevance, created, name, rating (optional)
- `page`: Page number (default: 1)
- `page_size`: Items per page (default: 20, max: 100)

**Response**: Paginated list of skills

### Get Skill Details

```bash
GET /marketplace/skills/{skill_id}
```

**Response**: Full skill object with ratings

### Get Categories

```bash
GET /marketplace/categories
```

**Response**: List of categories with skill counts

### Rate Skill

```bash
POST /marketplace/skills/{skill_id}/rate
Content-Type: application/json

{
  "user_id": "my-agent",
  "rating": 5,
  "comment": "Excellent!"
}
```

**Response**: Updated rating information

### Install Skill

```bash
POST /marketplace/skills/{skill_id}/install
Content-Type: application/json

{
  "agent_id": "my-agent",
  "auto_install_deps": true
}
```

**Response**: Installation result with package details

---

## Summary

The Atom Skill Marketplace provides a centralized, secure platform for discovering and installing community skills. Key features:

- ✅ PostgreSQL-based search with full-text matching
- ✅ Community ratings and reviews
- ✅ Automatic dependency installation
- ✅ Comprehensive security scanning
- ✅ Maturity-based governance
- ✅ Category-based organization

**Next Steps**:
1. Browse marketplace to discover skills
2. Install skills with auto-dependency management
3. Rate skills to provide community feedback
4. Publish your own skills to share with community

---

**See Also**:
- [Advanced Skill Execution](./ADVANCED_SKILL_EXECUTION.md) - Overview of Phase 60 features
- [Skill Composition Patterns](./SKILL_COMPOSITION_PATTERNS.md) - Workflow design patterns
- [Community Skills](./COMMUNITY_SKILLS.md) - Phase 14 foundation

**Last Updated**: February 19, 2026
