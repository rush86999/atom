import os
import mimetypes
from pathlib import Path
from typing import List, Optional
from atom_security.core.models import Finding, ScanResult, Severity, SecurityRule
from atom_security.core.patterns import RuleLoader, PatternMatcher

class StaticAnalyzer:
    """
    Analyzes files using regex patterns defined in signatures.yaml.
    """
    
    def __init__(self, rules_path: Optional[Path] = None):
        loader = RuleLoader(rules_path)
        self.rules = loader.load_rules()
        self.matcher = PatternMatcher(self.rules)
        
    def scan_content(self, content: str, file_type: str = 'python') -> List[Finding]:
        """Scan string content for security issues."""
        findings = []
        for rule in self.rules:
            if self._applies_to_file(rule, file_type):
                matches = self.matcher.match(content, rule)
                for line_num, line_content in matches:
                    finding = Finding(
                        rule_id=rule.id,
                        category=rule.category,
                        severity=rule.severity,
                        line_number=line_num,
                        line_content=line_content,
                        description=rule.description,
                        remediation=rule.remediation
                    )
                    findings.append(finding)
        return findings
        
    def scan_file(self, file_path: Path) -> List[Finding]:
        """Scan a single file for security issues."""
        findings = []
        
        try:
            # Determine file type
            file_type = self._detect_file_type(file_path)
            if not file_type:
                return []
                
            # Skip large files (>1MB)
            if file_path.stat().st_size > 1_000_000:
                print(f"Skipping large file: {file_path}")
                return []
                
            content = file_path.read_text(errors='ignore')
            
            # Check rules applicable to this file type
            for rule in self.rules:
                if self._applies_to_file(rule, file_type):
                    matches = self.matcher.match(content, rule)
                    
                    for line_num, line_content in matches:
                        finding = Finding(
                            rule_id=rule.id,
                            category=rule.category,
                            severity=rule.severity,
                            file_path=str(file_path),
                            line_number=line_num,
                            line_content=line_content,
                            description=rule.description,
                            remediation=rule.remediation
                        )
                        findings.append(finding)
                        
        except Exception as e:
            print(f"Error scanning {file_path}: {e}")
            
        return findings

    def scan_directory(self, directory: Path) -> ScanResult:
        """Scan a directory recursively."""
        scan_directory = Path(directory)
        all_findings = []
        files_scanned = 0
        
        import time
        start_time = time.time()
        
        # Walk directory
        for root, dirs, files in os.walk(scan_directory):
            # Skip hidden dirs
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            for file in files:
                if file.startswith('.'):
                    continue
                    
                file_path = Path(root) / file
                findings = self.scan_file(file_path)
                all_findings.extend(findings)
                files_scanned += 1
                
        duration = time.time() - start_time
        
        # Calculate summary metrics
        max_severity = Severity.INFO
        is_safe = True
        
        severity_rank = {
            Severity.INFO: 0, 
            Severity.LOW: 1, 
            Severity.MEDIUM: 2, 
            Severity.HIGH: 3, 
            Severity.CRITICAL: 4
        }
        
        for f in all_findings:
            if severity_rank[f.severity] >= severity_rank[Severity.HIGH]:
                is_safe = False
            
            if severity_rank[f.severity] > severity_rank[max_severity]:
                max_severity = f.severity
                
        return ScanResult(
            is_safe=is_safe,
            max_severity=max_severity,
            findings=all_findings,
            scan_duration=duration,
            files_scanned=files_scanned,
            analyzers_run=["StaticAnalyzer"]
        )

    def _detect_file_type(self, file_path: Path) -> Optional[str]:
        """Map file extension to rule file_type."""
        ext = file_path.suffix.lower()
        if ext in ['.py', '.pyw']:
            return 'python'
        elif ext in ['.sh', '.bash', '.zsh']:
            return 'bash'
        elif ext in ['.md', '.markdown', '.txt']:
            return 'markdown'
        elif ext in ['.yml', '.yaml']:
            return 'manifest' # Or yaml
        # Binary check could be added here
        return None

    def _applies_to_file(self, rule: SecurityRule, file_type: str) -> bool:
        """Check if rule applies to file type."""
        return file_type in rule.file_types or 'all' in rule.file_types
