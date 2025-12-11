# Model Context Protocol (MCP) Integration

This document describes the MCP (Model Context Protocol) integration that has been added to the ATOM platform, allowing the main agent to connect to and utilize MCP servers for extended capabilities.

## Overview

The Model Context Protocol (MCP) enables secure communication between language models and external data sources. This integration provides:

- **Server Management**: Connect to, manage, and monitor MCP servers
- **Tool Discovery**: Automatically discover available tools from connected servers
- **Tool Execution**: Execute tools from MCP servers through the ATOM interface
- **Custom Server Support**: Add and configure custom MCP servers
- **Category Organization**: Browse servers by functional categories

## Features

### Built-in Server Support

The integration includes support for the most popular MCP servers:

#### Storage & File Systems
- **Filesystem** (`filesystem`) - File operations, directory navigation
- **Google Drive** (`google-drive`) - Cloud storage access

#### Database Connectivity
- **Database** (`database`) - SQL and NoSQL database operations
- **PostgreSQL** (`postgres`) - PostgreSQL database connectivity

#### Search & Information
- **Web Search** (`web-search`) - Real-time web search capabilities
- **Brave Search** (`brave-search`) - Brave search engine integration

#### Development Tools
- **Git** (`git`) - Repository operations, version control
- **GitHub** (`github`) - GitHub repository management

#### Communication
- **Slack** (`slack`) - Slack workspace integration
- **Email** (`email`) - Email communication tools

#### Infrastructure
- **Kubernetes** (`kubernetes`) - Container orchestration
- **Cloud Platforms** (`aws`, `azure`, `gcp`) - Cloud service management

#### Memory & Knowledge
- **Memory** (`memory`) - Knowledge graph and persistent storage
- **Fetch** (`fetch`) - Web content retrieval and API calls

### Server Categories

Servers are organized into these categories:

- **🗄️ Storage** - File systems and cloud storage
- **🔍 Search** - Search engines and information retrieval
- **🗃️ Database** - Database connectivity and management
- **💻 Development** - Development tools and repositories
- **🧠 Memory** - Knowledge storage and retrieval
- **🌐 Network** - Web content and API access
- **💬 Communication** - Messaging and collaboration
- **☸️ Infrastructure** - Cloud and container management
- **⚙️ Custom** - User-defined servers

## Architecture

### Backend Components

#### MCP Service (`backend/integrations/mcp_service.py`)
- Manages MCP server connections
- Handles tool discovery and execution
- Provides server configuration management

#### MCP Routes (`backend/integrations/mcp_routes.py`)
- REST API endpoints for MCP operations
- Proxy between frontend and MCP service
- HTTP interface for MCP functionality

### Frontend Components

#### MCP Integration Component (`frontend/components/integrations/MCPIntegration.tsx`)
- React component for MCP server management
- Server browsing and connection interface
- Tool execution interface
- Custom server configuration

#### API Routes (`frontend/pages/api/integrations/mcp/`)
- Proxy routes to backend MCP endpoints
- Health check, servers, connections, categories

### Service Registry

MCP servers are registered in the service registry (`backend/core/service_registry.py`):
```python
{
    "id": "mcp_servers",
    "name": "MCP Servers",
    "description": "Model Context Protocol servers for extended AI capabilities",
    "status": "available",
    "oauth_required": False
}
```

## API Endpoints

### Health & Status
- `GET /api/mcp/health` - Check MCP service health
- `GET /api/mcp/status` - Get MCP integration status

### Server Management
- `GET /api/mcp/servers` - List available servers
- `GET /api/mcp/servers/{server_id}` - Get server details
- `POST /api/mcp/servers/connect` - Connect to a server
- `POST /api/mcp/servers/disconnect` - Disconnect from a server
- `POST /api/mcp/servers/custom` - Add custom server

### Connections
- `GET /api/mcp/connections` - List active connections
- `GET /api/mcp/connections/{server_id}/tools` - Get server tools
- `POST /api/mcp/connections/{server_id}/tools/{tool_name}/execute` - Execute tool

