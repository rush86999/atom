# Atom Search UI Guide

## Overview

The Atom Search UI provides advanced hybrid search capabilities across both web and desktop applications, powered by LanceDB for semantic and keyword-based search. This guide covers the search features available in both platforms.

## Web App Search Features

### Search Page
Access the search functionality at `/search` in the web application.

#### Key Features:
- **Hybrid Search**: Combines semantic (vector) and keyword search for optimal results
- **Real-time Suggestions**: Get search suggestions as you type
- **Advanced Filtering**: Filter by document type, relevance score, and tags
- **Search Types**:
  - **Hybrid**: Best overall results combining semantic and keyword matching
  - **Semantic**: Focus on meaning and context using vector embeddings
  - **Keyword**: Traditional text matching

#### Search Interface:
1. **Search Bar**: Enter your query with real-time suggestions
2. **Type Selector**: Choose between hybrid, semantic, or keyword search
3. **Filters Panel**:
   - Document Type (document, meeting, note, email, pdf)
   - Minimum Relevance Score (0-100%)
   - Date Range (coming soon)
4. **Results Display**:
   - Relevance scores for each result
   - Document metadata (author, creation date, tags)
   - Document type badges
   - Content preview

### API Endpoints

The web app connects to the following search endpoints:

- `POST /api/lancedb-search/hybrid` - Hybrid search
- `POST /api/lancedb-search/semantic` - Semantic search  
- `POST /api/lancedb-search/filter` - Filter-based search
- `GET /api/lancedb-search/suggestions` - Search suggestions
- `GET /api/lancedb-search/analytics` - Search analytics

## Desktop App Search Features

### Research Component
Access search functionality through the "Research" tab in the desktop application.

#### Key Features:
- **Local File Ingestion**: Add local documents to the search index
- **Directory Scanning**: Automatically scan directories for supported files
- **Batch Processing**: Ingest multiple files at once
- **Progress Tracking**: Real-time progress for file ingestion
- **Same Search Capabilities**: All web app search features plus local data

#### Supported File Types:
- Text files: `.txt`, `.md`
- Documents: `.pdf`, `.docx`, `.pptx`, `.xlsx`
- Data files: `.csv`, `.json`

#### Local Ingestion Process:
1. **Select Directory**: Choose a folder to scan for documents
2. **File Selection**: Review and select files to ingest
3. **Batch Processing**: Ingest all selected files automatically
4. **Search Ready**: Immediately search across ingested documents

### Desktop-Specific Features

#### File Management:
- **Directory Browser**: Navigate and select local directories
- **File Preview**: See file details before ingestion
- **Select All/Clear**: Quick selection controls
- **Progress Monitoring**: Real-time ingestion status

#### Tauri Backend Commands:
- `search_documents` - Perform LanceDB search
- `ingest_document` - Add local files to search index
- `get_search_suggestions` - Get search suggestions

## LanceDB Integration

### Search Architecture
- **Vector Embeddings**: OpenAI text-embedding-3-small for semantic search
- **Hybrid Ranking**: Combines vector similarity and keyword relevance
- **User Isolation**: All searches are scoped to individual users
- **Real-time Indexing**: New documents are immediately searchable

### Search Types Explained

#### Hybrid Search
- **How it works**: Combines vector similarity scores with keyword matching
- **Best for**: General purpose searching across diverse content
- **Scoring**: Weighted combination of semantic and keyword relevance

#### Semantic Search
- **How it works**: Uses vector embeddings to find conceptually similar content
- **Best for**: Finding related concepts and contextual matches
- **Scoring**: Pure vector similarity (cosine distance)

#### Keyword Search
- **How it works**: Traditional text matching with relevance scoring
- **Best for**: Exact phrase matching and known terms
- **Scoring**: BM25 or similar keyword relevance algorithm

## Usage Examples

