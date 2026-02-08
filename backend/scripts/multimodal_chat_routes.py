from datetime import datetime
import logging
import os
from typing import Any, Dict, List, Optional
import uuid
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Configure logging
logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter()

# Configuration
UPLOAD_DIR = "uploads"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_FILE_TYPES = {
    "image": ["jpg", "jpeg", "png", "gif", "bmp", "webp"],
    "document": ["pdf", "doc", "docx", "txt", "md"],
    "spreadsheet": ["xls", "xlsx", "csv"],
    "presentation": ["ppt", "pptx"],
    "audio": ["mp3", "wav", "m4a", "ogg"],
    "video": ["mp4", "mov", "avi", "mkv"],
}


# Pydantic models
class FileUploadResponse(BaseModel):
    file_id: str = Field(..., description="Unique file identifier")
    filename: str = Field(..., description="Original filename")
    file_type: str = Field(..., description="File type category")
    file_size: int = Field(..., description="File size in bytes")
    upload_url: Optional[str] = Field(None, description="URL to access the file")
    processing_status: str = Field(..., description="Current processing status")
    analysis_result: Optional[Dict[str, Any]] = Field(
        None, description="File analysis results"
    )


class MultiModalMessage(BaseModel):
    message: str = Field(..., description="Text message content")
    user_id: str = Field(..., description="User identifier")
    file_ids: List[str] = Field(
        default_factory=list, description="List of attached file IDs"
    )
    context_id: Optional[str] = Field(
        None, description="Conversation context identifier"
    )
    message_type: str = Field("multimodal", description="Type of message")


class FileAnalysisResult(BaseModel):
    file_id: str = Field(..., description="File identifier")
    analysis_type: str = Field(..., description="Type of analysis performed")
    results: Dict[str, Any] = Field(..., description="Analysis results")
    confidence: Optional[float] = Field(None, description="Analysis confidence score")


# Ensure upload directory exists
def ensure_upload_dir():
    """Create upload directory if it doesn't exist"""
    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR)
        logger.info(f"Created upload directory: {UPLOAD_DIR}")


def get_file_extension(filename: str) -> str:
    """Extract file extension from filename"""
    return filename.lower().split(".")[-1] if "." in filename else ""


def is_file_type_allowed(filename: str) -> tuple[bool, str]:
    """Check if file type is allowed and return file category"""
    extension = get_file_extension(filename)

    for category, extensions in ALLOWED_FILE_TYPES.items():
        if extension in extensions:
            return True, category

    return False, ""


def scan_file_for_threats(file_path: str) -> bool:
    """
    Basic file security scanning
    In production, integrate with proper antivirus/security scanning service
    """
    try:
        # Check file size
        file_size = os.path.getsize(file_path)
        if file_size > MAX_FILE_SIZE:
            return False

        # Basic file header validation
        with open(file_path, "rb") as f:
            header = f.read(100)  # Read first 100 bytes

            # Check for common malicious file signatures
            malicious_signatures = [
                b"\x4d\x5a",  # EXE files
                b"\x7f\x45\x4c\x46",  # ELF files
                b"\xca\xfe\xba\xbe",  # Java class files
            ]

            for signature in malicious_signatures:
                if header.startswith(signature):
                    return False

        return True
    except Exception as e:
        logger.error(f"Error scanning file {file_path}: {e}")
        return False


def analyze_image_file(file_path: str) -> Dict[str, Any]:
    """Analyze image file and extract information"""
    try:
        # In production, integrate with image analysis service (OpenCV, PIL, etc.)
        from PIL import ExifTags, Image
        import PIL.Image

        with Image.open(file_path) as img:
            width, height = img.size
            format_type = img.format
            mode = img.mode

            # Extract basic metadata
            metadata = {
                "dimensions": f"{width}x{height}",
                "format": format_type,
                "color_mode": mode,
                "file_size": os.path.getsize(file_path),
            }

            # Try to extract EXIF data
            try:
                exif_data = img._getexif()
                if exif_data:
                    exif = {}
                    for tag, value in exif_data.items():
                        decoded = ExifTags.TAGS.get(tag, tag)
                        exif[decoded] = value
                    metadata["exif"] = exif
            except Exception:
                pass

            return {
                "analysis_type": "image",
                "metadata": metadata,
                "description": f"Image: {width}x{height} {format_type}",
                "confidence": 0.95,
            }
    except ImportError:
        # Fallback if PIL is not available
        return {
            "analysis_type": "image",
            "metadata": {"file_size": os.path.getsize(file_path)},
            "description": "Image file (detailed analysis requires PIL)",
            "confidence": 0.7,
        }
    except Exception as e:
        logger.error(f"Error analyzing image {file_path}: {e}")
        return {
            "analysis_type": "image",
            "metadata": {"file_size": os.path.getsize(file_path)},
            "description": "Image file (analysis failed)",
            "confidence": 0.5,
        }


