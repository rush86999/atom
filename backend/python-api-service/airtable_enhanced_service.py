"""
Airtable Enhanced Service Implementation
Complete Airtable data management with API integration
"""

import os
import logging
import json
import asyncio
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, asdict
import httpx

# Configure logging
logger = logging.getLogger(__name__)

# Airtable API configuration
AIRTABLE_API_BASE_URL = "https://api.airtable.com/v0"

@dataclass
class AirtableBase:
    """Airtable base representation"""
    id: str
    name: str
    permission_level: str
    sharing: str
    created_time: str
    last_modified_time: str
    base_icon_url: str
    base_color_theme: str
    workspace_id: str
    workspace_name: str
    collaboration: Dict[str, Any]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

@dataclass
class AirtableTable:
    """Airtable table representation"""
    id: str
    name: str
    primary_field_id: str
    primary_field_name: str
    description: str
    records_count: int
    views_count: int
    fields: List[Dict[str, Any]]
    views: List[Dict[str, Any]]
    created_time: str
    last_modified_time: str
    base_id: str
    base_name: str
    icon_emoji: str
    icon_url: str
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

@dataclass
class AirtableField:
    """Airtable field representation"""
    id: str
    name: str
    type: str
    description: str
    options: Dict[str, Any]
    required: bool
    unique: bool
    hidden: bool
    formula: str
    validation: Dict[str, Any]
    lookup: Dict[str, Any]
    rollup: Dict[str, Any]
    multiple_record_links: Dict[str, Any]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

@dataclass
class AirtableView:
    """Airtable view representation"""
    id: str
    name: str
    type: str
    personal: bool
    description: str
    filters: List[Dict[str, Any]]
    sorts: List[Dict[str, Any]]
    field_options: Dict[str, Any]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

@dataclass
class AirtableRecord:
    """Airtable record representation"""
    id: str
    created_time: str
    fields: Dict[str, Any]
    field_values: Dict[str, Any]
    table_id: str
    table_name: str
    base_id: str
    base_name: str
    attachments: List[Dict[str, Any]]
    linked_records: List[Dict[str, Any]]
    comments_count: int
    last_modified_time: str
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

@dataclass
class AirtableUser:
    """Airtable user representation"""
    id: str
    email: str
    name: str
    state: str
    invites: List[Dict[str, Any]]
    enterprise_info: Dict[str, Any]
    group_info: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

@dataclass
class AirtableWebhook:
    """Airtable webhook representation"""
    id: str
    is_hook_enabled: bool
    cursor: int
    last_hook_time: str
    base_notification_url: str
    spec: Dict[str, Any]
    expiration_time: str
    created_time: str
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

