# Mock WordPress service for development
# This provides mock implementations for WordPress XML-RPC functionality

import os
import logging
from typing import Optional, Dict, Any
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

class MockClient:
    """Mock WordPress XML-RPC Client for development"""

    def __init__(self, url: str, username: str, password: str):
        self.url = url
        self.username = username
        self.password = password
        self.posts = self._create_mock_posts()

    def _create_mock_posts(self) -> Dict[str, Dict]:
        """Create mock WordPress posts for development"""
        return {
            "1": {
                "id": "1",
                "title": "Welcome to WordPress",
                "content": "This is your first post. Edit or delete it, then start writing!",
                "status": "publish",
                "date": "2024-01-15T10:00:00",
                "modified": "2024-01-15T10:00:00",
                "author": "admin"
            },
            "2": {
                "id": "2",
                "title": "Sample Post",
                "content": "This is a sample post with some content for testing purposes.",
                "status": "publish",
                "date": "2024-01-16T14:30:00",
                "modified": "2024-01-16T14:30:00",
                "author": "admin"
            },
            "3": {
                "id": "3",
                "title": "Draft Article",
                "content": "This is a draft article that hasn't been published yet.",
                "status": "draft",
                "date": "2024-01-17T09:15:00",
                "modified": "2024-01-17T09:15:00",
                "author": "editor"
            }
        }

    def call(self, method, *args):
        """Mock call method for XML-RPC operations"""
        method_name = str(method).split('.')[-1] if hasattr(method, '__name__') else str(method)

        if method_name == "NewPost":
            # Create new post
            post = args[0]
            new_id = str(len(self.posts) + 1)
            self.posts[new_id] = {
                "id": new_id,
                "title": getattr(post, 'title', 'Untitled'),
                "content": getattr(post, 'content', ''),
                "status": getattr(post, 'post_status', 'draft'),
                "date": datetime.now().isoformat(),
                "modified": datetime.now().isoformat(),
                "author": self.username
            }
            return new_id

        elif method_name == "GetPost":
            # Get existing post
            post_id = str(args[0])
            if post_id in self.posts:
                return self.posts[post_id]
            raise Exception(f"Post {post_id} not found")

        # Default return for unknown methods
        return None

class MockWordPressPost:
    """Mock WordPressPost object"""

    def __init__(self):
        self.id = None
        self.title = None
        self.content = None
        self.post_status = None
        self.date = None
        self.modified = None

# Mock classes for compatibility
Client = MockClient
WordPressPost = MockWordPressPost

# Mock methods for compatibility
class NewPost:
    """Mock NewPost method"""
    pass

class GetPost:
    """Mock GetPost method"""
    pass

async def get_wordpress_client(user_id: str, db_conn_pool) -> Optional[MockClient]:
    """Mock function to get WordPress client"""
    # In development mode, use mock credentials
    url = os.environ.get("WORDPRESS_URL", "https://example.com/xmlrpc.php")
    username = os.environ.get("WORDPRESS_USERNAME", "admin")
    password = os.environ.get("WORDPRESS_PASSWORD", "password")

    logger.info(f"Creating mock WordPress client for {url} with user {username}")

    try:
        client = MockClient(url, username, password)
        return client
    except Exception as e:
        logger.error(f"Failed to create WordPress client: {e}")
        return None

async def create_post(client: MockClient, post_data: Dict[str, Any]) -> MockWordPressPost:
    """Mock function to create post"""
    try:
        post = MockWordPressPost()
        post.title = post_data.get('title', 'Untitled Post')
        post.content = post_data.get('content', '')
        post.post_status = post_data.get('status', 'draft')

        # Use mock call to create post
        post_id = client.call(NewPost(), post)
        post.id = post_id

        logger.info(f"Created mock WordPress post with ID: {post_id}")
        return post

    except Exception as e:
        logger.error(f"Error creating WordPress post: {e}")
        raise

async def get_post(client: MockClient, post_id: str) -> MockWordPressPost:
    """Mock function to get post"""
    try:
        post_data = client.call(GetPost(), post_id)

        post = MockWordPressPost()
        post.id = post_data['id']
        post.title = post_data['title']
        post.content = post_data['content']
        post.post_status = post_data['status']
        post.date = post_data['date']
        post.modified = post_data['modified']

        return post

    except Exception as e:
        logger.error(f"Error getting WordPress post {post_id}: {e}")
        raise

# Additional mock functions for development
async def list_posts(client: MockClient, status: str = None) -> list:
    """Mock function to list posts"""
    posts = []
    for post_id, post_data in client.posts.items():
        if status is None or post_data['status'] == status:
            posts.append(post_data)
    return posts

async def update_post(client: MockClient, post_id: str, post_data: Dict[str, Any]) -> bool:
    """Mock function to update post"""
    if post_id in client.posts:
        client.posts[post_id].update({
            'title': post_data.get('title', client.posts[post_id]['title']),
            'content': post_data.get('content', client.posts[post_id]['content']),
            'status': post_data.get('status', client.posts[post_id]['status']),
            'modified': datetime.now().isoformat()
        })
        return True
    return False

async def delete_post(client: MockClient, post_id: str) -> bool:
    """Mock function to delete post"""
    if post_id in client.posts:
        del client.posts[post_id]
        return True
    return False