def analyze_document_file(file_path: str, file_extension: str) -> Dict[str, Any]:
    """Analyze document file and extract information"""
    try:
        file_size = os.path.getsize(file_path)

        # Basic document analysis
        if file_extension == "pdf":
            return {
                "analysis_type": "document",
                "document_type": "PDF",
                "file_size": file_size,
                "page_count": "Unknown",  # Would require PDF parsing library
                "description": "PDF document",
                "confidence": 0.8,
            }
        elif file_extension in ["doc", "docx"]:
            return {
                "analysis_type": "document",
                "document_type": "Word Document",
                "file_size": file_size,
                "description": "Microsoft Word document",
                "confidence": 0.8,
            }
        elif file_extension == "txt":
            # Basic text file analysis
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read(1000)  # Read first 1000 characters
                line_count = len(content.split("\n"))
                word_count = len(content.split())

            return {
                "analysis_type": "document",
                "document_type": "Text File",
                "file_size": file_size,
                "line_count": line_count,
                "word_count": word_count,
                "preview": content[:200] + "..." if len(content) > 200 else content,
                "description": f"Text document ({word_count} words)",
                "confidence": 0.9,
            }
        else:
            return {
                "analysis_type": "document",
                "document_type": "Document",
                "file_size": file_size,
                "description": f"{file_extension.upper()} document",
                "confidence": 0.7,
            }
    except Exception as e:
        logger.error(f"Error analyzing document {file_path}: {e}")
        return {
            "analysis_type": "document",
            "document_type": "Unknown",
            "file_size": os.path.getsize(file_path),
            "description": "Document file (analysis failed)",
            "confidence": 0.5,
        }


def analyze_audio_file(file_path: str) -> Dict[str, Any]:
    """Analyze audio file and extract information"""
    try:
        file_size = os.path.getsize(file_path)

        # In production, integrate with audio processing library
        return {
            "analysis_type": "audio",
            "file_size": file_size,
            "duration": "Unknown",  # Would require audio processing library
            "sample_rate": "Unknown",
            "description": "Audio file",
            "confidence": 0.7,
        }
    except Exception as e:
        logger.error(f"Error analyzing audio {file_path}: {e}")
        return {
            "analysis_type": "audio",
            "file_size": os.path.getsize(file_path),
            "description": "Audio file (analysis failed)",
            "confidence": 0.5,
        }


def analyze_file(file_path: str, filename: str, file_category: str) -> Dict[str, Any]:
    """Analyze file based on its category"""
    extension = get_file_extension(filename)

    if file_category == "image":
        return analyze_image_file(file_path)
    elif file_category in ["document", "spreadsheet", "presentation"]:
        return analyze_document_file(file_path, extension)
    elif file_category == "audio":
        return analyze_audio_file(file_path)
    elif file_category == "video":
        return {
            "analysis_type": "video",
            "file_size": os.path.getsize(file_path),
            "description": "Video file",
            "confidence": 0.7,
        }
    else:
        return {
            "analysis_type": "unknown",
            "file_size": os.path.getsize(file_path),
            "description": f"File type: {file_category}",
            "confidence": 0.5,
        }


# File storage for tracking uploaded files (in production, use database)
file_registry = {}


