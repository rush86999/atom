"""
GitHub OAuth Database Operations
Handles storage and retrieval of GitHub OAuth tokens and user data
"""

import os
import logging
import asyncio
import json
import base64
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List
import asyncpg
import sqlite3
import aiosqlite

# Import encryption utilities
try:
    from atom_encryption import decrypt_data, encrypt_data
    ENCRYPTION_AVAILABLE = True
except ImportError:
    ENCRYPTION_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("atom_encryption not available, tokens will be stored in plaintext")

logger = logging.getLogger(__name__)

# Database configuration
DB_TYPE = os.getenv('ATOM_DB_TYPE', 'sqlite')
POSTGRES_URL = os.getenv('ATOM_POSTGRES_URL')
ATOM_OAUTH_ENCRYPTION_KEY = os.getenv('ATOM_OAUTH_ENCRYPTION_KEY')

# GitHub OAuth configuration
GITHUB_CLIENT_ID = os.getenv('GITHUB_CLIENT_ID', 'mock_github_client_id')
GITHUB_CLIENT_SECRET = os.getenv('GITHUB_CLIENT_SECRET', 'mock_github_client_secret')
GITHUB_REDIRECT_URI = os.getenv('GITHUB_REDIRECT_URI', 'http://localhost:3000/integrations/github/callback')
GITHUB_SCOPE = os.getenv('GITHUB_SCOPE', 'repo user:email read:org')

# Mock database fallback
MOCK_DB = {
    'github_tokens': {},
    'github_users': {},
    'github_repos': {},
    'github_issues': {},
    'github_prs': {}
}

# Initialize SQLite database if needed
def init_sqlite_db():
    """Initialize SQLite database with GitHub tables"""
    try:
        db_path = os.getenv('ATOM_SQLITE_PATH', 'data/atom_development.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # GitHub tokens table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS github_oauth_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                access_token TEXT NOT NULL,
                token_type TEXT DEFAULT 'bearer',
                scope TEXT,
                expires_at TIMESTAMP,
                refresh_token TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # GitHub users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS github_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                github_user_id INTEGER NOT NULL,
                login TEXT NOT NULL,
                name TEXT,
                email TEXT,
                avatar_url TEXT,
                bio TEXT,
                company TEXT,
                location TEXT,
                blog TEXT,
                html_url TEXT,
                followers INTEGER DEFAULT 0,
                following INTEGER DEFAULT 0,
                public_repos INTEGER DEFAULT 0,
                created_at TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id)
            )
        ''')
        
        # GitHub repositories cache
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS github_repositories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                repo_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                full_name TEXT NOT NULL,
                description TEXT,
                private BOOLEAN DEFAULT FALSE,
                fork BOOLEAN DEFAULT FALSE,
                html_url TEXT,
                clone_url TEXT,
                ssh_url TEXT,
                language TEXT,
                stargazers_count INTEGER DEFAULT 0,
                watchers_count INTEGER DEFAULT 0,
                forks_count INTEGER DEFAULT 0,
                open_issues_count INTEGER DEFAULT 0,
                default_branch TEXT DEFAULT 'main',
                created_at TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, repo_id)
            )
        ''')
        
        # GitHub issues cache
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS github_issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                issue_id INTEGER NOT NULL,
                number INTEGER NOT NULL,
                title TEXT NOT NULL,
                body TEXT,
                state TEXT DEFAULT 'open',
                locked BOOLEAN DEFAULT FALSE,
                comments INTEGER DEFAULT 0,
                created_at TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                closed_at TIMESTAMP,
                html_url TEXT,
                UNIQUE(user_id, issue_id)
            )
        ''')
        
        # GitHub pull requests cache
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS github_pull_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                pr_id INTEGER NOT NULL,
                number INTEGER NOT NULL,
                title TEXT NOT NULL,
                body TEXT,
                state TEXT DEFAULT 'open',
                locked BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                closed_at TIMESTAMP,
                merged_at TIMESTAMP,
                html_url TEXT,
                UNIQUE(user_id, pr_id)
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("GitHub SQLite database initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize GitHub SQLite database: {e}")
        raise

# Initialize database
if DB_TYPE == 'sqlite':
    init_sqlite_db()

async def save_tokens(db_conn_pool, user_id: str, token_data: Dict[str, Any]) -> bool:
    """
    Save GitHub OAuth tokens for user
    """
    try:
        if DB_TYPE == 'postgres' and db_conn_pool:
            return await _save_tokens_postgres(db_conn_pool, user_id, token_data)
        elif DB_TYPE == 'sqlite':
            return await _save_tokens_sqlite(user_id, token_data)
        else:
            # Mock fallback
            MOCK_DB['github_tokens'][user_id] = {
                **token_data,
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            return True
    except Exception as e:
        logger.error(f"Error saving GitHub tokens for user {user_id}: {e}")
        return False

async def _save_tokens_postgres(db_conn_pool, user_id: str, token_data: Dict[str, Any]) -> bool:
    """Save tokens to PostgreSQL"""
    try:
        # Encrypt sensitive data
        access_token = token_data.get('access_token', '')
        refresh_token = token_data.get('refresh_token', '')
        
        if ENCRYPTION_AVAILABLE:
            access_token = encrypt_data(access_token, ATOM_OAUTH_ENCRYPTION_KEY)
            refresh_token = encrypt_data(refresh_token, ATOM_OAUTH_ENCRYPTION_KEY)
        
        async with db_conn_pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO github_oauth_tokens 
                (user_id, access_token, token_type, scope, expires_at, refresh_token)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (user_id) 
                DO UPDATE SET 
                access_token = $2, token_type = $3, scope = $4, expires_at = $5, 
                refresh_token = $6, updated_at = CURRENT_TIMESTAMP
            ''', (
                user_id,
                access_token,
                token_data.get('token_type', 'bearer'),
                token_data.get('scope'),
                token_data.get('expires_at'),
                refresh_token
            ))
        
        logger.info(f"GitHub tokens saved for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving GitHub tokens to PostgreSQL: {e}")
        return False

