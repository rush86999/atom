# MCP Web Search Setup

Enable agents to perform web searches and access web content.

## Environment Variables

Set one of these for web search (without them, mock data is returned):

| Variable | Description |
|----------|-------------|
| `TAVILY_API_KEY` | [Tavily Search API](https://tavily.com) (recommended) |
| `BRAVE_SEARCH_API_KEY` | [Brave Search API](https://brave.com/search/api/) |

## Local Development

Add to your `.env` file:
```bash
TAVILY_API_KEY=your_tavily_key
# OR
BRAVE_SEARCH_API_KEY=your_brave_key
```

## Production (Fly.io)

```bash
fly secrets set TAVILY_API_KEY=your_key
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/mcp/search?query=...` | Web search |
| `GET /api/mcp/servers` | List active MCP servers |
| `POST /api/mcp/execute` | Execute MCP tool |

## Testing

```bash
curl "http://localhost:8000/api/mcp/search?query=AI%20trends%202025"
```
