import enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from pathlib import Path

class Severity(str, enum.Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"

class Finding(BaseModel):
    """
    Represents a single security finding detected by an analyzer.
    """
    rule_id: str
    category: str
    severity: Severity
    file_path: str
    line_number: int
    line_content: Optional[str] = None
    description: str
    remediation: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ScanResult(BaseModel):
    """
    Results from scanning a single skill or directory.
    """
    is_safe: bool
    max_severity: Severity
    findings: List[Finding]
    scan_duration: float
    files_scanned: int
    analyzers_run: List[str]

class SecurityRule(BaseModel):
    """
    Definition of a security rule for pattern matching.
    """
    id: str
    category: str
    severity: Severity
    patterns: List[str]
    exclude_patterns: List[str] = Field(default_factory=list)
    file_types: List[str]
    description: str
    remediation: Optional[str] = None
