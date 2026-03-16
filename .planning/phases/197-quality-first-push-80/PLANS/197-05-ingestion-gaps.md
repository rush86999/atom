# Auto Document Ingestion - Coverage Gaps Analysis

**Baseline Coverage:** 29% (331/468 lines missing)
**Target Coverage:** 60% (280/468 lines need coverage)
**Current:** 30 tests passing

## Missing Coverage by Priority

### HIGH PRIORITY (Core Ingestion Flow)

1. **DocumentParser._get_docling_processor()** [Lines 95-101]
   - Lazy loading initialization
   - Docling availability check
   - **Impact:** Core parsing logic

2. **DocumentParser.parse_document() - Docling path** [Lines 113-126]
   - Docling document processing
   - Export format handling
   - Error fallback
   - **Impact:** Primary parsing for PDF/DOCX/Excel

3. **CSV formula extraction** [Lines 163-178]
   - Formula extractor integration
   - Temp file handling
   - **Impact:** Business logic capture

4. **Excel formula extraction** [Lines 256-271]
   - Formula extraction from spreadsheets
   - Temp file cleanup
   - **Impact:** Business logic capture

### MEDIUM PRIORITY (File Processing)

5. **CSV parsing with formula extraction** [Lines 191-193]
   - CSV parsing edge cases
   - **Impact:** Data file support

6. **PDF parsing** [Lines 202-221]
   - PyPDF2 and pypdf fallback
   - Page limiting
   - **Impact:** PDF document support

7. **DOCX parsing** [Lines 228-247]
   - Paragraph extraction
   - Table extraction
   - **Impact:** Word document support

8. **Excel parsing** [Lines 278-302]
   - Multi-sheet handling
   - openpyxl fallback
   - **Impact:** Spreadsheet support

### HIGH PRIORITY (Service Integration)

9. **AutoDocumentIngestionService.__init__()** [Lines 320-339]
   - LanceDB handler initialization
   - Secrets redactor initialization
   - **Impact:** Service setup

10. **get_settings()** [Lines 343-348]
    - Settings creation
    - **Impact:** Configuration

11. **update_settings()** [Lines 362-380]
    - Settings mutation
    - **Impact:** Configuration updates

### CRITICAL PRIORITY (Main Sync Flow)

12. **sync_integration()** [Lines 393-536] - 144 lines!
    - File listing
    - File filtering (type, size, modification)
    - Document parsing
    - Secrets redaction
    - LanceDB ingestion
    - Agent triggering
    - Error handling
    - **Impact:** PRIMARY INGESTION FUNCTION

13. **_list_files()** [Lines 544-561]
    - Integration routing
    - **Impact:** File discovery

14. **_download_file()** [Lines 569-584]
    - Download routing
    - **Impact:** Content retrieval

### MEDIUM PRIORITY (Integration Adapters)

15. **Google Drive adapter** [Lines 589-657]
    - _list_google_drive_files()
    - _download_google_drive_file()
    - Export format handling
    - **Impact:** Google Drive integration

16. **Dropbox adapter** [Lines 661-747]
    - _list_dropbox_files()
    - _download_dropbox_file()
    - Temporary link handling
    - **Impact:** Dropbox integration

17. **OneDrive/Notion stubs** [Lines 751-765]
    - Placeholder implementations
    - **Impact:** Future integrations

### LOW PRIORITY (Query Operations)

18. **get_ingested_documents()** [Lines 773-780]
    - Filtering by integration/type
    - **Impact:** Query operations

19. **remove_integration_documents()** [Lines 790-804]
    - Document cleanup
    - LanceDB deletion
    - **Impact:** Data management

20. **get_all_settings()** [Lines 813]
    - Settings export
    - **Impact:** Configuration readout

21. **Global service singleton** [Lines 835-837]
    - Service instantiation
    - **Impact:** Service lifecycle

## Test Strategy for 60% Coverage

### Phase 1: Document Processing (Target: 40%)
- Test Docling integration path
- Test PDF parsing with mocked PyPDF2
- Test DOCX parsing with mocked python-docx
- Test Excel parsing with mocked pandas/openpyxl
- Test CSV formula extraction

### Phase 2: Service Setup (Target: 50%)
- Test AutoDocumentIngestionService initialization
- Test get_settings() and update_settings()
- Test settings persistence

### Phase 3: Sync Flow (Target: 60%)
- Test sync_integration() with mocked integrations
- Test file filtering logic (type, size, modification)
- Test document parsing and ingestion
- Test secrets redaction
- Test error handling
- Test agent triggering

### Phase 4: Integration Adapters (Optional - would push to 70%+)
- Test Google Drive adapter with mocked httpx
- Test Dropbox adapter with mocked httpx
- Test _list_files() routing
- Test _download_file() routing

## Testing Challenges

1. **External Dependencies:** Docling, PyPDF2, python-docx, pandas, openpyxl - need mocking
2. **HTTP Clients:** httpx for Google Drive/Dropbox - need mocking
3. **Database:** LanceDB handler - need mocking or in-memory test
4. **Secrets Redaction:** Optional dependency - need conditional testing
5. **Agent Triggering:** Atom meta agent - need mocking

## Recommended Test Structure

```
tests/unit/test_auto_document_ingestion.py
├── TestDocumentParser (existing)
│   ├── test_docling_integration (NEW)
│   ├── test_pdf_parsing_with_pypdf2 (NEW)
│   ├── test_docx_parsing_with_docx (NEW)
│   ├── test_excel_parsing_with_pandas (NEW)
│   └── test_csv_formula_extraction (NEW)
├── TestAutoDocumentIngestionService (NEW)
│   ├── test_service_initialization (NEW)
│   ├── test_get_settings (NEW)
│   ├── test_update_settings (NEW)
│   ├── test_sync_integration_flow (NEW)
│   ├── test_file_filtering (NEW)
│   ├── test_document_ingestion (NEW)
│   ├── test_secrets_redaction (NEW)
│   └── test_agent_triggering (NEW)
└── TestIntegrationAdapters (NEW)
    ├── test_list_google_drive_files (NEW)
    ├── test_download_google_drive_file (NEW)
    ├── test_list_dropbox_files (NEW)
    └── test_download_dropbox_file (NEW)
```

## Coverage Calculation

- **Current:** 137/468 lines = 29%
- **Needed for 60%:** 280/468 lines = 60%
- **Gap:** 143 lines need coverage

**Estimated Tests Required:**
- 5 tests for DocumentParser enhancements → ~40 lines
- 8 tests for Service setup → ~30 lines
- 10 tests for Sync flow → ~80 lines
- **Total:** ~23 new tests to reach 60%
