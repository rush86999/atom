import re
import yaml
from pathlib import Path
from typing import List, Dict, Pattern, Optional
from atom_security.core.models import SecurityRule, Severity

class RuleLoader:
    """
    Loads and compiles security rules from YAML definitions.
    """
    
    def __init__(self, rules_path: Optional[Path] = None):
        if rules_path is None:
            # Default to bundled rules
            self.rules_path = Path(__file__).parents[1] / "data" / "rules" / "signatures.yaml"
        else:
            self.rules_path = rules_path
            
    def load_rules(self) -> List[SecurityRule]:
        """Load rules from YAML file."""
        if not self.rules_path.exists():
            raise FileNotFoundError(f"Rules file not found at {self.rules_path}")
            
        with open(self.rules_path, "r") as f:
            data = yaml.safe_load(f)
            
        rules = []
        for rule_data in data:
            if not rule_data:
                continue
            try:
                # Convert string severity to enum if needed
                if isinstance(rule_data.get("severity"), str):
                    rule_data["severity"] = Severity(rule_data["severity"])
                
                rules.append(SecurityRule(**rule_data))
            except Exception as e:
                print(f"Error loading rule {rule_data.get('id')}: {e}")
                
        return rules

class PatternMatcher:
    """
    Compiled regex matcher for security rules.
    """
    
    def __init__(self, rules: List[SecurityRule]):
        self.rules = rules
        self.compiled_patterns: Dict[str, List[Pattern]] = {}
        self.compiled_excludes: Dict[str, List[Pattern]] = {}
        self._compile_patterns()
        
    def _compile_patterns(self):
        """Compile all regex patterns for performance."""
        for rule in self.rules:
            # Compile inclusion patterns
            patterns = []
            for p in rule.patterns:
                try:
                    patterns.append(re.compile(p, re.IGNORECASE | re.MULTILINE))
                except re.error as e:
                    print(f"Invalid regex in rule {rule.id}: {p} -> {e}")
            self.compiled_patterns[rule.id] = patterns
            
            # Compile exclusion patterns
            excludes = []
            for p in rule.exclude_patterns:
                try:
                    excludes.append(re.compile(p, re.IGNORECASE | re.MULTILINE))
                except re.error as e:
                    print(f"Invalid exclude regex in rule {rule.id}: {p} -> {e}")
            self.compiled_excludes[rule.id] = excludes
            
    def match(self, content: str, rule: SecurityRule) -> List[tuple[int, str]]:
        """
        Check content against a rule.
        Returns list of (line_number, matched_text) tuples.
        """
        matches = []
        
        # Quick check if rule applies to ANY content
        # For line-by-line scanning, we might optimize this further
        
        lines = content.splitlines()
        
        for line_idx, line in enumerate(lines, 1):
            is_match = False
            matched_text = ""
            
            # Check all patterns
            for pattern in self.compiled_patterns.get(rule.id, []):
                m = pattern.search(line)
                if m:
                    is_match = True
                    matched_text = m.group(0)
                    break
            
            if is_match:
                # Check exclusions
                is_excluded = False
                for exclude in self.compiled_excludes.get(rule.id, []):
                    if exclude.search(line):
                        is_excluded = True
                        break
                
                if not is_excluded:
                    matches.append((line_idx, line.strip()))
                    
        return matches