### Organization
- `GET /api/mcp/categories` - Get server categories
- `GET /api/mcp/tools/all` - Get all available tools

## Usage Examples

### Connecting to a Server

```javascript
// Connect to filesystem MCP server
const response = await fetch('/api/mcp/servers/connect', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    server_id: 'filesystem',
    user_id: 'default_user'
  })
});

const result = await response.json();
console.log('Connected:', result.connection);
```

### Executing a Tool

```javascript
// Execute a file reading tool
const response = await fetch('/api/mcp/connections/filesystem/tools/read_file/execute', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    server_id: 'filesystem',
    tool_name: 'read_file',
    arguments: {
      path: '/path/to/file.txt'
    }
  })
});

const result = await response.json();
console.log('Tool result:', result.execution.result);
```

### Adding a Custom Server

```javascript
// Add custom MCP server
const response = await fetch('/api/mcp/servers/custom', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    server_id: 'my-custom-server',
    command: 'npx',
    args: ['@myorg/my-mcp-server', '--option', 'value'],
    description: 'My custom MCP server for specific functionality',
    category: 'custom',
    icon: '🔧'
  })
});

const result = await response.json();
console.log('Server added:', result.server);
```

## Configuration

### Environment Variables

```bash
# MCP Configuration
MCP_CONFIG_PATH=.mcp.json          # Path to MCP configuration file
MCP_SERVER_HOST=localhost          # MCP server host
MCP_SERVER_PORT=8001              # MCP server port
MCP_SERVER_TIMEOUT=30             # Connection timeout in seconds
```

### MCP Configuration File

The `.mcp.json` file stores custom server configurations:

```json
{
  "mcpServers": {
    "my-custom-server": {
      "command": "npx",
      "args": ["@myorg/my-mcp-server"],
      "description": "Custom server for specific functionality",
      "category": "custom",
      "icon": "🔧"
    }
  }
}
```

## Requirements

### Backend Dependencies

- `loguru` - Logging
- `mcp` - Model Context Protocol SDK (optional)
- `fastapi` - API framework
- `pydantic` - Data validation

### Frontend Dependencies

- React with TypeScript
- UI components (shadcn/ui)
- Lucide React icons

### MCP SDK Installation (Optional)

For full MCP server connectivity:

```bash
pip install mcp
```

Or use npm:

```bash
npm install -g @modelcontextprotocol/sdk
```

## Security Considerations

1. **Server Authentication**: MCP servers should implement proper authentication
2. **Tool Permissions**: Implement tool-level permission checks
3. **Input Validation**: Validate all tool arguments before execution
4. **Resource Limits**: Set appropriate resource limits for tool execution
5. **Audit Logging**: Log all MCP server connections and tool executions

## Troubleshooting

### Common Issues

#### MCP SDK Not Available
- Install the MCP SDK: `pip install mcp`
- The integration will work in limited mode without the SDK

#### Server Connection Failures
- Check server command and arguments
- Verify MCP server is installed and accessible
- Check network connectivity and firewall settings

#### Tool Execution Errors
- Validate tool arguments format (JSON)
- Check tool schema requirements
- Ensure proper server permissions

### Debug Mode

Enable debug logging by setting the log level:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Future Enhancements

1. **Server Templates** - Pre-configured server templates
2. **Tool Workflows** - Chain multiple tools into workflows
3. **Server Discovery** - Auto-discover available MCP servers
4. **Performance Monitoring** - Monitor server performance and usage
5. **Advanced Security** - Enhanced authentication and authorization
6. **Batch Operations** - Execute multiple tools in parallel
7. **Tool Caching** - Cache tool results for improved performance

## Contributing

To add new MCP server support:

1. Add server configuration to `mcp_service.py`
2. Update server categories and icons
3. Add appropriate error handling
4. Update documentation
5. Add tests for the new server

## References

- [Model Context Protocol Documentation](https://modelcontextprotocol.io/)
- [MCP SDK GitHub Repository](https://github.com/modelcontextprotocol/servers)
- [MCP Server List](https://github.com/awesome-mcp-servers)

---

**Last Updated**: December 10, 2025
**Version**: 1.0.0