"""
Crash Deduplicator for Error Signature Hashing

This module provides crash deduplication using SHA256 hashing of error
signatures to group similar crashes and prevent duplicate bug filings.

Features:
- SHA256-based crash deduplication using error signature hashing
- Stack trace extraction from crash logs
- Unique crash identification for bug filing
"""

import hashlib
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class CrashDeduplicator:
    """
    Deduplicate crashes using error signature hashing.

    Groups crashes by SHA256 hash of error signature (stack trace)
    to identify unique crashes for bug filing.

    Example:
        dedup = CrashDeduplicator()
        crashes_by_signature = dedup.deduplicate_crashes(crash_dir)
        unique_crashes = dedup.get_unique_crashes(crashes_by_signature)
    """

    def deduplicate_crashes(self, crash_dir: Path) -> Dict[str, List[Path]]:
        """
        Deduplicate crashes by error signature hash.

        Args:
            crash_dir: Directory containing crash files (*.input and *.log)

        Returns:
            Dict mapping signature_hash to list of crash files
        """
        crashes_by_signature: Dict[str, List[Path]] = {}

        # Iterate over all crash input files
        crash_files = list(crash_dir.glob("*.input"))

        for crash_file in crash_files:
            # Read crash log file
            crash_log_file = crash_file.with_suffix(".log")

            if not crash_log_file.exists():
                # No log file, use filename as signature
                signature_hash = self._generate_signature_hash(crash_file.name)
            else:
                try:
                    # Extract stack trace from log
                    stack_trace = self._extract_stack_trace(crash_log_file)
                    signature_hash = self._generate_signature_hash(stack_trace)
                except Exception as e:
                    # Failed to read log, use filename as fallback
                    print(f"Warning: Failed to extract stack trace from {crash_log_file}: {e}")
                    signature_hash = self._generate_signature_hash(crash_file.name)

            # Group crashes by signature
            if signature_hash not in crashes_by_signature:
                crashes_by_signature[signature_hash] = []

            crashes_by_signature[signature_hash].append(crash_file)

        return crashes_by_signature

    def _extract_stack_trace(self, crash_log_file: Path) -> str:
        """
        Extract Python stack trace from crash log.

        Args:
            crash_log_file: Path to crash log file

        Returns:
            Stack trace string with line numbers
        """
        try:
            with open(crash_log_file, "r", errors="ignore") as f:
                crash_log = f.read()

            # Split into lines
            lines = crash_log.split("\n")

            # Find "Traceback" line (start of stack trace)
            traceback_start = -1
            for i, line in enumerate(lines):
                if "Traceback" in line or "traceback" in line:
                    traceback_start = i
                    break

            if traceback_start == -1:
                # No traceback found, return entire log
                return crash_log[:1000]  # Limit to 1000 chars

            # Extract stack trace until non-indented line (end of traceback)
            stack_trace_lines = [lines[traceback_start]]
            for i in range(traceback_start + 1, len(lines)):
                line = lines[i]

                # Stop at end of traceback (non-indented line or error message)
                if line and not line.startswith(" ") and not line.startswith("\t") and ":" in line:
                    # This is likely the error message line, include it
                    stack_trace_lines.append(line)
                    break

                # Stop if we hit an empty line after indented lines
                if not line and len(stack_trace_lines) > 1:
                    break

                stack_trace_lines.append(line)

            stack_trace = "\n".join(stack_trace_lines)

            # Limit stack trace length to prevent hash collisions from very long traces
            return stack_trace[:2000] if len(stack_trace) > 2000 else stack_trace

        except Exception as e:
            # Failed to read log, return hashable representation
            return f"Error reading log: {str(e)}"

    def _generate_signature_hash(self, stack_trace: str) -> str:
        """
        Generate SHA256 hash of error signature.

        Args:
            stack_trace: Stack trace string

        Returns:
            SHA256 signature hash as hex digest
        """
        # Normalize stack trace for hashing
        # Remove line numbers (they change between runs)
        normalized_trace = re.sub(r' line \d+', ' line N', stack_trace)
        normalized_trace = re.sub(r':\d+', ':N', normalized_trace)

        # Generate SHA256 hash
        signature_hash = hashlib.sha256(normalized_trace.encode('utf-8')).hexdigest()

        return signature_hash

    def get_unique_crashes(self, crashes_by_signature: Dict[str, List[Path]]) -> List[Path]:
        """
        Get representative crash for each unique signature.

        Args:
            crashes_by_signature: Dict mapping signature_hash to list of crash files

        Returns:
            List of unique crash files (one per signature)
        """
        unique_crashes = []

        for signature_hash, crash_files in crashes_by_signature.items():
            if crash_files:
                # Return first crash file as representative
                unique_crashes.append(crash_files[0])

        return unique_crashes

    def get_signature_summary(self, crashes_by_signature: Dict[str, List[Path]]) -> List[Dict]:
        """
        Get summary of crashes grouped by signature.

        Args:
            crashes_by_signature: Dict mapping signature_hash to list of crash files

        Returns:
            List of dicts with signature_hash, count, and example_crash
        """
        summary = []

        for signature_hash, crash_files in crashes_by_signature.items():
            summary.append({
                "signature_hash": signature_hash,
                "count": len(crash_files),
                "example_crash": str(crash_files[0]) if crash_files else None
            })

        # Sort by count (descending)
        summary.sort(key=lambda x: x["count"], reverse=True)

        return summary


# Convenience function for deduplication
def deduplicate_crashes(crash_dir: Path) -> Dict[str, List[Path]]:
    """
    Deduplicate crashes by error signature hash.

    Args:
        crash_dir: Directory containing crash files (*.input and *.log)

    Returns:
        Dict mapping signature_hash to list of crash files
    """
    deduplicator = CrashDeduplicator()
    return deduplicator.deduplicate_crashes(crash_dir)
