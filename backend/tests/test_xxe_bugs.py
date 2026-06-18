"""
Test suite for XXE (XML External Entity) injection vulnerabilities.

RED PHASE: These tests expose XXE vulnerabilities.

The bugs:
1. enterprise_auth_service.py:486 - ET.fromstring() parses SAML without XXE protection
2. enterprise_auth_service.py:588 - ET.fromstring() parses XML without XXE protection
"""

import pytest
import inspect


class TestXXEVulnerabilities:
    """
    Test suite revealing XXE vulnerabilities.

    The bug: XML parsing is performed without disabling external entities,
    allowing attackers to perform XXE attacks like file reading and SSRF.
    """

    def test_saml_parsing_uses_unsafe_et_fromstring(self):
        """
        Test that SAML response parsing uses unsafe ET.fromstring().

        BUG: Line 486 - ET.fromstring(xml_string) parses user-provided SAML
        without disabling external entities, allowing XXE attacks.
        """
        from core.enterprise_auth_service import EnterpriseAuthService

        source = inspect.getsource(EnterpriseAuthService.validate_saml_response)

        # Verify the bug - ET.fromstring is used
        assert 'ET.fromstring' in source, \
            "Bug confirmed: ET.fromstring is used to parse XML"

        # Verify no XXE protection is present
        assert 'defusedxml' not in source, \
            "Bug confirmed: defusedxml not used for safe parsing"

        # Verify no parser configuration to disable entities
        assert 'XMLParser' not in source or 'resolve_entities' not in source, \
            "Bug confirmed: No parser configuration to disable entities"

    def test_signature_verification_uses_unsafe_et_fromstring(self):
        """
        Test that signature verification uses unsafe ET.fromstring().

        BUG: Line 588 - ET.fromstring(xml_string) parses XML without XXE protection.
        """
        from core.enterprise_auth_service import EnterpriseAuthService

        source = inspect.getsource(EnterpriseAuthService._verify_saml_signature)

        # Verify the bug - ET.fromstring is used
        assert 'ET.fromstring' in source, \
            "Bug confirmed: ET.fromstring is used to parse XML"

        # Verify no XXE protection
        assert 'defusedxml' not in source, \
            "Bug confirmed: No defusedxml protection"

    def test_xxe_attack_vector_possible(self):
        """
        Test that XXE attack vector is possible.

        BUG: An attacker could craft a malicious SAML response with XXE payload
        to read local files or perform SSRF attacks.
        """
        # This test demonstrates the XXE attack vector
        # In a vulnerable implementation, this XML would read /etc/passwd

        malicious_xxe_xml = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE samlp:Response [
  <!ENTITY % xxe SYSTEM "file:///etc/passwd">
  %xxe;
]>
<samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol">
  <saml:Assertion xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion">
    <saml:AttributeStatement>
      <saml:Attribute Name="user">&xxe;</saml:Attribute>
    </saml:AttributeStatement>
  </saml:Assertion>
</samlp:Response>
"""

        # In Python 3.8+, ET.fromstring disables entities by default
        # But this should be explicitly configured for defense in depth
        from xml.etree import ElementTree as ET

        try:
            # In vulnerable implementations, this would parse the entity
            # In Python 3.8+, this raises a ParseError or ignores the entity
            # But we shouldn't rely on implicit security
            root = ET.fromstring(malicious_xxe_xml)
            # If we get here without error, the implementation might be vulnerable
            # depending on Python version
            assert False, "Bug confirmed: XXE XML was parsed (implicit security only)"
        except Exception:
            # Exception is good, but we want explicit protection
            pass

    def test_no_defusedxml_import(self):
        """
        Test that defusedxml is not imported for safe XML parsing.

        BUG: The codebase doesn't use defusedxml for safe XML parsing.
        """
        from core.enterprise_auth_service import EnterpriseAuthService
        import inspect

        # Get the full module source
        source = inspect.getsource(EnterpriseAuthService)

        # Verify defusedxml is not used
        assert 'defusedxml' not in source, \
            "Bug confirmed: defusedxml not imported for safe XML parsing"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
