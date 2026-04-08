# Canvas Component Marketplace Guide

**Last Updated:** 2026-04-07

Learn how to browse, install, and use canvas components from the atomagentos.com marketplace.

⚠️ **Commercial Service:** Canvas components are proprietary content from the atomagentos.com marketplace. Requires valid API token. See [LICENSE.md](../../LICENSE.md#marketplace-commercial-appendix) for details.

## Overview

Canvas components are reusable UI elements that agents can use to create rich, interactive presentations. The marketplace provides hundreds of professionally designed components for every use case.

### Component Categories

- **📊 Charts** - Data visualization (Line, Bar, Pie, Area, Scatter)
- **📝 Forms** - Interactive forms (Input forms, surveys, configurations)
- **📋 Tables** - Data display (Grids, pivot tables, sortable lists)
- **📄 Markdown** - Rich text and documentation
- **🖼️ Media** - Images, videos, audio players
- **🎮 Interactive** - Custom widgets, calculators, sliders
- **📐 Layouts** - Grid systems, containers, spacers

## Quick Start

### 1. Browse Available Components

```bash
# List all components
curl http://localhost:8000/api/v1/marketplace/components

# Filter by category
curl http://localhost:8000/api/v1/marketplace/components?category=charts

# Search by name
curl http://localhost:8000/api/v1/marketplace/components?query=line+chart
```

**Response:**
```json
{
  "components": [
    {
      "id": "comp_line_chart_001",
      "name": "Line Chart Pro",
      "description": "Professional line chart with zoom and pan",
      "category": "charts",
      "component_type": "react",
      "version": "2.1.0",
      "author": "atomagentos",
      "rating": 4.8,
      "installs": 1250,
      "price": 0.0,
      "tags": ["chart", "visualization", "data"]
    }
  ],
  "total": 1,
  "page": 1
}
```

### 2. Get Component Details

```bash
# Get full component details
curl http://localhost:8000/api/v1/marketplace/components/comp_line_chart_001
```

**Response:**
```json
{
  "id": "comp_line_chart_001",
  "name": "Line Chart Pro",
  "description": "Professional line chart with zoom and pan support",
  "long_description": "Advanced line chart component with...",

  "component_type": "react",
  "category": "charts",
  "version": "2.1.0",

  "config_schema": {
    "type": "object",
    "properties": {
      "data": {"type": "array"},
      "xKey": {"type": "string"},
      "yKey": {"type": "string"},
      "color": {"type": "string"},
      "showZoom": {"type": "boolean"}
    }
  },

  "dependencies": [
    {"name": "recharts", "version": "^2.10.0"}
  ],

  "preview_url": "https://atomagentos.com/components/comp_line_chart_001/preview",
  "thumbnail_url": "https://atomagentos.com/components/comp_line_chart_001/thumb.png",

  "author": "atomagentos",
  "license": "Proprietary",
  "rating": 4.8,
  "rating_count": 125,
  "installs": 1250,
  "created_at": "2026-03-15T10:00:00Z"
}
```

### 3. Install a Component

```bash
# Install component to a canvas
curl -X POST http://localhost:8000/api/v1/marketplace/components/comp_line_chart_001/install \
  -H "Content-Type: application/json" \
  -d '{
    "canvas_id": "your_canvas_id"
  }'
```

**Response:**
```json
{
  "success": true,
  "installation_id": "inst_abc123",
  "component_name": "Line Chart Pro",
  "message": "Component installed successfully"
}
```

### 4. Use Component in Canvas

After installation, the component is available for use in your canvas:

```python
from core.canvas_tool import CanvasTool

canvas = CanvasTool(db)

# Add the installed component to your canvas
canvas.add_component(
    canvas_id="your_canvas_id",
    component_id="comp_line_chart_001",
    config={
        "data": sales_data,
        "xKey": "month",
        "yKey": "revenue",
        "color": "#3b82f6",
        "showZoom": True
    },
    position={"x": 0, "y": 0, "width": 12, "height": 6}
)
```

## Component Types

### Charts Components

**Line Chart**
```json
{
  "component_id": "comp_line_chart_001",
  "config": {
    "data": [{"month": "Jan", "value": 100}, ...],
    "xKey": "month",
    "yKey": "value",
    "color": "#3b82f6"
  }
}
```

**Bar Chart**
```json
{
  "component_id": "comp_bar_chart_001",
  "config": {
    "data": [{"category": "A", "value": 100}, ...],
    "xKey": "category",
    "yKey": "value",
    "orientation": "vertical"
  }
}
```

**Pie Chart**
```json
{
  "component_id": "comp_pie_chart_001",
  "config": {
    "data": [{"label": "A", "value": 30}, ...],
    "labelKey": "label",
    "valueKey": "value"
  }
}
```

### Form Components

**Text Input Form**
```json
{
  "component_id": "comp_form_text_001",
  "config": {
    "fields": [
      {"name": "email", "type": "email", "label": "Email", "required": true},
      {"name": "message", "type": "textarea", "label": "Message"}
    ],
    "submit_url": "/api/forms/contact"
  }
}
```

**Survey Form**
```json
{
  "component_id": "comp_form_survey_001",
  "config": {
    "title": "Customer Satisfaction Survey",
    "questions": [
      {"id": "q1", "type": "rating", "question": "How satisfied are you?"},
      {"id": "q2", "type": "text", "question": "Any feedback?"}
    ]
  }
}
```

### Table Components

**Data Grid**
```json
{
  "component_id": "comp_table_grid_001",
  "config": {
    "data": [...],
    "columns": [
      {"field": "name", "header": "Name", "sortable": true},
      {"field": "status", "header": "Status", "filterable": true}
    ],
    "pagination": true,
    "pageSize": 20
  }
}
```

### Interactive Components

**Calculator**
```json
{
  "component_id": "comp_calc_basic_001",
  "config": {
    "operations": ["+", "-", "*", "/"],
    "memory": true
  }
}
```

**Slider Control**
```json
{
  "component_id": "comp_slider_range_001",
  "config": {
    "min": 0,
    "max": 100,
    "step": 1,
    "defaultValue": 50
  }
}
```

## Configuration Schema

Each component defines a JSON schema for its configuration:

```json
{
  "config_schema": {
    "type": "object",
    "properties": {
      "data": {
        "type": "array",
        "description": "Data to display"
      },
      "color": {
        "type": "string",
        "description": "Primary color (hex)",
        "default": "#3b82f6"
      },
      "showLegend": {
        "type": "boolean",
        "description": "Show legend",
        "default": true
      }
    },
    "required": ["data"]
  }
}
```

## Installation Options

### Install with Default Configuration

```bash
curl -X POST http://localhost:8000/api/v1/marketplace/components/{component_id}/install \
  -H "Content-Type: application/json" \
  -d '{
    "canvas_id": "your_canvas_id"
  }'
```

### Install with Custom Configuration

```bash
curl -X POST http://localhost:8000/api/v1/marketplace/components/{component_id}/install \
  -H "Content-Type: application/json" \
  -d '{
    "canvas_id": "your_canvas_id",
    "config": {
      "color": "#ef4444",
      "showLegend": false
    },
    "position": {
      "x": 0,
      "y": 0,
      "width": 12,
      "height": 6
    }
  }'
```

### Install Multiple Components

```bash
# Install multiple components at once
for component in comp_line_chart_001 comp_bar_chart_001 comp_table_grid_001; do
  curl -X POST http://localhost:8000/api/v1/marketplace/components/$component/install \
    -H "Content-Type: application/json" \
    -d "{\"canvas_id\": \"your_canvas_id\"}"
done
```

## Component Lifecycle

### Installation

When you install a component:
1. Component metadata is fetched from atomagentos.com
2. Component code and dependencies are downloaded
3. Component is stored in local database
4. Installation record is created
5. Usage is reported to mothership

### Usage

Components are used in canvas presentations:
- Agent creates canvas
- Agent adds installed components
- Components render with provided configuration
- User interacts with components
- Component actions trigger agent callbacks

### Updates

When component updates are available:
1. Check for updates: `GET /api/v1/marketplace/components/updates`
2. Update component: `POST /api/v1/marketplace/components/{id}/update`
3. Old version is preserved (rollback possible)

### Uninstallation

```bash
# Uninstall component from canvas
curl -X DELETE http://localhost:8000/api/v1/marketplace/components/{installation_id}
```

⚠️ **Note:** Uninstallation removes component from canvas but keeps component metadata in case other canvases use it.

## Troubleshooting

### Component Not Found

**Problem:** 404 when trying to install component

**Solutions:**
1. Verify component ID is correct
2. Check marketplace connection: `curl /api/v1/marketplace/health`
3. Ensure API token is valid
4. Component may have been removed from marketplace

### Installation Failed

**Problem:** Installation returns error

**Common causes:**
- Invalid configuration (doesn't match schema)
- Missing dependencies
- Canvas not found
- Insufficient permissions

**Solutions:**
1. Check component schema: `GET /api/v1/marketplace/components/{id}`
2. Verify config matches schema
3. Check logs: `tail -f logs/atom.log | grep component`
4. Ensure canvas exists

### Component Not Rendering

**Problem:** Component installed but not visible

**Solutions:**
1. Check component position (x, y, width, height)
2. Verify config data is valid
3. Check browser console for errors
4. Ensure dependencies are loaded

## Best Practices

### Component Selection

✅ **Do:**
- Choose components with high ratings (4.5+ stars)
- Check component installs and reviews
- Verify component matches your use case
- Test component in development first

❌ **Don't:**
- Install components with low ratings
- Use components without documentation
- Install more components than needed
- Ignore component dependencies

### Configuration

✅ **Do:**
- Follow component schema exactly
- Provide all required fields
- Validate data before passing to component
- Use sensible defaults

❌ **Don't:**
- Omit required configuration fields
- Pass invalid data types
- Hardcode configuration (use variables)
- Ignore component validation

### Performance

✅ **Do:**
- Lazy load components when possible
- Use pagination for large datasets
- Cache component configurations
- Monitor component performance

❌ **Don't:**
- Render too many components on one canvas
- Load large datasets without pagination
- Re-create components unnecessarily
- Ignore component memory usage

## API Reference

### Browse Components

```bash
GET /api/v1/marketplace/components

Query Parameters:
- limit: number of results (default: 20, max: 100)
- offset: pagination offset (default: 0)
- category: filter by category
- query: search by name/description
- sort: sort order (name, rating, installs, created)
```

### Get Component Details

```bash
GET /api/v1/marketplace/components/{component_id}

Returns:
- Full component metadata
- Configuration schema
- Dependencies
- Preview URLs
- Rating and install counts
```

### Install Component

```bash
POST /api/v1/marketplace/components/{component_id}/install

Body:
{
  "canvas_id": "string (required)",
  "config": "object (optional)",
  "position": {
    "x": "number (optional)",
    "y": "number (optional)",
    "width": "number (optional)",
    "height": "number (optional)"
  }
}

Returns:
{
  "success": true,
  "installation_id": "string",
  "component_name": "string"
}
```

### Uninstall Component

```bash
DELETE /api/v1/marketplace/components/installations/{installation_id}

Returns:
{
  "success": true
}
```

### Check for Updates

```bash
GET /api/v1/marketplace/components/updates

Returns:
{
  "updates_available": [
    {
      "component_id": "string",
      "current_version": "string",
      "latest_version": "string"
    }
  ]
}
```

## Examples

### Complete Example: Sales Dashboard

```bash
# 1. Create a new canvas
curl -X POST http://localhost:8000/api/canvases \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Sales Dashboard",
    "description": "Monthly sales performance"
  }'

# 2. Install components
components=(
  "comp_line_chart_001"  # Revenue trend
  "comp_bar_chart_001"   # Sales by region
  "comp_table_grid_001"   # Top deals
)

for component in "${components[@]}"; do
  curl -X POST "http://localhost:8000/api/v1/marketplace/components/$component/install" \
    -H "Content-Type: application/json" \
    -d "{\"canvas_id\": \"$canvas_id\"}"
done

# 3. Configure components
python << EOF
from core.canvas_tool import CanvasTool

canvas = CanvasTool(db)
canvas.add_component(
    canvas_id=canvas_id,
    component_id="comp_line_chart_001",
    config={
        "data": get_revenue_data(),
        "xKey": "month",
        "yKey": "revenue"
    },
    position={"x": 0, "y": 0, "width": 12, "height": 6}
)
EOF
```

### Complete Example: Customer Feedback Form

```bash
# 1. Install survey form component
curl -X POST http://localhost:8000/api/v1/marketplace/components/comp_form_survey_001/install \
  -H "Content-Type: application/json" \
  -d '{
    "canvas_id": "feedback_canvas",
    "config": {
      "title": "Customer Feedback",
      "questions": [
        {"id": "q1", "type": "rating", "question": "Overall satisfaction"},
        {"id": "q2", "type": "text", "question": "What can we improve?"}
      ],
      "submit_url": "/api/feedback/submit"
    }
  }'
```

## Support

### Documentation

**Marketplace Documentation:**
- **Connection Guide**: [connection.md](connection.md) - Marketplace setup and configuration
- **Domain Marketplace**: [domains.md](domains.md) - Domain marketplace guide
- **Skills Marketplace**: [skills.md](skills.md) - Skills marketplace guide

**Platform Documentation:**
- **Canvas System**: [canvas/recording.md](../canvas/recording.md) - Canvas system overview
- **Canvas Reference**: [canvas/reference.md](../canvas/reference.md) - Canvas API reference
- **Canvas AI**: [canvas/ai-accessibility.md](../canvas/ai-accessibility.md) - AI accessibility
- **Agent Learning**: [canvas/agent-learning.md](../canvas/agent-learning.md) - Agent learning from canvas

**Documentation Guides:**
- **Documentation Structure**: [DOCUMENTATION_STRUCTURE_GUIDE.md](../DOCUMENTATION_STRUCTURE_GUIDE.md) - Complete docs navigation guide
- **docs.atomagentos.com**: [DOCS_ATOMAGENTOS_GUIDE.md](../DOCS_ATOMAGENTOS_GUIDE.md) - Commercial platform docs

**Commercial Documentation:**
- **Component API**: https://docs.atomagentos.com/api/components - Component API reference
- **Account Management**: https://docs.atomagentos.com/account - API tokens, billing
- **Support Portal**: https://docs.atomagentos.com/support - Help center

### Community

- **Marketplace**: [https://atomagentos.com/marketplace/components](https://atomagentos.com/marketplace/components)
- **Documentation**: [https://docs.atomagentos.com/canvas](https://docs.atomagentos.com/canvas)
- **GitHub Issues**: [https://github.com/rush86999/atom/issues](https://github.com/rush86999/atom/issues)

---

**Version:** 1.0
**Platform:** Atom Open Source + atomagentos.com Marketplace
**Last Updated:** 2026-04-07
