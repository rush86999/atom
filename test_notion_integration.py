#!/usr/bin/env python3
"""
Test Notion integration with the token
"""

import os
import requests
import json

def test_notion_integration():
    # Get the Notion token from environment
    notion_token = os.getenv('NOTION_TOKEN')
    
    if not notion_token:
        return {'success': False, 'error': 'NOTION_TOKEN not found in environment'}
    
    print(f"🔑 Testing Notion with token: {notion_token[:20]}...")
    
    # Test API call
    headers = {
        'Authorization': f'Bearer {notion_token}',
        'Content-Type': 'application/json',
        'Notion-Version': '2022-06-28'
    }
    
    try:
        # Test search functionality
        search_url = 'https://api.notion.com/v1/search'
        search_data = {
            'query': '',
            'filter': {
                'property': 'object',
                'value': 'page'
            }
        }
        
        response = requests.post(search_url, headers=headers, json=search_data, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            pages = data.get('results', [])
            
            return {
                'success': True,
                'service': 'notion',
                'api_connected': True,
                'real_data': True,
                'pages_found': len(pages),
                'sample_pages': [
                    {
                        'id': page.get('id'),
                        'title': page.get('properties', {}).get('title', [{}])[0].get('title', 'No title') if page.get('properties', {}).get('title') else 'No title',
                        'created_time': page.get('created_time'),
                        'last_edited_time': page.get('last_edited_time'),
                        'url': page.get('url'),
                        'real_integration': True
                    } for page in pages[:5]
                ],
                'message': f'Notion integration successful! Found {len(pages)} pages',
                'token_status': 'valid'
            }
        else:
            return {
                'success': False,
                'error': f'API request failed',
                'status_code': response.status_code,
                'response': response.text,
                'token_status': 'invalid_or_expired'
            }
            
    except Exception as e:
        return {
            'success': False,
            'error': f'Notion API connection error: {str(e)}',
            'token_status': 'connection_error'
        }

if __name__ == "__main__":
    result = test_notion_integration()
    print(json.dumps(result, indent=2))