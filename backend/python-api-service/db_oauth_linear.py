"""
Linear OAuth Token Database Operations
Secure storage for Linear OAuth tokens in PostgreSQL
"""

import logging
from datetime import datetime, timezone
import base64

logger = logging.getLogger(__name__)

async def save_tokens(db_conn_pool, user_id: str, access_token: str, refresh_token: str, expires_at: datetime, scope: str, user_info: dict = None):
    """Save Linear OAuth tokens"""
    sql = """
        INSERT INTO user_linear_oauth_tokens 
        (user_id, access_token, refresh_token, expires_at, scope, user_info, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE SET
            access_token = EXCLUDED.access_token,
            refresh_token = EXCLUDED.refresh_token,
            expires_at = EXCLUDED.expires_at,
            scope = EXCLUDED.scope,
            user_info = EXCLUDED.user_info,
            updated_at = EXCLUDED.updated_at
    """
    
    conn = await db_conn_pool.acquire()
    try:
        now = datetime.now(timezone.utc)
        
        await conn.execute(
            sql,
            (
                user_id,
                access_token,
                refresh_token,
                expires_at,
                scope,
                user_info,
                now,
                now
            )
        )
        
        await conn.commit()
        logger.info(f"Successfully saved Linear tokens for user {user_id}")
        
    except Exception as e:
        await conn.rollback()
        logger.error(f"Error saving Linear tokens for user {user_id}: {e}")
        raise
    finally:
        await db_conn_pool.release(conn)

async def get_tokens(db_conn_pool, user_id: str):
    """Get Linear OAuth tokens for user"""
    sql = """
        SELECT access_token, refresh_token, expires_at, scope, user_info, updated_at
        FROM user_linear_oauth_tokens
        WHERE user_id = %s
    """
    
    conn = await db_conn_pool.acquire()
    try:
        result = await conn.execute(sql, (user_id,))
        row = await result.fetchone()
        
        if not row:
            logger.warning(f"No Linear tokens found for user {user_id}")
            return None
        
        tokens = {
            'access_token': row['access_token'],
            'refresh_token': row['refresh_token'],
            'expires_at': row['expires_at'],
            'scope': row['scope'],
            'user_info': row['user_info'],
            'updated_at': row['updated_at']
        }
        
        # Check if tokens are expired
        if datetime.now(timezone.utc) >= tokens['expires_at']:
            logger.warning(f"Linear tokens for user {user_id} are expired")
            return None
        
        logger.info(f"Successfully retrieved Linear tokens for user {user_id}")
        return tokens
        
    except Exception as e:
        logger.error(f"Error retrieving Linear tokens for user {user_id}: {e}")
        raise
    finally:
        await db_conn_pool.release(conn)

async def delete_tokens(db_conn_pool, user_id: str):
    """Delete Linear OAuth tokens for user"""
    sql = "DELETE FROM user_linear_oauth_tokens WHERE user_id = %s"
    
    conn = await db_conn_pool.acquire()
    try:
        await conn.execute(sql, (user_id,))
        await conn.commit()
        logger.info(f"Successfully deleted Linear tokens for user {user_id}")
        
    except Exception as e:
        await conn.rollback()
        logger.error(f"Error deleting Linear tokens for user {user_id}: {e}")
        raise
    finally:
        await db_conn_pool.release(conn)

