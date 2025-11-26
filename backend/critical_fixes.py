"""
Critical Fixes: API Placeholder Data Detection
Scans codebase and database for placeholder data artifacts
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

PLACEHOLDER_INDICATORS = [
    "Lorem Ipsum",
    "John Doe",
    "Jane Doe",
    "123 Main St",
    "example.com",
    "test@test.com",
    "placeholder",
    "mock_data",
    "TODO: Replace",
    "FIXME: Hardcoded"
]

class PlaceholderDetector:
    """Detects placeholder data in API responses and database"""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.findings: List[Dict[str, Any]] = []
        
    def scan_codebase(self):
        """Scan codebase for hardcoded placeholder strings"""
        logger.info("Scanning codebase for placeholder strings...")
        
        extensions = ['.py', '.js', '.ts', '.tsx', '.json']
        skip_dirs = ['node_modules', '.git', '__pycache__', 'venv', 'dist', 'build']
        
        for path in self.project_root.rglob('*'):
            if path.is_dir():
                if any(skip_dir in path.parts for skip_dir in skip_dirs):
                    continue
            
            if path.suffix in extensions and path.is_file():
                try:
                    content = path.read_text(encoding='utf-8', errors='ignore')
                    for indicator in PLACEHOLDER_INDICATORS:
                        if indicator in content:
                            # Filter out this file (the detector itself)
                            if path.name == "critical_fixes.py":
                                continue
                                
                            self.findings.append({
                                "type": "code_placeholder",
                                "file": str(path.relative_to(self.project_root)),
                                "indicator": indicator,
                                "line_count": content.count(indicator)
                            })
                except Exception as e:
                    logger.warning(f"Could not read {path}: {e}")

    def scan_database(self):
        """Scan database for placeholder records (Mock implementation)"""
        logger.info("Scanning database for placeholder records...")
        # In a real scenario, this would connect to DB and query tables
        # For now, we'll check JSON data files which act as our DB
        
        data_dir = self.project_root / "backend" / "data"
        if data_dir.exists():
            for json_file in data_dir.glob("*.json"):
                try:
                    content = json_file.read_text(encoding='utf-8')
                    data = json.loads(content)
                    self._recursive_scan(data, str(json_file.relative_to(self.project_root)))
                except Exception as e:
                    logger.warning(f"Could not scan {json_file}: {e}")

    def _recursive_scan(self, data: Any, source: str):
        """Recursively scan JSON data"""
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, str):
                    for indicator in PLACEHOLDER_INDICATORS:
                        if indicator in v:
                            self.findings.append({
                                "type": "data_placeholder",
                                "source": source,
                                "key": k,
                                "value": v[:50] + "...",
                                "indicator": indicator
                            })
                else:
                    self._recursive_scan(v, source)
        elif isinstance(data, list):
            for item in data:
                self._recursive_scan(item, source)

    def generate_report(self):
        """Generate detection report"""
        report = {
            "timestamp": "2025-11-24T12:00:00",
            "total_findings": len(self.findings),
            "findings": self.findings
        }
        
        output_path = self.project_root / "backend" / "placeholder_report.json"
        output_path.write_text(json.dumps(report, indent=2))
        logger.info(f"Report saved to {output_path}")
        
        # Print summary
        print("\n" + "="*50)
        print("PLACEHOLDER DETECTION SUMMARY")
        print("="*50)
        print(f"Total Findings: {len(self.findings)}")
        
        by_type = {}
        for f in self.findings:
            by_type[f["type"]] = by_type.get(f["type"], 0) + 1
            
        for t, count in by_type.items():
            print(f"{t}: {count}")
            
        print("\nTop Indicators:")
        indicators = {}
        for f in self.findings:
            indicators[f["indicator"]] = indicators.get(f["indicator"], 0) + 1
            
        for ind, count in sorted(indicators.items(), key=lambda x: -x[1])[:5]:
            print(f"  {ind}: {count}")

if __name__ == "__main__":
    detector = PlaceholderDetector(os.getcwd())
    detector.scan_codebase()
    detector.scan_database()
    detector.generate_report()