async def _save_tokens_sqlite(user_id: str, token_data: Dict[str, Any]) -> bool:
    """Save tokens to SQLite"""
    try:
        # Encrypt sensitive data
        access_token = token_data.get('access_token', '')
        refresh_token = token_data.get('refresh_token', '')
        
        if ENCRYPTION_AVAILABLE:
            access_token = encrypt_data(access_token, ATOM_OAUTH_ENCRYPTION_KEY)
            refresh_token = encrypt_data(refresh_token, ATOM_OAUTH_ENCRYPTION_KEY)
        
        db_path = os.getenv('ATOM_SQLITE_PATH', 'data/atom_development.db')
        async with aiosqlite.connect(db_path) as conn:
            await conn.execute('''
                INSERT OR REPLACE INTO github_oauth_tokens 
                (user_id, access_token, token_type, scope, expires_at, refresh_token)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                access_token,
                token_data.get('token_type', 'bearer'),
                token_data.get('scope'),
                token_data.get('expires_at'),
                refresh_token
            ))
            await conn.commit()
        
        logger.info(f"GitHub tokens saved for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving GitHub tokens to SQLite: {e}")
        return False

async def get_tokens(db_conn_pool, user_id: str) -> Optional[Dict[str, Any]]:
    """
    Get GitHub OAuth tokens for user
    """
    try:
        if DB_TYPE == 'postgres' and db_conn_pool:
            return await _get_tokens_postgres(db_conn_pool, user_id)
        elif DB_TYPE == 'sqlite':
            return await _get_tokens_sqlite(user_id)
        else:
            # Mock fallback
            return MOCK_DB['github_tokens'].get(user_id)
    except Exception as e:
        logger.error(f"Error getting GitHub tokens for user {user_id}: {e}")
        return None

async def _get_tokens_postgres(db_conn_pool, user_id: str) -> Optional[Dict[str, Any]]:
    """Get tokens from PostgreSQL"""
    try:
        async with db_conn_pool.acquire() as conn:
            row = await conn.fetchrow('''
                SELECT access_token, token_type, scope, expires_at, refresh_token,
                       created_at, updated_at
                FROM github_oauth_tokens 
                WHERE user_id = $1
            ''', user_id)
            
            if not row:
                return None
            
            # Decrypt sensitive data
            access_token = row['access_token']
            refresh_token = row['refresh_token']
            
            if ENCRYPTION_AVAILABLE:
                access_token = decrypt_data(access_token, ATOM_OAUTH_ENCRYPTION_KEY)
                refresh_token = decrypt_data(refresh_token, ATOM_OAUTH_ENCRYPTION_KEY)
            
            return {
                'access_token': access_token,
                'token_type': row['token_type'],
                'scope': row['scope'],
                'expires_at': row['expires_at'],
                'refresh_token': refresh_token,
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            }
        
    except Exception as e:
        logger.error(f"Error getting GitHub tokens from PostgreSQL: {e}")
        return None

async def _get_tokens_sqlite(user_id: str) -> Optional[Dict[str, Any]]:
    """Get tokens from SQLite"""
    try:
        db_path = os.getenv('ATOM_SQLITE_PATH', 'data/atom_development.db')
        async with aiosqlite.connect(db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute('''
                SELECT access_token, token_type, scope, expires_at, refresh_token,
                       created_at, updated_at
                FROM github_oauth_tokens 
                WHERE user_id = ?
            ''', (user_id,))
            row = await cursor.fetchone()
            
            if not row:
                return None
            
            # Decrypt sensitive data
            access_token = row['access_token']
            refresh_token = row['refresh_token']
            
            if ENCRYPTION_AVAILABLE:
                access_token = decrypt_data(access_token, ATOM_OAUTH_ENCRYPTION_KEY)
                refresh_token = decrypt_data(refresh_token, ATOM_OAUTH_ENCRYPTION_KEY)
            
            return {
                'access_token': access_token,
                'token_type': row['token_type'],
                'scope': row['scope'],
                'expires_at': row['expires_at'],
                'refresh_token': refresh_token,
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            }
        
    except Exception as e:
        logger.error(f"Error getting GitHub tokens from SQLite: {e}")
        return None

async def delete_tokens(db_conn_pool, user_id: str) -> bool:
    """
    Delete GitHub OAuth tokens for user
    """
    try:
        if DB_TYPE == 'postgres' and db_conn_pool:
            async with db_conn_pool.acquire() as conn:
                result = await conn.execute(
                    'DELETE FROM github_oauth_tokens WHERE user_id = $1',
                    user_id
                )
                return result != 'DELETE 0'
        
        elif DB_TYPE == 'sqlite':
            db_path = os.getenv('ATOM_SQLITE_PATH', 'data/atom_development.db')
            async with aiosqlite.connect(db_path) as conn:
                await conn.execute(
                    'DELETE FROM github_oauth_tokens WHERE user_id = ?',
                    (user_id,)
                )
                await conn.commit()
                return True
        
        else:
            # Mock fallback
            if user_id in MOCK_DB['github_tokens']:
                del MOCK_DB['github_tokens'][user_id]
                return True
            return False
        
    except Exception as e:
        logger.error(f"Error deleting GitHub tokens for user {user_id}: {e}")
        return False

async def save_user_github_tokens(db_conn_pool, user_id: str, token_data: Dict[str, Any]) -> bool:
    """
    Save GitHub tokens and user data (combined operation)
    """
    try:
        # Save tokens
        tokens_saved = await save_tokens(db_conn_pool, user_id, token_data)
        
        # Extract and save user info if available
        if 'user_info' in token_data:
            user_info = token_data['user_info']
            user_saved = await save_github_user(db_conn_pool, user_id, user_info)
        else:
            user_saved = True
        
        return tokens_saved and user_saved
        
    except Exception as e:
        logger.error(f"Error saving GitHub user tokens for user {user_id}: {e}")
        return False

async def get_user_github_tokens(db_conn_pool, user_id: str) -> Optional[Dict[str, Any]]:
    """
    Get GitHub tokens with user info
    """
    try:
        # Get tokens
        tokens = await get_tokens(db_conn_pool, user_id)
        if not tokens:
            return None
        
        # Get user info
        user_info = await get_github_user(db_conn_pool, user_id)
        
        return {
            **tokens,
            'user_info': user_info
        }
        
    except Exception as e:
        logger.error(f"Error getting user GitHub tokens for user {user_id}: {e}")
        return None

async def delete_user_github_tokens(db_conn_pool, user_id: str) -> bool:
    """
    Delete GitHub tokens and user data (combined operation)
    """
    try:
        # Delete tokens
        tokens_deleted = await delete_tokens(db_conn_pool, user_id)
        
        # Delete user info
        user_deleted = await delete_github_user(db_conn_pool, user_id)
        
        return tokens_deleted or user_deleted
        
    except Exception as e:
        logger.error(f"Error deleting user GitHub tokens for user {user_id}: {e}")
        return False

# GitHub user data operations
async def save_github_user(db_conn_pool, user_id: str, user_info: Dict[str, Any]) -> bool:
    """Save GitHub user information"""
    try:
        if DB_TYPE == 'postgres' and db_conn_pool:
            return await _save_github_user_postgres(db_conn_pool, user_id, user_info)
        elif DB_TYPE == 'sqlite':
            return await _save_github_user_sqlite(user_id, user_info)
        else:
            # Mock fallback
            MOCK_DB['github_users'][user_id] = {
                **user_info,
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            return True
    except Exception as e:
        logger.error(f"Error saving GitHub user info for user {user_id}: {e}")
        return False

async def _save_github_user_postgres(db_conn_pool, user_id: str, user_info: Dict[str, Any]) -> bool:
    """Save GitHub user info to PostgreSQL"""
    try:
        async with db_conn_pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO github_users 
                (user_id, github_user_id, login, name, email, avatar_url, bio,
                 company, location, blog, html_url, followers, following, public_repos)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                ON CONFLICT (user_id) 
                DO UPDATE SET 
                github_user_id = $2, login = $3, name = $4, email = $5, avatar_url = $6,
                bio = $7, company = $8, location = $9, blog = $10, html_url = $11,
                followers = $12, following = $13, public_repos = $14,
                updated_at = CURRENT_TIMESTAMP
            ''', (
                user_id,
                user_info.get('id'),
                user_info.get('login'),
                user_info.get('name'),
                user_info.get('email'),
                user_info.get('avatar_url'),
                user_info.get('bio'),
                user_info.get('company'),
                user_info.get('location'),
                user_info.get('blog'),
                user_info.get('html_url'),
                user_info.get('followers', 0),
                user_info.get('following', 0),
                user_info.get('public_repos', 0)
            ))
        
        logger.info(f"GitHub user info saved for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving GitHub user info to PostgreSQL: {e}")
        return False