@router.post("/api/v1/chat/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    context_id: Optional[str] = Form(None),
):
    """
    Upload a file for multi-modal chat
    """
    try:
        ensure_upload_dir()

        # Validate file type
        is_allowed, file_category = is_file_type_allowed(file.filename)
        if not is_allowed:
            raise HTTPException(
                status_code=400,
                detail=f"File type not allowed. Supported types: {ALLOWED_FILE_TYPES}",
            )

        # Generate unique file ID
        file_id = str(uuid.uuid4())
        safe_filename = f"{file_id}_{file.filename}"
        file_path = os.path.join(UPLOAD_DIR, safe_filename)

        # Read file content and save
        content = await file.read()

        # Check file size
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024 * 1024)}MB",
            )

        # Save file
        with open(file_path, "wb") as f:
            f.write(content)

        # Security scanning
        if not scan_file_for_threats(file_path):
            os.remove(file_path)  # Clean up potentially malicious file
            raise HTTPException(status_code=400, detail="File failed security scan")

        # Analyze file
        analysis_result = analyze_file(file_path, file.filename, file_category)

        # Store file metadata
        file_metadata = {
            "file_id": file_id,
            "filename": file.filename,
            "file_path": file_path,
            "file_size": len(content),
            "file_category": file_category,
            "user_id": user_id,
            "context_id": context_id,
            "uploaded_at": datetime.now().isoformat(),
            "analysis_result": analysis_result,
            "processing_status": "completed",
        }

        file_registry[file_id] = file_metadata

        logger.info(f"File uploaded successfully: {file.filename} (ID: {file_id})")

        return FileUploadResponse(
            file_id=file_id,
            filename=file.filename,
            file_type=file_category,
            file_size=len(content),
            upload_url=f"/api/v1/chat/files/{file_id}",
            processing_status="completed",
            analysis_result=analysis_result,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(status_code=500, detail="File upload failed")


@router.post("/api/v1/chat/multimodal", response_model=Dict[str, Any])
async def send_multimodal_message(message: MultiModalMessage):
    """
    Send a multi-modal chat message with file attachments
    """
    try:
        # Validate file attachments
        valid_files = []
        invalid_files = []

        for file_id in message.file_ids:
            if file_id in file_registry:
                file_metadata = file_registry[file_id]

                # Check if user owns the file
                if file_metadata["user_id"] != message.user_id:
                    invalid_files.append(file_id)
                    continue

                valid_files.append(
                    {
                        "file_id": file_id,
                        "filename": file_metadata["filename"],
                        "file_type": file_metadata["file_category"],
                        "analysis": file_metadata["analysis_result"],
                    }
                )
            else:
                invalid_files.append(file_id)

        # Process the multi-modal message
        response_data = {
            "response": f"Received your message with {len(valid_files)} file(s)",
            "context_id": message.context_id
            or f"ctx_{message.user_id}_{datetime.now().isoformat()}",
            "user_id": message.user_id,
            "attachments": valid_files,
            "invalid_files": invalid_files,
            "message_analysis": {
                "text_length": len(message.message),
                "file_count": len(valid_files),
                "has_attachments": len(valid_files) > 0,
            },
            "timestamp": datetime.now().isoformat(),
        }

        # Add file-specific responses
        if valid_files:
            file_descriptions = []
            for file_info in valid_files:
                analysis = file_info["analysis"]
                description = analysis.get("description", "File attachment")
                file_descriptions.append(f"- {file_info['filename']}: {description}")

            response_data["file_summary"] = "\n".join(file_descriptions)

        logger.info(
            f"Multi-modal message processed for user {message.user_id} with {len(valid_files)} files"
        )

        return response_data

    except Exception as e:
        logger.error(f"Error processing multi-modal message: {e}")
        raise HTTPException(status_code=500, detail="Message processing failed")


@router.get("/api/v1/chat/files/{file_id}")
async def get_file(file_id: str):
    """
    Retrieve an uploaded file
    """
    if file_id not in file_registry:
        raise HTTPException(status_code=404, detail="File not found")

    file_metadata = file_registry[file_id]
    file_path = file_metadata["file_path"]

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on server")

    # In production, serve file with proper content-type headers
    return JSONResponse(
        {
            "file_id": file_id,
            "filename": file_metadata["filename"],
            "file_size": file_metadata["file_size"],
            "file_type": file_metadata["file_category"],
            "uploaded_at": file_metadata["uploaded_at"],
            "analysis_result": file_metadata["analysis_result"],
        }
    )


@router.get("/api/v1/chat/files/{file_id}/download")
async def download_file(file_id: str):
    """
    Download an uploaded file
    """
    if file_id not in file_registry:
        raise HTTPException(status_code=404, detail="File not found")

    file_metadata = file_registry[file_id]
    file_path = file_metadata["file_path"]

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on server")

    # In production, implement proper file serving with content-disposition
    from fastapi.responses import FileResponse

    return FileResponse(
        path=file_path,
        filename=file_metadata["filename"],
        media_type="application/octet-stream",
    )


@router.delete("/api/v1/chat/files/{file_id}")
async def delete_file(file_id: str, user_id: str):
    """
    Delete an uploaded file
    """
    if file_id not in file_registry:
        raise HTTPException(status_code=404, detail="File not found")

    file_metadata = file_registry[file_id]

    # Check ownership
    if file_metadata["user_id"] != user_id:
        raise HTTPException(
            status_code=403, detail="Not authorized to delete this file"
        )

    file_path = file_metadata["file_path"]

    try:
        # Delete physical file
        if os.path.exists(file_path):
            os.remove(file_path)

        # Remove from registry
        del file_registry[file_id]

        logger.info(f"File deleted: {file_id}")

        return {"success": True, "message": "File deleted successfully"}

    except Exception as e:
        logger.error(f"Error deleting file {file_id}: {e}")
        raise HTTPException(status_code=500, detail="File deletion failed")


@router.get("/api/v1/chat/files")
async def list_user_files(user_id: str, limit: int = 50, offset: int = 0):
    """
    List files uploaded by a user
    """
    user_files = []

    for file_id, metadata in file_registry.items():
        if metadata["user_id"] == user_id:
            user_files.append(
                {
                    "file_id": file_id,
                    "filename": metadata["filename"],
                    "file_size": metadata["file_size"],
                    "file_type": metadata["file_category"],
                    "uploaded_at": metadata["uploaded_at"],
                    "processing_status": metadata["processing_status"],
                }
            )

    # Apply pagination
    start_idx = offset
    end_idx = offset + limit
    paginated_files = user_files[start_idx:end_idx]

    return {
        "files": paginated_files,
        "total_count": len(user_files),
        "offset": offset,
        "limit": limit,
    }
