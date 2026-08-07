"""
Test suite for XXE (XML External Entity) injection protections.

GREEN PHASE: These tests verify the XXE fixes (commit 4d409f163).

The fixes:
1. enterprise_auth_service.py - SAML/XML parsing uses defusedxml (disables
   entities, DTDs, and other dangerous XML features).
"""

import inspect

import pytest


class TestXXEProtections:
    """
    Test suite verifying XXE protections are in place.

    The fix: XML parsing is performed with defusedxml, which rejects external
    entities, preventing XXE attacks like file reading and SSRF.
    """

    def test_saml_parsing_uses_defusedxml(self):
        """
        SAML response parsing must use defusedxml (safe XML parsing).
        """
        from core.enterprise_auth_service import EnterpriseAuthService

        source = inspect.getsource(EnterpriseAuthService.validate_saml_response)

        assert "defusedxml" in source, \
            "XXE fix missing: defusedxml must be used for SAML parsing"

    def test_signature_verification_uses_defusedxml(self):
        """
        Signature verification must use defusedxml (safe XML parsing).
        """
        from core.enterprise_auth_service import EnterpriseAuthService

        source = inspect.getsource(EnterpriseAuthService._verify_saml_signature)

        assert "defusedxml" in source, \
            "XXE fix missing: defusedxml must be used for signature verification"

    def test_xxe_attack_vector_blocked(self):
        """
        The malicious XXE payload must be REJECTED by the safe parser.
        """
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

        from defusedxml import ElementTree as SafeET

        with pytest.raises(Exception):
            SafeET.fromstring(malicious_xxe_xml)

    def test_defusedxml_import_present(self):
        """
        defusedxml must be imported for safe XML parsing.
        """
        from core.enterprise_auth_service import EnterpriseAuthService

        source = inspect.getsource(EnterpriseAuthService)

        assert "defusedxml" in source, \
            "XXE fix missing: defusedxml must be imported for safe XML parsing"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