async def _save_github_user_sqlite(user_id: str, user_info: Dict[str, Any]) -> bool:
    """Save GitHub user info to SQLite"""
    try:
        db_path = os.getenv('ATOM_SQLITE_PATH', 'data/atom_development.db')
        async with aiosqlite.connect(db_path) as conn:
            await conn.execute('''
                INSERT OR REPLACE INTO github_users 
                (user_id, github_user_id, login, name, email, avatar_url, bio,
                 company, location, blog, html_url, followers, following, public_repos)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                user_info.get('id'),
                user_info.get('login'),
                user_info.get('name'),
                user_info.get('email'),
                user_info.get('avatar_url'),
                user_info.get('bio'),
                user_info.get('company'),
                user_info.get('location'),
                user_info.get('blog'),
                user_info.get('html_url'),
                user_info.get('followers', 0),
                user_info.get('following', 0),
                user_info.get('public_repos', 0)
            ))
            await conn.commit()
        
        logger.info(f"GitHub user info saved for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving GitHub user info to SQLite: {e}")
        return False

async def get_github_user(db_conn_pool, user_id: str) -> Optional[Dict[str, Any]]:
    """Get GitHub user information"""
    try:
        if DB_TYPE == 'postgres' and db_conn_pool:
            return await _get_github_user_postgres(db_conn_pool, user_id)
        elif DB_TYPE == 'sqlite':
            return await _get_github_user_sqlite(user_id)
        else:
            # Mock fallback
            return MOCK_DB['github_users'].get(user_id)
    except Exception as e:
        logger.error(f"Error getting GitHub user info for user {user_id}: {e}")
        return None

async def _get_github_user_postgres(db_conn_pool, user_id: str) -> Optional[Dict[str, Any]]:
    """Get GitHub user info from PostgreSQL"""
    try:
        async with db_conn_pool.acquire() as conn:
            row = await conn.fetchrow('''
                SELECT github_user_id, login, name, email, avatar_url, bio,
                       company, location, blog, html_url, followers, following,
                       public_repos, created_at, updated_at
                FROM github_users 
                WHERE user_id = $1
            ''', user_id)
            
            if not row:
                return None
            
            return {
                'id': row['github_user_id'],
                'login': row['login'],
                'name': row['name'],
                'email': row['email'],
                'avatar_url': row['avatar_url'],
                'bio': row['bio'],
                'company': row['company'],
                'location': row['location'],
                'blog': row['blog'],
                'html_url': row['html_url'],
                'followers': row['followers'],
                'following': row['following'],
                'public_repos': row['public_repos'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            }
        
    except Exception as e:
        logger.error(f"Error getting GitHub user info from PostgreSQL: {e}")
        return None

async def _get_github_user_sqlite(user_id: str) -> Optional[Dict[str, Any]]:
    """Get GitHub user info from SQLite"""
    try:
        db_path = os.getenv('ATOM_SQLITE_PATH', 'data/atom_development.db')
        async with aiosqlite.connect(db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute('''
                SELECT github_user_id, login, name, email, avatar_url, bio,
                       company, location, blog, html_url, followers, following,
                       public_repos, created_at, updated_at
                FROM github_users 
                WHERE user_id = ?
            ''', (user_id,))
            row = await cursor.fetchone()
            
            if not row:
                return None
            
            return {
                'id': row['github_user_id'],
                'login': row['login'],
                'name': row['name'],
                'email': row['email'],
                'avatar_url': row['avatar_url'],
                'bio': row['bio'],
                'company': row['company'],
                'location': row['location'],
                'blog': row['blog'],
                'html_url': row['html_url'],
                'followers': row['followers'],
                'following': row['following'],
                'public_repos': row['public_repos'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            }
        
    except Exception as e:
        logger.error(f"Error getting GitHub user info from SQLite: {e}")
        return None

async def delete_github_user(db_conn_pool, user_id: str) -> bool:
    """Delete GitHub user information"""
    try:
        if DB_TYPE == 'postgres' and db_conn_pool:
            async with db_conn_pool.acquire() as conn:
                result = await conn.execute(
                    'DELETE FROM github_users WHERE user_id = $1',
                    user_id
                )
                return result != 'DELETE 0'
        
        elif DB_TYPE == 'sqlite':
            db_path = os.getenv('ATOM_SQLITE_PATH', 'data/atom_development.db')
            async with aiosqlite.connect(db_path) as conn:
                await conn.execute(
                    'DELETE FROM github_users WHERE user_id = ?',
                    (user_id,)
                )
                await conn.commit()
                return True
        
        else:
            # Mock fallback
            if user_id in MOCK_DB['github_users']:
                del MOCK_DB['github_users'][user_id]
                return True
            return False
        
    except Exception as e:
        logger.error(f"Error deleting GitHub user info for user {user_id}: {e}")
        return False

# Helper functions for GitHub-specific operations
async def refresh_github_tokens(db_conn_pool, user_id: str, new_token_data: Dict[str, Any]) -> bool:
    """Refresh GitHub tokens with new access token"""
    try:
        # Get existing tokens
        existing_tokens = await get_tokens(db_conn_pool, user_id)
        if not existing_tokens:
            return False
        
        # Update with new token data
        updated_token_data = {
            **existing_tokens,
            **new_token_data,
            'updated_at': datetime.utcnow().isoformat()
        }
        
        return await save_tokens(db_conn_pool, user_id, updated_token_data)
        
    except Exception as e:
        logger.error(f"Error refreshing GitHub tokens for user {user_id}: {e}")
        return False

async def get_github_user_repositories(db_conn_pool, user_id: str) -> List[Dict[str, Any]]:
    """Get cached repositories for GitHub user"""
    try:
        if DB_TYPE == 'postgres' and db_conn_pool:
            async with db_conn_pool.acquire() as conn:
                rows = await conn.fetch('''
                    SELECT repo_id, name, full_name, description, private, fork,
                           html_url, clone_url, ssh_url, language, stargazers_count,
                           watchers_count, forks_count, open_issues_count,
                           default_branch, created_at, updated_at
                    FROM github_repositories 
                    WHERE user_id = $1
                    ORDER BY updated_at DESC
                ''', user_id)
                
                return [dict(row) for row in rows]
        
        elif DB_TYPE == 'sqlite':
            db_path = os.getenv('ATOM_SQLITE_PATH', 'data/atom_development.db')
            async with aiosqlite.connect(db_path) as conn:
                conn.row_factory = aiosqlite.Row
                cursor = await conn.execute('''
                    SELECT repo_id, name, full_name, description, private, fork,
                           html_url, clone_url, ssh_url, language, stargazers_count,
                           watchers_count, forks_count, open_issues_count,
                           default_branch, created_at, updated_at
                    FROM github_repositories 
                    WHERE user_id = ?
                    ORDER BY updated_at DESC
                ''', (user_id,))
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        
        else:
            # Mock fallback
            return [repo for repo in MOCK_DB['github_repos'].values() 
                   if repo.get('user_id') == user_id]
        
    except Exception as e:
        logger.error(f"Error getting cached GitHub repositories for user {user_id}: {e}")
        return []

async def save_github_repositories(db_conn_pool, user_id: str, repos: List[Dict[str, Any]]) -> bool:
    """Save GitHub repositories cache"""
    try:
        if not repos:
            return True
        
        if DB_TYPE == 'postgres' and db_conn_pool:
            async with db_conn_pool.acquire() as conn:
                for repo in repos:
                    await conn.execute('''
                        INSERT INTO github_repositories 
                        (user_id, repo_id, name, full_name, description, private, fork,
                         html_url, clone_url, ssh_url, language, stargazers_count,
                         watchers_count, forks_count, open_issues_count, default_branch)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                        ON CONFLICT (user_id, repo_id) 
                        DO UPDATE SET 
                        name = $3, full_name = $4, description = $5, private = $6,
                        fork = $7, html_url = $8, clone_url = $9, ssh_url = $10,
                        language = $11, stargazers_count = $12, watchers_count = $13,
                        forks_count = $14, open_issues_count = $15, default_branch = $16,
                        updated_at = CURRENT_TIMESTAMP
                    ''', (
                        user_id,
                        repo.get('id'),
                        repo.get('name'),
                        repo.get('full_name'),
                        repo.get('description'),
                        repo.get('private', False),
                        repo.get('fork', False),
                        repo.get('html_url'),
                        repo.get('clone_url'),
                        repo.get('ssh_url'),
                        repo.get('language'),
                        repo.get('stargazers_count', 0),
                        repo.get('watchers_count', 0),
                        repo.get('forks_count', 0),
                        repo.get('open_issues_count', 0),
                        repo.get('default_branch', 'main')
                    ))
        
        elif DB_TYPE == 'sqlite':
            db_path = os.getenv('ATOM_SQLITE_PATH', 'data/atom_development.db')
            async with aiosqlite.connect(db_path) as conn:
                for repo in repos:
                    await conn.execute('''
                        INSERT OR REPLACE INTO github_repositories 
                        (user_id, repo_id, name, full_name, description, private, fork,
                         html_url, clone_url, ssh_url, language, stargazers_count,
                         watchers_count, forks_count, open_issues_count, default_branch)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        user_id,
                        repo.get('id'),
                        repo.get('name'),
                        repo.get('full_name'),
                        repo.get('description'),
                        repo.get('private', False),
                        repo.get('fork', False),
                        repo.get('html_url'),
                        repo.get('clone_url'),
                        repo.get('ssh_url'),
                        repo.get('language'),
                        repo.get('stargazers_count', 0),
                        repo.get('watchers_count', 0),
                        repo.get('forks_count', 0),
                        repo.get('open_issues_count', 0),
                        repo.get('default_branch', 'main')
                    ))
                await conn.commit()
        
        else:
            # Mock fallback
            for repo in repos:
                repo_key = f"{user_id}_{repo.get('id')}"
                MOCK_DB['github_repositories'][repo_key] = {
                    **repo,
                    'user_id': user_id,
                    'updated_at': datetime.utcnow().isoformat()
                }
        
        logger.info(f"Saved {len(repos)} GitHub repositories for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving GitHub repositories for user {user_id}: {e}")
        return False

# Utility functions
def is_token_expired(expires_at: str) -> bool:
    """Check if token is expired"""
    if not expires_at:
        return True
    
    try:
        expiry_time = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        current_time = datetime.now(timezone.utc)
        # Add 5 minute buffer
        return current_time >= expiry_time - timedelta(minutes=5)
    except Exception:
        return True

async def cleanup_expired_tokens(db_conn_pool) -> int:
    """Clean up expired tokens"""
    try:
        # Implementation depends on database type
        # This is a placeholder for cleanup logic
        logger.info("Cleaning up expired GitHub tokens")
        return 0
    except Exception as e:
        logger.error(f"Error cleaning up expired GitHub tokens: {e}")
        return 0