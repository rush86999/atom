"""
VS Code Enhanced Service Implementation
Complete VS Code development environment integration with workspace management
"""

import os
import logging
import json
import asyncio
import subprocess
import platform
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, asdict
import httpx
import aiofiles
from pathlib import Path

# Configure logging
logger = logging.getLogger(__name__)

# VS Code API configuration
VSCODE_API_BASE_URL = "https://marketplace.visualstudio.com/_apis/public/gallery/extensionquery"
VSCODE_EXTENSIONS_API = "https://marketplace.visualstudio.com/_apis/public/gallery/extensionquery"
VSCODE_THEME_API = "https://raw.githubusercontent.com/microsoft/vscode/master/src/vs/platform/theme/common/colorThemeData.ts"

@dataclass
class VSCodeFile:
    """VS Code file representation"""
    path: str
    name: str
    extension: str
    size: int
    created_at: str
    modified_at: str
    content: str
    content_hash: str
    language: str
    encoding: str
    line_count: int
    char_count: int
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

@dataclass
class VSCodeProject:
    """VS Code project/workspace representation"""
    id: str
    name: str
    path: str
    type: str  # workspace, folder, file
    files: List[VSCodeFile]
    folders: List[str]
    settings: Dict[str, Any]
    extensions: List[str]
    git_info: Dict[str, Any]
    build_system: str
    language_stats: Dict[str, int]
    last_activity: str
    created_at: str
    updated_at: str
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

@dataclass
class VSCodeExtension:
    """VS Code extension representation"""
    id: str
    name: str
    publisher: Dict[str, Any]
    description: str
    version: str
    category: str
    tags: List[str]
    release_date: str
    last_updated: str
    download_count: int
    rating: float
    is_pre_release: bool
    dependencies: List[str]
    contributes: Dict[str, Any]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

@dataclass
class VSCodeSettings:
    """VS Code settings representation"""
    user_settings: Dict[str, Any]
    workspace_settings: Dict[str, Any]
    folder_settings: Dict[str, str]
    keybindings: List[Dict[str, Any]]
    snippets: Dict[str, Any]
    tasks: List[Dict[str, Any]]
    launch: List[Dict[str, Any]]
    extensions: Dict[str, Any]
    themes: Dict[str, Any]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

@dataclass
class VSCodeActivity:
    """VS Code development activity representation"""
    id: str
    user_id: str
    project_id: str
    action_type: str
    file_path: str
    content: str
    timestamp: str
    language: str
    session_id: str
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

