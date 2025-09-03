from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class MCPBase(ABC):
    """
    Abstract base class for a generic cloud provider connector.
    """

    @abstractmethod
    def list_files(
        self,
        access_token: str,
        folder_id: Optional[str] = None,
        query: Optional[str] = None,
        page_size: int = 100,
        page_token: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Lists files and folders."""
        pass

    @abstractmethod
    def get_file_metadata(
        self,
        access_token: str,
        file_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Retrieves metadata for a specific file."""
        pass

    @abstractmethod
    def download_file(
        self,
        access_token: str,
        file_id: str,
        target_mime_type: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Downloads a file's content."""
        pass