async def get_user_linear_issues(db_conn_pool, user_id: str, issue_ids: list = None):
    """Get Linear issues for user from database"""
    if not issue_ids:
        return []
    
    # Create placeholders for IN clause
    placeholders = ','.join(['%s'] * len(issue_ids))
    sql = f"""
        SELECT issue_id, identifier, title, description, status_id, status_name, status_color, status_type,
               priority_id, priority_label, priority_level, assignee_id, assignee_name, assignee_avatar_url,
               project_id, project_name, team_id, team_name, labels, created_at, updated_at, due_date, state
        FROM user_linear_issues
        WHERE user_id = %s AND issue_id IN ({placeholders})
        ORDER BY created_at DESC
    """
    
    conn = await db_conn_pool.acquire()
    try:
        result = await conn.execute(sql, [user_id] + issue_ids)
        rows = await result.fetchall()
        
        issues = []
        for row in rows:
            issues.append({
                'issue_id': row['issue_id'],
                'identifier': row['identifier'],
                'title': row['title'],
                'description': row['description'],
                'status': {
                    'id': row['status_id'],
                    'name': row['status_name'],
                    'color': row['status_color'],
                    'type': row['status_type']
                },
                'priority': {
                    'id': row['priority_id'],
                    'label': row['priority_label'],
                    'priority': row['priority_level']
                },
                'assignee': row['assignee_id'] ? {
                    'id': row['assignee_id'],
                    'name': row['assignee_name'],
                    'avatarUrl': row['assignee_avatar_url']
                } : None,
                'project': {
                    'id': row['project_id'],
                    'name': row['project_name']
                },
                'team': {
                    'id': row['team_id'],
                    'name': row['team_name']
                },
                'labels': row['labels'] or [],
                'created_at': row['created_at'],
                'updated_at': row['updated_at'],
                'dueDate': row['due_date'],
                'state': row['state']
            })
        
        logger.info(f"Successfully retrieved {len(issues)} Linear issues for user {user_id}")
        return issues
        
    except Exception as e:
        logger.error(f"Error retrieving Linear issues for user {user_id}: {e}")
        raise
    finally:
        await db_conn_pool.release(conn)

async def save_linear_issue(db_conn_pool, user_id: str, issue_data: dict):
    """Save Linear issue metadata"""
    sql = """
        INSERT INTO user_linear_issues 
        (user_id, issue_id, identifier, title, description, status_id, status_name, status_color, status_type,
         priority_id, priority_label, priority_level, assignee_id, assignee_name, assignee_avatar_url,
         project_id, project_name, team_id, team_name, labels, created_at, updated_at, due_date, state, metadata, stored_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id, issue_id) DO UPDATE SET
            identifier = EXCLUDED.identifier,
            title = EXCLUDED.title,
            description = EXCLUDED.description,
            status_id = EXCLUDED.status_id,
            status_name = EXCLUDED.status_name,
            status_color = EXCLUDED.status_color,
            status_type = EXCLUDED.status_type,
            priority_id = EXCLUDED.priority_id,
            priority_label = EXCLUDED.priority_label,
            priority_level = EXCLUDED.priority_level,
            assignee_id = EXCLUDED.assignee_id,
            assignee_name = EXCLUDED.assignee_name,
            assignee_avatar_url = EXCLUDED.assignee_avatar_url,
            project_id = EXCLUDED.project_id,
            project_name = EXCLUDED.project_name,
            team_id = EXCLUDED.team_id,
            team_name = EXCLUDED.team_name,
            labels = EXCLUDED.labels,
            updated_at = EXCLUDED.updated_at,
            due_date = EXCLUDED.due_date,
            state = EXCLUDED.state,
            metadata = EXCLUDED.metadata,
            stored_at = EXCLUDED.stored_at
    """
    
    conn = await db_conn_pool.acquire()
    try:
        now = datetime.now(timezone.utc)
        
        await conn.execute(
            sql,
            (
                user_id,
                issue_data['issue_id'],
                issue_data.get('identifier'),
                issue_data.get('title'),
                issue_data.get('description'),
                issue_data.get('status', {}).get('id'),
                issue_data.get('status', {}).get('name'),
                issue_data.get('status', {}).get('color'),
                issue_data.get('status', {}).get('type'),
                issue_data.get('priority', {}).get('id'),
                issue_data.get('priority', {}).get('label'),
                issue_data.get('priority', {}).get('priority'),
                issue_data.get('assignee', {}).get('id'),
                issue_data.get('assignee', {}).get('name'),
                issue_data.get('assignee', {}).get('avatarUrl'),
                issue_data.get('project', {}).get('id'),
                issue_data.get('project', {}).get('name'),
                issue_data.get('team', {}).get('id'),
                issue_data.get('team', {}).get('name'),
                issue_data.get('labels', []),
                issue_data.get('createdAt'),
                issue_data.get('updatedAt'),
                issue_data.get('dueDate'),
                issue_data.get('state'),
                issue_data.get('metadata'),
                now
            )
        )
        
        await conn.commit()
        logger.debug(f"Successfully saved Linear issue {issue_data.get('identifier')} for user {user_id}")
        
    except Exception as e:
        await conn.rollback()
        logger.error(f"Error saving Linear issue for user {user_id}: {e}")
        raise
    finally:
        await db_conn_pool.release(conn)