class VSCodeEnhancedService:
    """Enhanced VS Code service with complete development environment integration"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.api_base_url = VSCODE_API_BASE_URL
        self.extensions_api = VSCODE_EXTENSIONS_API
        self.theme_api = VSCODE_THEME_API
        self.workspace_cache = {}
        self.file_cache = {}
        self.extension_cache = {}
        
        # Supported file types and languages
        self.language_mapping = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'javascriptreact',
            '.tsx': 'typescriptreact',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.cs': 'csharp',
            '.go': 'go',
            '.rs': 'rust',
            '.php': 'php',
            '.rb': 'ruby',
            '.swift': 'swift',
            '.kt': 'kotlin',
            '.scala': 'scala',
            '.r': 'r',
            '.m': 'objective-c',
            '.dart': 'dart',
            '.lua': 'lua',
            '.sh': 'shell',
            '.ps1': 'powershell',
            '.bat': 'batch',
            '.cmd': 'batch',
            '.html': 'html',
            '.htm': 'html',
            '.xml': 'xml',
            '.css': 'css',
            '.scss': 'scss',
            '.sass': 'sass',
            '.less': 'less',
            '.json': 'json',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.toml': 'toml',
            '.ini': 'ini',
            '.md': 'markdown',
            '.txt': 'plaintext',
            '.sql': 'sql',
            '.graphql': 'graphql',
            '.dockerfile': 'dockerfile',
            '.docker-compose.yml': 'yaml',
            '.docker-compose.yaml': 'yaml'
        }
        
        # Build system indicators
        self.build_system_indicators = {
            'npm': ['package.json', 'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml'],
            'python': ['setup.py', 'requirements.txt', 'Pipfile', 'pyproject.toml', 'poetry.lock'],
            'maven': ['pom.xml', 'pom.xml'],
            'gradle': ['build.gradle', 'settings.gradle', 'gradlew'],
            'cargo': ['Cargo.toml', 'Cargo.lock'],
            'cmake': ['CMakeLists.txt', 'CMakeCache.txt'],
            'make': ['Makefile', 'makefile'],
            'docker': ['Dockerfile', 'docker-compose.yml', 'docker-compose.yaml', '.dockerignore'],
            'github': ['.github', 'github.yml', 'github.yaml'],
            'gitlab': ['.gitlab-ci.yml', '.gitlab-ci.yaml'],
            'vscode': ['.vscode', 'tasks.json', 'launch.json', 'settings.json']
        }
    
    def _get_file_language(self, file_path: str) -> str:
        """Get programming language for file"""
        ext = Path(file_path).suffix.lower()
        return self.language_mapping.get(ext, 'plaintext')
    
    def _detect_build_system(self, project_path: str) -> str:
        """Detect build system for project"""
        project_path = Path(project_path)
        
        for build_system, indicators in self.build_system_indicators.items():
            for indicator in indicators:
                if (project_path / indicator).exists():
                    return build_system
        
        return 'unknown'
    
    def _calculate_file_hash(self, content: str) -> str:
        """Calculate hash for file content"""
        import hashlib
        return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]
    
    async def get_workspace_info(self, workspace_path: str, user_id: str = None) -> Optional[VSCodeProject]:
        """Get VS Code workspace information"""
        try:
            workspace_path = Path(workspace_path).resolve()
            
            if not workspace_path.exists():
                logger.error(f"Workspace path does not exist: {workspace_path}")
                return None
            
            # Get workspace metadata
            workspace_name = workspace_path.name
            workspace_id = f"{user_id}:{workspace_name}:{workspace_path.as_posix()}" if user_id else f"{workspace_name}:{workspace_path.as_posix()}"
            
            # Detect build system
            build_system = self._detect_build_system(workspace_path)
            
            # Get Git information
            git_info = await self._get_git_info(workspace_path)
            
            # Get workspace settings
            settings = await self._get_workspace_settings(workspace_path)
            
            # Get installed extensions
            extensions = await self._get_workspace_extensions(workspace_path)
            
            # Get project structure
            folders, files = await self._get_project_structure(workspace_path)
            
            # Calculate language statistics
            language_stats = {}
            for file_path in files:
                language = self._get_file_language(file_path)
                language_stats[language] = language_stats.get(language, 0) + 1
            
            # Get last activity timestamp
            last_activity = await self._get_last_activity(workspace_path)
            
            project = VSCodeProject(
                id=workspace_id,
                name=workspace_name,
                path=workspace_path.as_posix(),
                type='workspace',
                files=[],  # Will be populated on demand
                folders=folders,
                settings=settings,
                extensions=extensions,
                git_info=git_info,
                build_system=build_system,
                language_stats=language_stats,
                last_activity=last_activity,
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat(),
                metadata={
                    'user_id': user_id,
                    'vscode_version': await self._get_vscode_version(),
                    'platform': platform.system().lower(),
                    'detected_at': datetime.utcnow().isoformat()
                }
            )
            
            logger.info(f"VS Code workspace info retrieved: {workspace_name}")
            return project
            
        except Exception as e:
            logger.error(f"Error getting VS Code workspace info: {e}")
            return None
    
    async def _get_git_info(self, project_path: Path) -> Dict[str, Any]:
        """Get Git information for project"""
        try:
            if not (project_path / '.git').exists():
                return {}
            
            # Get current branch
            branch_result = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                cwd=project_path,
                capture_output=True,
                text=True
            )
            current_branch = branch_result.stdout.strip() if branch_result.returncode == 0 else 'main'
            
            # Get remote URL
            remote_result = subprocess.run(
                ['git', 'config', '--get', 'remote.origin.url'],
                cwd=project_path,
                capture_output=True,
                text=True
            )
            remote_url = remote_result.stdout.strip() if remote_result.returncode == 0 else ''
            
            # Get commit info
            commit_result = subprocess.run(
                ['git', 'log', '-1', '--format=%H|%s|%ai'],
                cwd=project_path,
                capture_output=True,
                text=True
            )
            
            commit_info = {}
            if commit_result.returncode == 0:
                commit_parts = commit_result.stdout.strip().split('|')
                if len(commit_parts) >= 3:
                    commit_info = {
                        'hash': commit_parts[0],
                        'message': commit_parts[1],
                        'date': commit_parts[2],
                        'branch': current_branch,
                        'remote_url': remote_url
                    }
            
            # Get status
            status_result = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=project_path,
                capture_output=True,
                text=True
            )
            
            modified_files = []
            if status_result.returncode == 0:
                for line in status_result.stdout.strip().split('\n'):
                    if line.strip():
                        status_code = line[:2]
                        file_path = line[3:]
                        modified_files.append({
                            'status': status_code,
                            'file': file_path
                        })
            
            return {
                'enabled': True,
                'branch': current_branch,
                'remote_url': remote_url,
                'latest_commit': commit_info,
                'modified_files': modified_files,
                'checked_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting Git info: {e}")
            return {'enabled': False, 'error': str(e)}
    
    async def _get_workspace_settings(self, workspace_path: Path) -> Dict[str, Any]:
        """Get VS Code workspace settings"""
        try:
            settings = {
                'workspace': {},
                'folder': {},
                'keybindings': [],
                'tasks': [],
                'launch': [],
                'extensions': {}
            }
            
            # Look for .vscode directory
            vscode_dir = workspace_path / '.vscode'
            
            if not vscode_dir.exists():
                return settings
            
            # Get workspace settings
            settings_file = vscode_dir / 'settings.json'
            if settings_file.exists():
                async with aiofiles.open(settings_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    settings['workspace'] = json.loads(content)
            
            # Get folder settings (if multi-root)
            for file in vscode_dir.glob('settings-*.json'):
                folder_name = file.stem.replace('settings-', '')
                async with aiofiles.open(file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    settings['folder'][folder_name] = json.loads(content)
            
            # Get keybindings
            keybindings_file = vscode_dir / 'keybindings.json'
            if keybindings_file.exists():
                async with aiofiles.open(keybindings_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    settings['keybindings'] = json.loads(content)
            
            # Get tasks
            tasks_file = vscode_dir / 'tasks.json'
            if tasks_file.exists():
                async with aiofiles.open(tasks_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    settings['tasks'] = json.loads(content)
            
            # Get launch configurations
            launch_file = vscode_dir / 'launch.json'
            if launch_file.exists():
                async with aiofiles.open(launch_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    settings['launch'] = json.loads(content)
            
            # Get extensions recommendations
            extensions_file = vscode_dir / 'extensions.json'
            if extensions_file.exists():
                async with aiofiles.open(extensions_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    settings['extensions'] = json.loads(content)
            
            return settings
            
        except Exception as e:
            logger.error(f"Error getting workspace settings: {e}")
            return {}
    
    async def _get_workspace_extensions(self, workspace_path: Path) -> List[str]:
        """Get extensions used in workspace"""
        try:
            extensions = []
            
            # Look for .vscode/extensions.json
            vscode_dir = workspace_path / '.vscode'
            extensions_file = vscode_dir / 'extensions.json'
            
            if extensions_file.exists():
                async with aiofiles.open(extensions_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    extensions_data = json.loads(content)
                    
                    # Extract extension IDs from recommendations
                    if 'recommendations' in extensions_data:
                        extensions.extend(extensions_data['recommendations'])
                    
                    # Extract from unwanted recommendations
                    if 'unwantedRecommendations' in extensions_data:
                        extensions.extend(extensions_data['unwantedRecommendations'])
            
            return list(set(extensions))  # Remove duplicates
            
        except Exception as e:
            logger.error(f"Error getting workspace extensions: {e}")
            return []
    
    async def _get_project_structure(self, project_path: Path, max_depth: int = 3) -> tuple[List[str], List[str]]:
        """Get project structure folders and files"""
        try:
            folders = []
            files = []
            
            # Common ignore patterns
            ignore_patterns = {
                'node_modules', '.git', '.vscode', '.idea', 'target', 'build', 'dist',
                '__pycache__', '.pytest_cache', '.coverage', 'coverage.xml',
                '.env', 'env', 'venv', '.venv', 'site-packages',
                '.DS_Store', 'Thumbs.db', 'desktop.ini'
            }
            
            for item in project_path.rglob('*'):
                # Skip if item is ignored
                if any(pattern in str(item) for pattern in ignore_patterns):
                    continue
                
                # Calculate depth
                relative_path = item.relative_to(project_path)
                depth = len(relative_path.parts) - 1
                
                if depth > max_depth:
                    continue
                
                if item.is_dir():
                    folders.append(item.relative_to(project_path).as_posix())
                elif item.is_file():
                    files.append(item.relative_to(project_path).as_posix())
            
            return sorted(folders), sorted(files)
            
        except Exception as e:
            logger.error(f"Error getting project structure: {e}")
            return [], []
    
    async def _get_last_activity(self, project_path: Path) -> str:
        """Get last activity timestamp for project"""
        try:
            latest_timestamp = 0
            
            # Check all files in project
            for item in project_path.rglob('*'):
                if item.is_file():
                    try:
                        timestamp = item.stat().st_mtime
                        if timestamp > latest_timestamp:
                            latest_timestamp = timestamp
                    except:
                        continue
            
            if latest_timestamp > 0:
                return datetime.fromtimestamp(latest_timestamp, timezone.utc).isoformat()
            
            return datetime.utcnow().isoformat()
            
        except Exception as e:
            logger.error(f"Error getting last activity: {e}")
            return datetime.utcnow().isoformat()
    
    async def _get_vscode_version(self) -> str:
        """Get VS Code version"""
        try:
            # Try to get from command line
            result = subprocess.run(['code', '--version'], capture_output=True, text=True)
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if lines:
                    return lines[0]
            
            # Fallback to mock version
            return "1.84.0"
            
        except Exception as e:
            logger.error(f"Error getting VS Code version: {e}")
            return "unknown"
    
    async def get_file_content(self, project_path: str, file_path: str, 
                             encoding: str = 'utf-8', max_size: int = 1024 * 1024) -> Optional[VSCodeFile]:
        """Get file content from VS Code project"""
        try:
            full_path = Path(project_path) / file_path
            
            if not full_path.exists() or not full_path.is_file():
                logger.error(f"File does not exist: {full_path}")
                return None
            
            # Check file size
            file_size = full_path.stat().st_size
            if file_size > max_size:
                logger.warning(f"File too large to read: {full_path} ({file_size} bytes)")
                return None
            
            # Read file content
            async with aiofiles.open(full_path, 'r', encoding=encoding, errors='ignore') as f:
                content = await f.read()
            
            # Get file metadata
            stat = full_path.stat()
            
            file = VSCodeFile(
                path=file_path,
                name=full_path.name,
                extension=full_path.suffix,
                size=file_size,
                created_at=datetime.fromtimestamp(stat.st_ctime, timezone.utc).isoformat(),
                modified_at=datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                content=content,
                content_hash=self._calculate_file_hash(content),
                language=self._get_file_language(file_path),
                encoding=encoding,
                line_count=len(content.splitlines()),
                char_count=len(content),
                metadata={
                    'encoding': encoding,
                    'readable': True,
                    'executable': os.access(full_path, os.X_OK),
                    'detected_at': datetime.utcnow().isoformat()
                }
            )
            
            logger.info(f"VS Code file content retrieved: {file_path}")
            return file
            
        except Exception as e:
            logger.error(f"Error getting file content: {e}")
            return None
    
    async def create_file(self, project_path: str, file_path: str, 
                         content: str, encoding: str = 'utf-8') -> bool:
        """Create file in VS Code project"""
        try:
            full_path = Path(project_path) / file_path
            
            # Create directories if needed
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file
            async with aiofiles.open(full_path, 'w', encoding=encoding) as f:
                await f.write(content)
            
            logger.info(f"VS Code file created: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating file: {e}")
            return False
    
    async def update_file(self, project_path: str, file_path: str, 
                         content: str, encoding: str = 'utf-8') -> bool:
        """Update file in VS Code project"""
        try:
            full_path = Path(project_path) / file_path
            
            if not full_path.exists():
                return await self.create_file(project_path, file_path, content, encoding)
            
            # Write file
            async with aiofiles.open(full_path, 'w', encoding=encoding) as f:
                await f.write(content)
            
            logger.info(f"VS Code file updated: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating file: {e}")
            return False
    
    async def delete_file(self, project_path: str, file_path: str) -> bool:
        """Delete file from VS Code project"""
        try:
            full_path = Path(project_path) / file_path
            
            if full_path.exists():
                full_path.unlink()
                logger.info(f"VS Code file deleted: {file_path}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            return False
    
    async def search_workspace_files(self, workspace_path: str, 
                                  search_query: str, file_pattern: str = None,
                                  case_sensitive: bool = False, 
                                  include_content: bool = False) -> List[Dict[str, Any]]:
        """Search files in VS Code workspace"""
        try:
            workspace_path = Path(workspace_path)
            results = []
            
            # Common ignore patterns
            ignore_patterns = {
                'node_modules', '.git', '.vscode', '.idea', 'target', 'build', 'dist',
                '__pycache__', '.pytest_cache', '.coverage', 'coverage.xml',
                '.DS_Store', 'Thumbs.db', 'desktop.ini', '*.log', '*.tmp'
            }
            
            # Prepare search query
            if not case_sensitive:
                search_query = search_query.lower()
            
            for file_path in workspace_path.rglob('*'):
                # Skip if file is ignored or not a file
                if any(pattern in str(file_path) for pattern in ignore_patterns):
                    continue
                
                if not file_path.is_file():
                    continue
                
                # Check file pattern
                if file_pattern:
                    import fnmatch
                    if not fnmatch.fnmatch(file_path.name, file_pattern):
                        continue
                
                # Check filename match
                filename_match = search_query in file_path.name
                if not case_sensitive:
                    filename_match = search_query.lower() in file_path.name.lower()
                
                content_match = False
                content_preview = ""
                
                if include_content:
                    try:
                        # Read file content for search
                        async with aiofiles.open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = await f.read()
                        
                        if content:
                            if not case_sensitive:
                                content_match = search_query in content.lower()
                            else:
                                content_match = search_query in content
                            
                            # Get preview
                            lines = content.splitlines()
                            for i, line in enumerate(lines):
                                if search_query in (line if case_sensitive else line.lower()):
                                    start = max(0, i - 2)
                                    end = min(len(lines), i + 3)
                                    content_preview = '\n'.join(lines[start:end])
                                    break
                    except:
                        continue
                
                if filename_match or content_match:
                    stat = file_path.stat()
                    results.append({
                        'path': file_path.relative_to(workspace_path).as_posix(),
                        'name': file_path.name,
                        'size': stat.st_size,
                        'modified_at': datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                        'language': self._get_file_language(file_path.as_posix()),
                        'filename_match': filename_match,
                        'content_match': content_match,
                        'content_preview': content_preview
                    })
            
            logger.info(f"VS Code workspace search completed: {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Error searching workspace files: {e}")
            return []
    
    async def get_extension_info(self, extension_id: str) -> Optional[VSCodeExtension]:
        """Get VS Code extension information"""
        try:
            if extension_id in self.extension_cache:
                return self.extension_cache[extension_id]
            
            # Search extension
            payload = {
                "filters": [{
                    "criteria": [{
                        "filterType": 8,
                        "value": extension_id
                    }]
                }],
                "flags": 1022
            }
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    VSCODE_EXTENSIONS_API,
                    json=payload,
                    headers={
                        'Accept': 'application/json;api-version=3.0-preview.1',
                        'Content-Type': 'application/json'
                    }
                )
                response.raise_for_status()
                
                data = response.json()
                
                if data.get('results') and len(data['results']) > 0:
                    extension_data = data['results'][0]['extensions'][0]
                    
                    # Extract extension information
                    publisher = extension_data.get('publisher', {})
                    statistics = extension_data.get('statistics', [])
                    download_count = 0
                    rating = 0.0
                    
                    for stat in statistics:
                        if stat.get('statisticName') == 'download':
                            download_count = stat.get('value', 0)
                        elif stat.get('statisticName') == 'averagerating':
                            rating = stat.get('value', 0.0)
                    
                    extension = VSCodeExtension(
                        id=extension_id,
                        name=extension_data.get('displayName', extension_id),
                        publisher={
                            'name': publisher.get('displayName', ''),
                            'id': publisher.get('publisherId', ''),
                            'url': publisher.get('domain', '')
                        },
                        description=extension_data.get('description', ''),
                        version=extension_data.get('versions', [{}])[0].get('version', ''),
                        category=extension_data.get('categories', ['Other'])[0],
                        tags=extension_data.get('tags', []),
                        release_date=extension_data.get('releaseDate', ''),
                        last_updated=extension_data.get('lastUpdated', ''),
                        download_count=download_count,
                        rating=rating,
                        is_pre_release=extension_data.get('flags', {}).get('isPreReleaseVersion', False),
                        dependencies=extension_data.get('dependencies', []),
                        contributes=extension_data.get('contributes', {}),
                        metadata={
                            'extension_id': extension_id,
                            'short_name': extension_data.get('shortName', ''),
                            'flags': extension_data.get('flags', {}),
                            'retrieved_at': datetime.utcnow().isoformat()
                        }
                    )
                    
                    # Cache extension info
                    self.extension_cache[extension_id] = extension
                    
                    logger.info(f"VS Code extension info retrieved: {extension_id}")
                    return extension
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting extension info: {e}")
            return None
    
    async def search_extensions(self, query: str, category: str = None, 
                             page_size: int = 50, page_number: int = 1) -> List[Dict[str, Any]]:
        """Search VS Code extensions"""
        try:
            payload = {
                "filters": [{
                    "criteria": [{
                        "filterType": 7,
                        "value": query
                    }]
                }],
                "flags": 1022,
                "pageSize": page_size,
                "pageNumber": page_number
            }
            
            if category:
                payload["filters"][0]["criteria"].append({
                    "filterType": 12,
                    "value": category
                })
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    VSCODE_EXTENSIONS_API,
                    json=payload,
                    headers={
                        'Accept': 'application/json;api-version=3.0-preview.1',
                        'Content-Type': 'application/json'
                    }
                )
                response.raise_for_status()
                
                data = response.json()
                
                extensions = []
                if data.get('results') and len(data['results']) > 0:
                    for extension_data in data['results'][0]['extensions']:
                        publisher = extension_data.get('publisher', {})
                        statistics = extension_data.get('statistics', [])
                        download_count = 0
                        rating = 0.0
                        
                        for stat in statistics:
                            if stat.get('statisticName') == 'download':
                                download_count = stat.get('value', 0)
                            elif stat.get('statisticName') == 'averagerating':
                                rating = stat.get('value', 0.0)
                        
                        extension_info = {
                            'id': extension_data.get('extensionId', ''),
                            'name': extension_data.get('displayName', ''),
                            'publisher': publisher.get('displayName', ''),
                            'description': extension_data.get('description', ''),
                            'version': extension_data.get('versions', [{}])[0].get('version', ''),
                            'category': extension_data.get('categories', ['Other'])[0],
                            'tags': extension_data.get('tags', []),
                            'download_count': download_count,
                            'rating': rating,
                            'is_pre_release': extension_data.get('flags', {}).get('isPreReleaseVersion', False),
                            'last_updated': extension_data.get('lastUpdated', ''),
                            'release_date': extension_data.get('releaseDate', ''),
                            'short_name': extension_data.get('shortName', ''),
                            'url': f"https://marketplace.visualstudio.com/items?itemName={extension_data.get('extensionId', '')}"
                        }
                        
                        extensions.append(extension_info)
                
                logger.info(f"VS Code extension search completed: {len(extensions)} results")
                return extensions
            
        except Exception as e:
            logger.error(f"Error searching extensions: {e}")
            return []
    
    async def get_recommended_extensions(self, project_path: str, language: str = None) -> List[Dict[str, Any]]:
        """Get recommended extensions for project"""
        try:
            recommendations = []
            
            # Analyze project for recommendations
            project_path = Path(project_path)
            
            # Check for specific file types and frameworks
            if language:
                language_recs = {
                    'python': [
                        {'id': 'ms-python.python', 'name': 'Python', 'category': 'Programming Languages'},
                        {'id': 'ms-python.pylint', 'name': 'Pylint', 'category': 'Linters'},
                        {'id': 'ms-python.black-formatter', 'name': 'Black Formatter', 'category': 'Formatters'},
                        {'id': 'ms-toolsai.jupyter', 'name': 'Jupyter', 'category': 'Notebooks'}
                    ],
                    'javascript': [
                        {'id': 'ms-vscode.vscode-typescript-next', 'name': 'TypeScript', 'category': 'Programming Languages'},
                        {'id': 'esbenp.prettier-vscode', 'name': 'Prettier', 'category': 'Formatters'},
                        {'id': 'dbaeumer.vscode-eslint', 'name': 'ESLint', 'category': 'Linters'}
                    ],
                    'typescript': [
                        {'id': 'ms-vscode.vscode-typescript-next', 'name': 'TypeScript', 'category': 'Programming Languages'},
                        {'id': 'esbenp.prettier-vscode', 'name': 'Prettier', 'category': 'Formatters'},
                        {'id': 'ms-vscode.vscode-typescript-next', 'name': 'TypeScript', 'category': 'Programming Languages'}
                    ],
                    'java': [
                        {'id': 'redhat.java', 'name': 'Extension Pack for Java', 'category': 'Programming Languages'},
                        {'id': 'vscjava.vscode-java-pack', 'name': 'Java Extension Pack', 'category': 'Programming Languages'}
                    ],
                    'go': [
                        {'id': 'golang.go', 'name': 'Go', 'category': 'Programming Languages'}
                    ],
                    'rust': [
                        {'id': 'rust-lang.rust-analyzer', 'name': 'Rust Analyzer', 'category': 'Programming Languages'}
                    ],
                    'docker': [
                        {'id': 'ms-azuretools.vscode-docker', 'name': 'Docker', 'category': 'Other'},
                        {'id': 'ms-vscode-remote.remote-containers', 'name': 'Dev Containers', 'category': 'Other'}
                    ]
                }
                
                if language in language_recs:
                    recommendations.extend(language_recs[language])
            
            # Check for framework-specific files
            if (project_path / 'package.json').exists():
                recommendations.extend([
                    {'id': 'ms-vscode.vscode-json', 'name': 'JSON', 'category': 'Programming Languages'},
                    {'id': 'bradlc.vscode-tailwindcss', 'name': 'Tailwind CSS', 'category': 'Other'}
                ])
            
            if (project_path / 'Cargo.toml').exists():
                recommendations.extend([
                    {'id': 'rust-lang.rust-analyzer', 'name': 'Rust Analyzer', 'category': 'Programming Languages'}
                ])
            
            if (project_path / 'requirements.txt').exists() or (project_path / 'pyproject.toml').exists():
                recommendations.extend([
                    {'id': 'ms-python.python', 'name': 'Python', 'category': 'Programming Languages'},
                    {'id': 'ms-python.flake8', 'name': 'Flake8', 'category': 'Linters'}
                ])
            
            # Add general recommendations
            general_recommendations = [
                {'id': 'ms-vscode.vscode-git-graph', 'name': 'Git Graph', 'category': 'SCM Providers'},
                {'id': 'eamodio.gitlens', 'name': 'GitLens', 'category': 'SCM Providers'},
                {'id': 'ms-vscode.hexeditor', 'name': 'Hex Editor', 'category': 'Other'},
                {'id': 'ms-vscode.vscode-markdown', 'name': 'Markdown All in One', 'category': 'Programming Languages'}
            ]
            
            recommendations.extend(general_recommendations)
            
            # Remove duplicates
            seen = set()
            unique_recommendations = []
            for rec in recommendations:
                if rec['id'] not in seen:
                    seen.add(rec['id'])
                    unique_recommendations.append(rec)
            
            logger.info(f"VS Code extension recommendations: {len(unique_recommendations)} suggestions")
            return unique_recommendations[:20]  # Limit to 20 recommendations
            
        except Exception as e:
            logger.error(f"Error getting recommended extensions: {e}")
            return []
    
    async def get_workspace_languages(self, workspace_path: str) -> Dict[str, Any]:
        """Get language statistics for workspace"""
        try:
            workspace_path = Path(workspace_path)
            language_stats = {}
            total_files = 0
            total_size = 0
            
            # Common ignore patterns
            ignore_patterns = {
                'node_modules', '.git', '.vscode', '.idea', 'target', 'build', 'dist',
                '__pycache__', '.pytest_cache', '.coverage', 'coverage.xml',
                '.DS_Store', 'Thumbs.db', 'desktop.ini'
            }
            
            for file_path in workspace_path.rglob('*'):
                # Skip if file is ignored or not a file
                if any(pattern in str(file_path) for pattern in ignore_patterns):
                    continue
                
                if not file_path.is_file():
                    continue
                
                # Get language
                language = self._get_file_language(file_path.as_posix())
                
                # Update statistics
                if language not in language_stats:
                    language_stats[language] = {
                        'count': 0,
                        'size': 0,
                        'extensions': set()
                    }
                
                try:
                    file_size = file_path.stat().st_size
                    language_stats[language]['count'] += 1
                    language_stats[language]['size'] += file_size
                    language_stats[language]['extensions'].add(file_path.suffix.lower())
                    total_files += 1
                    total_size += file_size
                except:
                    continue
            
            # Convert to final format
            result = {
                'languages': {},
                'total_files': total_files,
                'total_size': total_size,
                'dominant_language': None
            }
            
            for language, stats in language_stats.items():
                result['languages'][language] = {
                    'count': stats['count'],
                    'size': stats['size'],
                    'size_mb': round(stats['size'] / (1024 * 1024), 2),
                    'percentage': round((stats['count'] / total_files) * 100, 2) if total_files > 0 else 0,
                    'extensions': list(stats['extensions'])
                }
                
                # Track dominant language
                if (not result['dominant_language'] or 
                    stats['count'] > result['languages'][result['dominant_language']]['count']):
                    result['dominant_language'] = language
            
            logger.info(f"VS Code workspace languages analyzed: {len(result['languages'])} languages")
            return result
            
        except Exception as e:
            logger.error(f"Error getting workspace languages: {e}")
            return {'languages': {}, 'total_files': 0, 'total_size': 0}
    
    async def log_development_activity(self, user_id: str, project_id: str, 
                                    action_type: str, file_path: str, 
                                    content: str = None, session_id: str = None,
                                    metadata: Dict[str, Any] = None) -> bool:
        """Log development activity"""
        try:
            activity = VSCodeActivity(
                id=f"{user_id}:{project_id}:{action_type}:{file_path}:{datetime.utcnow().timestamp()}",
                user_id=user_id,
                project_id=project_id,
                action_type=action_type,
                file_path=file_path,
                content=content or '',
                timestamp=datetime.utcnow().isoformat(),
                language=self._get_file_language(file_path),
                session_id=session_id or f"session_{datetime.utcnow().timestamp()}",
                metadata=metadata or {}
            )
            
            # In a real implementation, this would be stored in a database
            # For now, we'll just log it
            logger.info(f"VS Code development activity logged: {action_type} on {file_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error logging development activity: {e}")
            return False
    
    async def get_service_info(self) -> Dict[str, Any]:
        """Get service information"""
        return {
            "name": "Enhanced VS Code Service",
            "version": "1.0.0",
            "description": "Complete VS Code development environment integration",
            "supported_languages": list(self.language_mapping.values()),
            "build_systems": list(self.build_system_indicators.keys()),
            "capabilities": [
                "workspace_management",
                "file_operations",
                "extension_management",
                "git_integration",
                "language_detection",
                "search_functionality",
                "activity_logging",
                "project_analysis"
            ],
            "api_endpoints": [
                "/api/vscode/enhanced/workspace/info",
                "/api/vscode/enhanced/workspace/files",
                "/api/vscode/enhanced/workspace/search",
                "/api/vscode/enhanced/workspace/languages",
                "/api/vscode/enhanced/extensions/search",
                "/api/vscode/enhanced/extensions/info",
                "/api/vscode/enhanced/extensions/recommendations",
                "/api/vscode/enhanced/activity/log",
                "/api/vscode/enhanced/health"
            ],
            "platform": platform.system().lower(),
            "python_version": platform.python_version(),
            "initialized_at": datetime.utcnow().isoformat()
        }

# Create singleton instance
vscode_enhanced_service = VSCodeEnhancedService()