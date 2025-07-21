import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from ingestion_pipeline.hybrid_search_service import hybrid_search_documents, UnifiedSearchResultItem

@pytest.fixture
def mock_lancedb_search_service():
    with patch('ingestion_pipeline.hybrid_search_service.lancedb_search_service', new_callable=AsyncMock) as mock_service:
        mock_service.search_lancedb_all.return_value = [
            {
                "id": "doc1",
                "user_id": "test_user",
                "title": "Test Document 1",
                "snippet": "This is a test snippet.",
                "original_url_or_link": "http://example.com/doc1",
                "document_doc_type": "pdf",
                "created_at": "2023-01-01T00:00:00Z",
                "last_modified_at": "2023-01-01T00:00:00Z",
                "ingested_at": "2023-01-02T00:00:00Z",
                "vector_score": 0.9
            }
        ]
        yield mock_service

@pytest.fixture
def mock_note_utils():
    with patch('ingestion_pipeline.hybrid_search_service.get_text_embedding_openai', new_callable=MagicMock) as mock_embedding:
        mock_embedding.return_value = {"status": "success", "data": [0.1, 0.2, 0.3]}
        yield mock_embedding

@pytest.fixture
def mock_lancedb_handler():
    with patch('ingestion_pipeline.hybrid_search_service.lancedb_handler', new_callable=AsyncMock) as mock_handler:
        mock_handler.get_lancedb_connection.return_value = AsyncMock()
        yield mock_handler


@pytest.mark.asyncio
async def test_hybrid_search_documents_happy_path(mock_lancedb_search_service, mock_note_utils, mock_lancedb_handler):
    # Arrange
    user_id = "test_user"
    query_text = "test query"

    mock_lancedb_search_service.search_lancedb_all.return_value = [
        {
            "id": "doc1",
            "user_id": user_id,
            "title": "Test Document 1",
            "snippet": "This is a test snippet.",
            "original_url_or_link": "http://example.com/doc1",
            "document_doc_type": "pdf",
            "created_at": "2023-01-01T00:00:00Z",
            "last_modified_at": "2023-01-01T00:00:00Z",
            "ingested_at": "2023-01-02T00:00:00Z",
            "vector_score": 0.9
        }
    ]

    # Act
    results = await hybrid_search_documents(user_id=user_id, query_text=query_text)

    # Assert
    assert len(results) == 1
    result = results[0]
    assert isinstance(result, UnifiedSearchResultItem)
    assert result.doc_id == "doc1"
    assert result.title == "Test Document 1"
    assert result.match_type == "semantic"
    mock_lancedb_search_service.search_lancedb_all.assert_called_once()
    mock_note_utils.assert_called_once_with(text_to_embed=query_text, openai_api_key_param=None)