### Web App Usage
```javascript
// Example search request
const searchRequest = {
  query: "project requirements",
  user_id: "user-123",
  filters: {
    doc_type: ["document", "meeting"],
    min_score: 0.7
  },
  limit: 10,
  search_type: "hybrid"
};
```

### Desktop App Usage
```rust
// Example Tauri command
let results = invoke("search_documents", {
  query: "API documentation",
  user_id: "desktop-user-123",
  search_type: "hybrid",
  limit: 20
}).await;
```

### Local File Ingestion
```rust
// Example file ingestion
let success = invoke("ingest_document", {
  file_path: "/path/to/document.pdf",
  content: "Document content...",
  user_id: "desktop-user-123",
  title: "Project Requirements",
  doc_type: "pdf"
}).await;
```

## Performance Tips

### Optimal Search Queries
- Use specific, descriptive phrases for better semantic matching
- Combine keywords for hybrid search effectiveness
- Leverage filters to narrow down large result sets

### File Ingestion Best Practices
- Organize documents in logical directory structures
- Use descriptive file names for better search results
- Process documents in batches for efficiency
- Monitor ingestion progress for large collections

### Search Performance
- Results are typically returned in < 500ms
- Vector search scales well to thousands of documents
- Hybrid search provides best balance of speed and accuracy

## Troubleshooting

### Common Issues

#### No Search Results
- Verify backend services are running
- Check that documents have been properly ingested
- Ensure user_id is correctly specified

#### Slow Search Performance
- Reduce the limit parameter for faster results
- Use more specific search queries
- Check backend resource usage

#### File Ingestion Failures
- Verify file permissions and accessibility
- Check supported file formats
- Monitor ingestion progress for errors

#### Desktop App Connection Issues
- Ensure Python backend is running on port 8083
- Verify Tauri backend commands are properly registered
- Check desktop app logs for connection errors

### Debugging Steps

1. **Check Backend Health**:
   ```bash
   curl http://localhost:8083/healthz
   ```

2. **Test Search API**:
   ```bash
   curl -X POST http://localhost:8083/api/lancedb-search/health
   ```

3. **Verify File Access** (Desktop):
   - Check file permissions
   - Verify directory access
   - Monitor ingestion logs

## Advanced Configuration

### Search Parameters

#### Relevance Threshold
- Default: 0.5 (50%)
- Adjust based on result quality needs
- Higher values return fewer but more relevant results

#### Result Limits
- Web app default: 20 results
- Desktop app default: 20 results
- Adjust based on performance requirements

#### Search Type Selection
- **Hybrid**: Best for general use
- **Semantic**: Best for conceptual searches
- **Keyword**: Best for exact matches

### Customization Options

#### Filter Presets
Create custom filter combinations for common search scenarios:
- "Recent Documents" - Last 30 days, high relevance
- "Meeting Notes" - Meeting type, any date
- "Technical Docs" - Document type, specific tags

#### Search Analytics
Monitor search usage patterns:
- Popular search terms
- Document type distribution
- Search performance metrics

## Integration with Other Features

### Workflow Automation
Search results can be integrated into automated workflows:
- Trigger actions based on search results
- Automate document categorization
- Generate reports from search analytics

### Third-Party Services
Search integrates with existing services:
- Notion documents
- Google Drive files
- Dropbox content
- Local file systems

## Security Considerations

### Data Privacy
- All searches are user-scoped
- Document content is processed locally when possible
- Vector embeddings preserve semantic meaning without exposing raw content

### Access Control
- User authentication required for all searches
- Document-level access controls
- Audit logging for search activities

## Support and Resources

### Getting Help
- Check application logs for detailed error information
- Review backend service status
- Contact support for persistent issues

### Additional Resources
- LanceDB documentation
- OpenAI embeddings guide
- Tauri desktop app development
- Next.js web app development

## Version History

### v1.0.0 (Current)
- Initial search UI implementation
- Hybrid search with LanceDB
- Web and desktop app support
- Local file ingestion for desktop
- Real-time search suggestions
- Advanced filtering capabilities