class AirtableEnhancedService:
    """Enhanced Airtable service with complete data management automation"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('AIRTABLE_API_KEY')
        self.api_base_url = AIRTABLE_API_BASE_URL
        
        # Cache for storing data
        self.bases_cache = {}
        self.tables_cache = {}
        self.records_cache = {}
        self.fields_cache = {}
        self.views_cache = {}
        self.users_cache = {}
        
        # Common Airtable field types
        self.field_types = {
            'single_line_text': 'Single line text',
            'long_text': 'Long text',
            'attachment': 'Attachment',
            'checkbox': 'Checkbox',
            'date': 'Date',
            'datetime': 'Date and time',
            'email': 'Email',
            'url': 'URL',
            'number': 'Number',
            'percent': 'Percent',
            'currency': 'Currency',
            'single_select': 'Single select',
            'multiple_selects': 'Multiple select',
            'multiple_record_links': 'Linked record',
            'lookup': 'Lookup',
            'rollup': 'Rollup',
            'formula': 'Formula',
            'created_time': 'Created time',
            'modified_time': 'Last modified time',
            'created_by': 'Created by',
            'modified_by': 'Last modified by',
            'barcode': 'Barcode',
            'rating': 'Rating',
            'duration': 'Duration',
            'rich_text': 'Rich text'
        }
        
        # Common view types
        self.view_types = {
            'grid': 'Grid',
            'form': 'Form',
            'kanban': 'Kanban',
            'gallery': 'Gallery',
            'calendar': 'Calendar',
            'gantt': 'Gantt',
            'timeline': 'Timeline'
        }
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers"""
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
    
    def _build_url(self, endpoint: str) -> str:
        """Build complete API URL"""
        return f"{self.api_base_url}/{endpoint}"
    
    async def _make_request(self, method: str, endpoint: str, 
                          params: Dict[str, Any] = None,
                          data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make HTTP request to Airtable API"""
        try:
            # Build URL
            url = self._build_url(endpoint)
            
            # Get auth headers
            headers = self._get_auth_headers()
            
            # Make request
            async with httpx.AsyncClient(timeout=30) as client:
                if method.upper() == 'GET':
                    response = await client.get(url, params=params, headers=headers)
                elif method.upper() == 'POST':
                    response = await client.post(url, params=params, json=data, headers=headers)
                elif method.upper() == 'PUT':
                    response = await client.put(url, params=params, json=data, headers=headers)
                elif method.upper() == 'PATCH':
                    response = await client.patch(url, params=params, json=data, headers=headers)
                elif method.upper() == 'DELETE':
                    response = await client.delete(url, params=params, headers=headers)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                # Handle response
                if response.status_code == 422:
                    try:
                        error_data = response.json()
                        return {
                            'error': 'Validation error',
                            'details': error_data,
                            'type': 'validation_error'
                        }
                    except:
                        pass
                
                response.raise_for_status()
                
                return response.json()
                
        except httpx.HTTPStatusError as e:
            logger.error(f"Airtable API HTTP error: {e.response.status_code} - {e.response.text}")
            return {
                'error': f'HTTP {e.response.status_code}',
                'message': e.response.text,
                'type': 'http_error'
            }
        except Exception as e:
            logger.error(f"Airtable API request error: {e}")
            return {
                'error': str(e),
                'type': 'request_error'
            }
    
    def _generate_cache_key(self, user_id: str, entity_id: str) -> str:
        """Generate cache key"""
        return f"{user_id}:{entity_id}"
    
    async def get_bases(self, user_id: str = None) -> List[AirtableBase]:
        """Get Airtable bases"""
        try:
            # Check cache first
            cache_key = self._generate_cache_key(user_id or 'all', 'bases')
            if cache_key in self.bases_cache:
                return self.bases_cache[cache_key]
            
            # Make request
            result = await self._make_request('GET', 'meta/bases')
            
            if result.get('error'):
                return []
            
            # Create base objects
            bases = []
            for base_data in result.get('bases', []):
                base = AirtableBase(
                    id=base_data.get('id', ''),
                    name=base_data.get('name', ''),
                    permission_level=base_data.get('permissionLevel', ''),
                    sharing=base_data.get('sharing', ''),
                    created_time=base_data.get('createdTime', ''),
                    last_modified_time=base_data.get('lastModifiedTime', ''),
                    base_icon_url=base_data.get('baseIconUrl', ''),
                    base_color_theme=base_data.get('baseColorTheme', ''),
                    workspace_id=base_data.get('workspaceId', ''),
                    workspace_name=base_data.get('workspaceName', ''),
                    collaboration=base_data.get('collaboration', {}),
                    metadata={
                        'accessed_at': datetime.utcnow().isoformat(),
                        'source': 'airtable_api'
                    }
                )
                bases.append(base)
            
            # Cache bases
            self.bases_cache[cache_key] = bases
            
            logger.info(f"Airtable bases retrieved: {len(bases)}")
            return bases
            
        except Exception as e:
            logger.error(f"Error getting Airtable bases: {e}")
            return []
    
    async def get_base(self, base_id: str, user_id: str = None) -> Optional[AirtableBase]:
        """Get Airtable base by ID"""
        try:
            # Check cache first
            cache_key = self._generate_cache_key(user_id or 'all', f'base_{base_id}')
            if cache_key in self.bases_cache:
                return self.bases_cache[cache_key]
            
            # Make request
            result = await self._make_request('GET', f'meta/bases/{base_id}')
            
            if result.get('error'):
                return None
            
            # Create base object
            base = AirtableBase(
                id=result.get('id', ''),
                name=result.get('name', ''),
                permission_level=result.get('permissionLevel', ''),
                sharing=result.get('sharing', ''),
                created_time=result.get('createdTime', ''),
                last_modified_time=result.get('lastModifiedTime', ''),
                base_icon_url=result.get('baseIconUrl', ''),
                base_color_theme=result.get('baseColorTheme', ''),
                workspace_id=result.get('workspaceId', ''),
                workspace_name=result.get('workspaceName', ''),
                collaboration=result.get('collaboration', {}),
                metadata={
                    'accessed_at': datetime.utcnow().isoformat(),
                    'source': 'airtable_api'
                }
            )
            
            # Cache base
            self.bases_cache[cache_key] = base
            
            logger.info(f"Airtable base retrieved: {base_id}")
            return base
            
        except Exception as e:
            logger.error(f"Error getting Airtable base: {e}")
            return None
    
    async def get_tables(self, base_id: str, user_id: str = None) -> List[AirtableTable]:
        """Get Airtable tables from base"""
        try:
            # Check cache first
            cache_key = self._generate_cache_key(user_id or 'all', f'tables_{base_id}')
            if cache_key in self.tables_cache:
                return self.tables_cache[cache_key]
            
            # Get base info first
            base = await self.get_base(base_id, user_id)
            if not base:
                return []
            
            # Make request for base schema
            result = await self._make_request('GET', f'meta/bases/{base_id}/tables')
            
            if result.get('error'):
                return []
            
            # Create table objects
            tables = []
            for table_data in result.get('tables', []):
                # Count records
                records_count = 0
                try:
                    records_result = await self.get_records(base_id, table_data.get('id', ''), limit=1)
                    if records_result.get('records'):
                        # Get total count
                        count_result = await self._make_request('GET', f'{base_id}/{table_data.get("id")}', {'pageSize': 1})
                        records_count = count_result.get('records', [])
                        # Airtable doesn't provide total count directly, so we'll estimate
                        records_count = 0  # Will be updated when records are actually fetched
                except:
                    pass
                
                table = AirtableTable(
                    id=table_data.get('id', ''),
                    name=table_data.get('name', ''),
                    primary_field_id=table_data.get('primaryFieldId', ''),
                    primary_field_name=table_data.get('primaryFieldName', ''),
                    description=table_data.get('description', ''),
                    records_count=records_count,
                    views_count=len(table_data.get('views', [])),
                    fields=table_data.get('fields', []),
                    views=table_data.get('views', []),
                    created_time=table_data.get('createdTime', ''),
                    last_modified_time=table_data.get('lastModifiedTime', ''),
                    base_id=base_id,
                    base_name=base.name,
                    icon_emoji=table_data.get('iconEmoji', ''),
                    icon_url=table_data.get('iconUrl', ''),
                    metadata={
                        'accessed_at': datetime.utcnow().isoformat(),
                        'source': 'airtable_api'
                    }
                )
                tables.append(table)
            
            # Cache tables
            self.tables_cache[cache_key] = tables
            
            logger.info(f"Airtable tables retrieved: {len(tables)}")
            return tables
            
        except Exception as e:
            logger.error(f"Error getting Airtable tables: {e}")
            return []
    
    async def get_table(self, base_id: str, table_id: str, user_id: str = None) -> Optional[AirtableTable]:
        """Get Airtable table by ID"""
        try:
            # Check cache first
            cache_key = self._generate_cache_key(user_id or 'all', f'table_{base_id}_{table_id}')
            if cache_key in self.tables_cache:
                return self.tables_cache[cache_key]
            
            # Get all tables and find the one we want
            tables = await self.get_tables(base_id, user_id)
            
            for table in tables:
                if table.id == table_id:
                    # Cache table
                    self.tables_cache[cache_key] = table
                    logger.info(f"Airtable table retrieved: {table_id}")
                    return table
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting Airtable table: {e}")
            return None
    
    async def get_records(self, base_id: str, table_id: str, 
                        view_id: str = None, filter_by_formula: str = None,
                        sort: List[Dict[str, str]] = None, fields: List[str] = None,
                        max_records: int = 100, page_size: int = 100,
                        offset: str = None, user_id: str = None) -> Dict[str, Any]:
        """Get Airtable records from table"""
        try:
            # Build parameters
            params = {}
            
            if view_id:
                params['view'] = view_id
            
            if filter_by_formula:
                params['filterByFormula'] = filter_by_formula
            
            if sort:
                params['sort'] = json.dumps(sort)
            
            if fields:
                params['fields'] = fields
            
            if max_records:
                params['maxRecords'] = max_records
            
            if page_size:
                params['pageSize'] = page_size
            
            if offset:
                params['offset'] = offset
            
            # Make request
            result = await self._make_request('GET', f'{base_id}/{table_id}', params)
            
            if result.get('error'):
                return {
                    'records': [],
                    'offset': None,
                    'error': result.get('error')
                }
            
            # Get table info for metadata
            table = await self.get_table(base_id, table_id, user_id)
            
            # Create record objects
            records = []
            for record_data in result.get('records', []):
                # Count attachments
                attachments = []
                for field_name, field_value in record_data.get('fields', {}).items():
                    if isinstance(field_value, list) and field_value and isinstance(field_value[0], dict):
                        if field_value[0].get('type') == 'attachment':
                            attachments = field_value
                            break
                
                # Count linked records
                linked_records = []
                for field_name, field_value in record_data.get('fields', {}).items():
                    if isinstance(field_value, list) and field_value and isinstance(field_value[0], str):
                        linked_records.append({
                            'field': field_name,
                            'record_ids': field_value
                        })
                
                record = AirtableRecord(
                    id=record_data.get('id', ''),
                    created_time=record_data.get('createdTime', ''),
                    fields=record_data.get('fields', {}),
                    field_values=record_data.get('fields', {}),
                    table_id=table_id,
                    table_name=table.name if table else '',
                    base_id=base_id,
                    base_name=table.base_name if table else '',
                    attachments=attachments,
                    linked_records=linked_records,
                    comments_count=0,  # Would need separate API call
                    last_modified_time=record_data.get('createdTime', ''),
                    metadata={
                        'accessed_at': datetime.utcnow().isoformat(),
                        'source': 'airtable_api'
                    }
                )
                records.append(record)
            
            # Update table records count
            if table:
                table.records_count = len(records)
            
            return {
                'records': records,
                'offset': result.get('offset'),
                'total': len(records)
            }
            
        except Exception as e:
            logger.error(f"Error getting Airtable records: {e}")
            return {
                'records': [],
                'offset': None,
                'error': str(e)
            }
    
    async def get_record(self, base_id: str, table_id: str, 
                        record_id: str, user_id: str = None) -> Optional[AirtableRecord]:
        """Get Airtable record by ID"""
        try:
            # Make request
            result = await self._make_request('GET', f'{base_id}/{table_id}/{record_id}')
            
            if result.get('error'):
                return None
            
            # Get table info for metadata
            table = await self.get_table(base_id, table_id, user_id)
            
            record_data = result
            
            # Count attachments
            attachments = []
            for field_name, field_value in record_data.get('fields', {}).items():
                if isinstance(field_value, list) and field_value and isinstance(field_value[0], dict):
                    if field_value[0].get('type') == 'attachment':
                        attachments = field_value
                        break
            
            # Count linked records
            linked_records = []
            for field_name, field_value in record_data.get('fields', {}).items():
                if isinstance(field_value, list) and field_value and isinstance(field_value[0], str):
                    linked_records.append({
                        'field': field_name,
                        'record_ids': field_value
                    })
            
            record = AirtableRecord(
                id=record_data.get('id', ''),
                created_time=record_data.get('createdTime', ''),
                fields=record_data.get('fields', {}),
                field_values=record_data.get('fields', {}),
                table_id=table_id,
                table_name=table.name if table else '',
                base_id=base_id,
                base_name=table.base_name if table else '',
                attachments=attachments,
                linked_records=linked_records,
                comments_count=0,
                last_modified_time=record_data.get('createdTime', ''),
                metadata={
                    'accessed_at': datetime.utcnow().isoformat(),
                    'source': 'airtable_api'
                }
            )
            
            logger.info(f"Airtable record retrieved: {record_id}")
            return record
            
        except Exception as e:
            logger.error(f"Error getting Airtable record: {e}")
            return None
    
    async def create_record(self, base_id: str, table_id: str, 
                          fields: Dict[str, Any], user_id: str = None) -> Optional[AirtableRecord]:
        """Create Airtable record"""
        try:
            # Make request
            result = await self._make_request('POST', f'{base_id}/{table_id}', 
                                           data={'fields': fields})
            
            if result.get('error'):
                return None
            
            # Get table info for metadata
            table = await self.get_table(base_id, table_id, user_id)
            
            record_data = result
            
            # Count attachments
            attachments = []
            for field_name, field_value in record_data.get('fields', {}).items():
                if isinstance(field_value, list) and field_value and isinstance(field_value[0], dict):
                    if field_value[0].get('type') == 'attachment':
                        attachments = field_value
                        break
            
            # Count linked records
            linked_records = []
            for field_name, field_value in record_data.get('fields', {}).items():
                if isinstance(field_value, list) and field_value and isinstance(field_value[0], str):
                    linked_records.append({
                        'field': field_name,
                        'record_ids': field_value
                    })
            
            record = AirtableRecord(
                id=record_data.get('id', ''),
                created_time=record_data.get('createdTime', ''),
                fields=record_data.get('fields', {}),
                field_values=record_data.get('fields', {}),
                table_id=table_id,
                table_name=table.name if table else '',
                base_id=base_id,
                base_name=table.base_name if table else '',
                attachments=attachments,
                linked_records=linked_records,
                comments_count=0,
                last_modified_time=record_data.get('createdTime', ''),
                metadata={
                    'created_at': datetime.utcnow().isoformat(),
                    'source': 'airtable_api'
                }
            )
            
            # Clear cache
            self._clear_record_cache()
            
            logger.info(f"Airtable record created: {record.id}")
            return record
            
        except Exception as e:
            logger.error(f"Error creating Airtable record: {e}")
            return None
    
    async def update_record(self, base_id: str, table_id: str, 
                          record_id: str, fields: Dict[str, Any], 
                          user_id: str = None) -> Optional[AirtableRecord]:
        """Update Airtable record"""
        try:
            # Make request
            result = await self._make_request('PATCH', f'{base_id}/{table_id}/{record_id}', 
                                           data={'fields': fields})
            
            if result.get('error'):
                return None
            
            # Get table info for metadata
            table = await self.get_table(base_id, table_id, user_id)
            
            record_data = result
            
            # Count attachments
            attachments = []
            for field_name, field_value in record_data.get('fields', {}).items():
                if isinstance(field_value, list) and field_value and isinstance(field_value[0], dict):
                    if field_value[0].get('type') == 'attachment':
                        attachments = field_value
                        break
            
            # Count linked records
            linked_records = []
            for field_name, field_value in record_data.get('fields', {}).items():
                if isinstance(field_value, list) and field_value and isinstance(field_value[0], str):
                    linked_records.append({
                        'field': field_name,
                        'record_ids': field_value
                    })
            
            record = AirtableRecord(
                id=record_data.get('id', ''),
                created_time=record_data.get('createdTime', ''),
                fields=record_data.get('fields', {}),
                field_values=record_data.get('fields', {}),
                table_id=table_id,
                table_name=table.name if table else '',
                base_id=base_id,
                base_name=table.base_name if table else '',
                attachments=attachments,
                linked_records=linked_records,
                comments_count=0,
                last_modified_time=record_data.get('createdTime', ''),
                metadata={
                    'updated_at': datetime.utcnow().isoformat(),
                    'source': 'airtable_api'
                }
            )
            
            # Clear cache
            self._clear_record_cache()
            
            logger.info(f"Airtable record updated: {record_id}")
            return record
            
        except Exception as e:
            logger.error(f"Error updating Airtable record: {e}")
            return None
    
    async def delete_record(self, base_id: str, table_id: str, record_id: str) -> bool:
        """Delete Airtable record"""
        try:
            # Make request
            result = await self._make_request('DELETE', f'{base_id}/{table_id}/{record_id}')
            
            # Check for error
            if result.get('error'):
                return False
            
            # Clear cache
            self._clear_record_cache()
            
            logger.info(f"Airtable record deleted: {record_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting Airtable record: {e}")
            return False
    
    async def get_fields(self, base_id: str, table_id: str, user_id: str = None) -> List[AirtableField]:
        """Get Airtable fields from table"""
        try:
            # Check cache first
            cache_key = self._generate_cache_key(user_id or 'all', f'fields_{base_id}_{table_id}')
            if cache_key in self.fields_cache:
                return self.fields_cache[cache_key]
            
            # Get table info
            table = await self.get_table(base_id, table_id, user_id)
            if not table:
                return []
            
            # Create field objects
            fields = []
            for field_data in table.fields:
                field = AirtableField(
                    id=field_data.get('id', ''),
                    name=field_data.get('name', ''),
                    type=field_data.get('type', ''),
                    description=field_data.get('description', ''),
                    options=field_data.get('options', {}),
                    required=field_data.get('required', False),
                    unique=field_data.get('unique', False),
                    hidden=field_data.get('hidden', False),
                    formula=field_data.get('formula', ''),
                    validation=field_data.get('validation', {}),
                    lookup=field_data.get('lookup', {}),
                    rollup=field_data.get('rollup', {}),
                    multiple_record_links=field_data.get('multipleRecordLinks', {}),
                    metadata={
                        'accessed_at': datetime.utcnow().isoformat(),
                        'source': 'airtable_api'
                    }
                )
                fields.append(field)
            
            # Cache fields
            self.fields_cache[cache_key] = fields
            
            logger.info(f"Airtable fields retrieved: {len(fields)}")
            return fields
            
        except Exception as e:
            logger.error(f"Error getting Airtable fields: {e}")
            return []
    
    async def get_views(self, base_id: str, table_id: str, user_id: str = None) -> List[AirtableView]:
        """Get Airtable views from table"""
        try:
            # Check cache first
            cache_key = self._generate_cache_key(user_id or 'all', f'views_{base_id}_{table_id}')
            if cache_key in self.views_cache:
                return self.views_cache[cache_key]
            
            # Get table info
            table = await self.get_table(base_id, table_id, user_id)
            if not table:
                return []
            
            # Create view objects
            views = []
            for view_data in table.views:
                view = AirtableView(
                    id=view_data.get('id', ''),
                    name=view_data.get('name', ''),
                    type=view_data.get('type', ''),
                    personal=view_data.get('personal', False),
                    description=view_data.get('description', ''),
                    filters=view_data.get('filters', {}),
                    sorts=view_data.get('sorts', []),
                    field_options=view_data.get('fieldOptions', {}),
                    metadata={
                        'accessed_at': datetime.utcnow().isoformat(),
                        'source': 'airtable_api'
                    }
                )
                views.append(view)
            
            # Cache views
            self.views_cache[cache_key] = views
            
            logger.info(f"Airtable views retrieved: {len(views)}")
            return views
            
        except Exception as e:
            logger.error(f"Error getting Airtable views: {e}")
            return []
    
    async def search_records(self, base_id: str, table_id: str, 
                          search_query: str, view_id: str = None,
                          fields: List[str] = None, max_records: int = 100,
                          user_id: str = None) -> Dict[str, Any]:
        """Search Airtable records"""
        try:
            # Build search formula
            formula = None
            if search_query:
                # Create formula to search in all text fields
                formula = f"SEARCH('{search_query}', {table_id}.{{name}}) != BLANK()"
            
            return await self.get_records(
                base_id=base_id,
                table_id=table_id,
                view_id=view_id,
                filter_by_formula=formula,
                fields=fields,
                max_records=max_records,
                user_id=user_id
            )
            
        except Exception as e:
            logger.error(f"Error searching Airtable records: {e}")
            return {
                'records': [],
                'offset': None,
                'error': str(e)
            }
    
    async def get_webhooks(self, base_id: str, user_id: str = None) -> List[AirtableWebhook]:
        """Get Airtable webhooks from base"""
        try:
            # Check cache first
            cache_key = self._generate_cache_key(user_id or 'all', f'webhooks_{base_id}')
            if cache_key in self.users_cache:  # Using users_cache for webhooks
                return self.users_cache[cache_key]
            
            # Make request
            result = await self._make_request('GET', f'bases/{base_id}/webhooks')
            
            if result.get('error'):
                return []
            
            # Create webhook objects
            webhooks = []
            for webhook_data in result.get('webhooks', []):
                webhook = AirtableWebhook(
                    id=webhook_data.get('id', ''),
                    is_hook_enabled=webhook_data.get('isHookEnabled', False),
                    cursor=webhook_data.get('cursor', 0),
                    last_hook_time=webhook_data.get('lastHookTime', ''),
                    base_notification_url=webhook_data.get('baseNotificationUrl', ''),
                    spec=webhook_data.get('spec', {}),
                    expiration_time=webhook_data.get('expirationTime', ''),
                    created_time=webhook_data.get('createdTime', ''),
                    metadata={
                        'accessed_at': datetime.utcnow().isoformat(),
                        'source': 'airtable_api'
                    }
                )
                webhooks.append(webhook)
            
            # Cache webhooks
            self.users_cache[cache_key] = webhooks
            
            logger.info(f"Airtable webhooks retrieved: {len(webhooks)}")
            return webhooks
            
        except Exception as e:
            logger.error(f"Error getting Airtable webhooks: {e}")
            return []
    
    def _clear_cache(self):
        """Clear all caches"""
        self.bases_cache.clear()
        self.tables_cache.clear()
        self.records_cache.clear()
        self.fields_cache.clear()
        self.views_cache.clear()
        self.users_cache.clear()
    
    def _clear_base_cache(self):
        """Clear base cache"""
        self.bases_cache.clear()
    
    def _clear_table_cache(self):
        """Clear table cache"""
        self.tables_cache.clear()
    
    def _clear_record_cache(self):
        """Clear record cache"""
        self.records_cache.clear()
    
    def _clear_field_cache(self):
        """Clear field cache"""
        self.fields_cache.clear()
    
    def _clear_view_cache(self):
        """Clear view cache"""
        self.views_cache.clear()
    
    def _clear_webhook_cache(self):
        """Clear webhook cache"""
        self.users_cache.clear()
    
    async def get_service_info(self) -> Dict[str, Any]:
        """Get service information"""
        return {
            "name": "Enhanced Airtable Service",
            "version": "1.0.0",
            "description": "Complete Airtable data management automation",
            "capabilities": [
                "base_management",
                "table_operations",
                "record_crud",
                "field_management",
                "view_management",
                "search_and_filtering",
                "webhook_support",
                "data_validation",
                "formula_evaluation",
                "attachment_handling",
                "relationship_mapping",
                "collaboration_tracking"
            ],
            "api_endpoints": [
                "/api/airtable/enhanced/bases/list",
                "/api/airtable/enhanced/bases/get",
                "/api/airtable/enhanced/tables/list",
                "/api/airtable/enhanced/tables/get",
                "/api/airtable/enhanced/records/list",
                "/api/airtable/enhanced/records/get",
                "/api/airtable/enhanced/records/create",
                "/api/airtable/enhanced/records/update",
                "/api/airtable/enhanced/records/delete",
                "/api/airtable/enhanced/fields/list",
                "/api/airtable/enhanced/views/list",
                "/api/airtable/enhanced/search/records",
                "/api/airtable/enhanced/webhooks/list",
                "/api/airtable/enhanced/health"
            ],
            "field_types": self.field_types,
            "view_types": self.view_types,
            "initialized_at": datetime.utcnow().isoformat()
        }

# Create singleton instance
airtable_enhanced_service = AirtableEnhancedService()