async def get_user_linear_projects(db_conn_pool, user_id: str, project_ids: list = None):
    """Get Linear projects for user from database"""
    if not project_ids:
        return []
    
    # Create placeholders for IN clause
    placeholders = ','.join(['%s'] * len(project_ids))
    sql = f"""
        SELECT project_id, name, description, url, icon, color, team_id, team_name, team_icon,
               state, progress, completed_issues_count, started_issues_count, unstarted_issues_count,
               backlogged_issues_count, canceled_issues_count, scope, created_at, updated_at
        FROM user_linear_projects
        WHERE user_id = %s AND project_id IN ({placeholders})
        ORDER BY created_at DESC
    """
    
    conn = await db_conn_pool.acquire()
    try:
        result = await conn.execute(sql, [user_id] + project_ids)
        rows = await result.fetchall()
        
        projects = []
        for row in rows:
            projects.append({
                'project_id': row['project_id'],
                'name': row['name'],
                'description': row['description'],
                'url': row['url'],
                'icon': row['icon'],
                'color': row['color'],
                'team': {
                    'id': row['team_id'],
                    'name': row['team_name'],
                    'icon': row['team_icon']
                },
                'state': row['state'],
                'progress': row['progress'],
                'completedIssuesCount': row['completed_issues_count'],
                'startedIssuesCount': row['started_issues_count'],
                'unstartedIssuesCount': row['unstarted_issues_count'],
                'backloggedIssuesCount': row['backlogged_issues_count'],
                'canceledIssuesCount': row['canceled_issues_count'],
                'scope': row['scope'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            })
        
        logger.info(f"Successfully retrieved {len(projects)} Linear projects for user {user_id}")
        return projects
        
    except Exception as e:
        logger.error(f"Error retrieving Linear projects for user {user_id}: {e}")
        raise
    finally:
        await db_conn_pool.release(conn)

async def save_linear_project(db_conn_pool, user_id: str, project_data: dict):
    """Save Linear project metadata"""
    sql = """
        INSERT INTO user_linear_projects 
        (user_id, project_id, name, description, url, icon, color, team_id, team_name, team_icon,
         state, progress, completed_issues_count, started_issues_count, unstarted_issues_count,
         backlogged_issues_count, canceled_issues_count, scope, created_at, updated_at, metadata, stored_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id, project_id) DO UPDATE SET
            name = EXCLUDED.name,
            description = EXCLUDED.description,
            url = EXCLUDED.url,
            icon = EXCLUDED.icon,
            color = EXCLUDED.color,
            team_id = EXCLUDED.team_id,
            team_name = EXCLUDED.team_name,
            team_icon = EXCLUDED.team_icon,
            state = EXCLUDED.state,
            progress = EXCLUDED.progress,
            completed_issues_count = EXCLUDED.completed_issues_count,
            started_issues_count = EXCLUDED.started_issues_count,
            unstarted_issues_count = EXCLUDED.unstarted_issues_count,
            backlogged_issues_count = EXCLUDED.backlogged_issues_count,
            canceled_issues_count = EXCLUDED.canceled_issues_count,
            scope = EXCLUDED.scope,
            updated_at = EXCLUDED.updated_at,
            metadata = EXCLUDED.metadata,
            stored_at = EXCLUDED.stored_at
    """
    
    conn = await db_conn_pool.acquire()
    try:
        now = datetime.now(timezone.utc)
        
        await conn.execute(
            sql,
            (
                user_id,
                project_data['project_id'],
                project_data.get('name'),
                project_data.get('description'),
                project_data.get('url'),
                project_data.get('icon'),
                project_data.get('color'),
                project_data.get('team', {}).get('id'),
                project_data.get('team', {}).get('name'),
                project_data.get('team', {}).get('icon'),
                project_data.get('state'),
                project_data.get('progress'),
                project_data.get('completedIssuesCount'),
                project_data.get('startedIssuesCount'),
                project_data.get('unstartedIssuesCount'),
                project_data.get('backloggedIssuesCount'),
                project_data.get('canceledIssuesCount'),
                project_data.get('scope'),
                project_data.get('createdAt'),
                project_data.get('updatedAt'),
                project_data.get('metadata'),
                now
            )
        )
        
        await conn.commit()
        logger.debug(f"Successfully saved Linear project {project_data.get('name')} for user {user_id}")
        
    except Exception as e:
        await conn.rollback()
        logger.error(f"Error saving Linear project for user {user_id}: {e}")
        raise
    finally:
        await db_conn_pool.release(conn)

async def get_user_linear_teams(db_conn_pool, user_id: str, team_ids: list = None):
    """Get Linear teams for user from database"""
    if not team_ids:
        return []
    
    # Create placeholders for IN clause
    placeholders = ','.join(['%s'] * len(team_ids))
    sql = f"""
        SELECT team_id, name, description, icon, color, organization_id, organization_name, organization_url_key,
               created_at, updated_at, member_count, issues_count, cycles_count
        FROM user_linear_teams
        WHERE user_id = %s AND team_id IN ({placeholders})
        ORDER BY created_at DESC
    """
    
    conn = await db_conn_pool.acquire()
    try:
        result = await conn.execute(sql, [user_id] + team_ids)
        rows = await result.fetchall()
        
        teams = []
        for row in rows:
            teams.append({
                'team_id': row['team_id'],
                'name': row['name'],
                'description': row['description'],
                'icon': row['icon'],
                'color': row['color'],
                'organization': {
                    'id': row['organization_id'],
                    'name': row['organization_name'],
                    'urlKey': row['organization_url_key']
                },
                'created_at': row['created_at'],
                'updated_at': row['updated_at'],
                'memberCount': row['member_count'],
                'issuesCount': row['issues_count'],
                'cyclesCount': row['cycles_count']
            })
        
        logger.info(f"Successfully retrieved {len(teams)} Linear teams for user {user_id}")
        return teams
        
    except Exception as e:
        logger.error(f"Error retrieving Linear teams for user {user_id}: {e}")
        raise
    finally:
        await db_conn_pool.release(conn)

async def save_linear_team(db_conn_pool, user_id: str, team_data: dict):
    """Save Linear team metadata"""
    sql = """
        INSERT INTO user_linear_teams 
        (user_id, team_id, name, description, icon, color, organization_id, organization_name, organization_url_key,
         created_at, updated_at, member_count, issues_count, cycles_count, metadata, stored_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id, team_id) DO UPDATE SET
            name = EXCLUDED.name,
            description = EXCLUDED.description,
            icon = EXCLUDED.icon,
            color = EXCLUDED.color,
            organization_id = EXCLUDED.organization_id,
            organization_name = EXCLUDED.organization_name,
            organization_url_key = EXCLUDED.organization_url_key,
            updated_at = EXCLUDED.updated_at,
            member_count = EXCLUDED.member_count,
            issues_count = EXCLUDED.issues_count,
            cycles_count = EXCLUDED.cycles_count,
            metadata = EXCLUDED.metadata,
            stored_at = EXCLUDED.stored_at
    """
    
    conn = await db_conn_pool.acquire()
    try:
        now = datetime.now(timezone.utc)
        
        await conn.execute(
            sql,
            (
                user_id,
                team_data['team_id'],
                team_data.get('name'),
                team_data.get('description'),
                team_data.get('icon'),
                team_data.get('color'),
                team_data.get('organization', {}).get('id'),
                team_data.get('organization', {}).get('name'),
                team_data.get('organization', {}).get('urlKey'),
                team_data.get('createdAt'),
                team_data.get('updatedAt'),
                team_data.get('memberCount'),
                team_data.get('issuesCount'),
                team_data.get('cyclesCount'),
                team_data.get('metadata'),
                now
            )
        )
        
        await conn.commit()
        logger.debug(f"Successfully saved Linear team {team_data.get('name')} for user {user_id}")
        
    except Exception as e:
        await conn.rollback()
        logger.error(f"Error saving Linear team for user {user_id}: {e}")
        raise
    finally:
        await db_conn_pool.release(conn)

# Helper functions
async def get_all_users_with_linear_tokens(db_conn_pool):
    """Get all users with valid Linear tokens"""
    sql = """
        SELECT user_id, access_token, refresh_token, expires_at, scope, user_info, updated_at
        FROM user_linear_oauth_tokens
        WHERE expires_at > %s
        ORDER BY updated_at DESC
    """
    
    conn = await db_conn_pool.acquire()
    try:
        now = datetime.now(timezone.utc)
        result = await conn.execute(sql, (now,))
        rows = await result.fetchall()
        
        users = []
        for row in rows:
            users.append({
                'user_id': row['user_id'],
                'access_token': row['access_token'],
                'refresh_token': row['refresh_token'],
                'expires_at': row['expires_at'],
                'scope': row['scope'],
                'user_info': row['user_info'],
                'updated_at': row['updated_at']
            })
        
        logger.info(f"Successfully retrieved {len(users)} users with Linear tokens")
        return users
        
    except Exception as e:
        logger.error(f"Error retrieving users with Linear tokens: {e}")
        raise
    finally:
        await db_conn_pool.release(conn)

async def refresh_linear_tokens(db_conn_pool, user_id: str, new_access_token: str, new_refresh_token: str, expires_at: datetime, scope: str):
    """Refresh Linear OAuth tokens"""
    sql = """
        UPDATE user_linear_oauth_tokens
        SET access_token = %s, refresh_token = %s, expires_at = %s, scope = %s, updated_at = %s
        WHERE user_id = %s
    """
    
    conn = await db_conn_pool.acquire()
    try:
        now = datetime.now(timezone.utc)
        
        await conn.execute(
            sql,
            (new_access_token, new_refresh_token, expires_at, scope, now, user_id)
        )
        
        await conn.commit()
        logger.info(f"Successfully refreshed Linear tokens for user {user_id}")
        
    except Exception as e:
        await conn.rollback()
        logger.error(f"Error refreshing Linear tokens for user {user_id}: {e}")
        raise
    finally:
        await db_conn_pool.release(conn)

async def update_linear_user_info(db_conn_pool, user_id: str, user_info: dict):
    """Update Linear user information"""
    sql = """
        UPDATE user_linear_oauth_tokens
        SET user_info = %s, updated_at = %s
        WHERE user_id = %s
    """
    
    conn = await db_conn_pool.acquire()
    try:
        now = datetime.now(timezone.utc)
        
        await conn.execute(sql, (user_info, now, user_id))
        await conn.commit()
        logger.info(f"Successfully updated Linear user info for user {user_id}")
        
    except Exception as e:
        await conn.rollback()
        logger.error(f"Error updating Linear user info for user {user_id}: {e}")
        raise
    finally:
        await db_conn_pool.release(conn)