"""
Test suite for XXE (XML External Entity) fix verification.

GREEN PHASE: These tests verify the XXE fixes are applied.
"""

import pytest


class TestXXEFixes:
    """Tests for verifying the XXE fixes."""

    def test_saml_parsing_uses_defusedxml(self):
        """
        Test that SAML parsing uses defusedxml for safe XML parsing.

        GREEN PHASE: After the fix, defusedxml should be used instead of ET.fromstring.
        """
        from core.enterprise_auth_service import EnterpriseAuthService
        import inspect

        source = inspect.getsource(EnterpriseAuthService.validate_saml_response)

        # Verify the fix - defusedxml is imported and used
        assert 'defusedxml' in source, \
            "Fix applied: defusedxml is imported for safe XML parsing"

        # Verify defusedxml ElementTree import is used
        assert 'from defusedxml import ElementTree' in source, \
            "Fix applied: defusedxml.ElementTree is imported for parsing"

        # Verify XXE fix comment is present
        assert 'XXE FIX' in source, \
            "Fix applied: XXE fix comment documents the security measure"

    def test_signature_verification_uses_defusedxml(self):
        """
        Test that signature verification uses defusedxml.

        GREEN PHASE: After the fix, defusedxml should be used in signature verification.
        """
        from core.enterprise_auth_service import EnterpriseAuthService
        import inspect

        source = inspect.getsource(EnterpriseAuthService._verify_saml_signature)

        # Verify the fix - defusedxml is used
        assert 'defusedxml' in source, \
            "Fix applied: defusedxml is used for safe XML parsing"

    def test_xxe_payload_blocked(self):
        """
        Test that XXE payload is blocked by defusedxml.

        GREEN PHASE: After the fix, malicious XXE payloads should be rejected.
        """
        # This test verifies that defusedxml blocks XXE attacks
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

        # defusedxml should block entities and raise an exception
        try:
            from defusedxml import ElementTree as DET

            # This should raise a ParseError due to DTD/entity being blocked
            root = DET.fromstring(malicious_xxe_xml)
            assert False, "Fix applied: XXE should be blocked by defusedxml"

        except ImportError:
            # If defusedxml is not installed, skip this test
            pytest.skip("defusedxml not installed")

        except Exception as e:
            # defusedxml should raise an exception for XXE
            assert "Entities" in str(e) or "DTD" in str(e) or "entity" in str(e).lower(), \
                f"Fix applied: XXE blocked with error: {e}"

    def test_safe_xml_parsing_allows_valid_saml(self):
        """
        Test that safe XML parsing still allows valid SAML responses.

        GREEN PHASE: After the fix, valid SAML should still work.
        """
        # Valid SAML response without XXE
        valid_saml_xml = """<?xml version="1.0" encoding="UTF-8"?>
<samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol" ID="response123">
  <saml:Assertion xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion" ID="assertion123">
    <saml:Subject>
      <saml:NameID Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress">
        user@example.com
      </saml:NameID>
    </saml:Subject>
    <saml:AttributeStatement>
      <saml:Attribute Name="email" NameFormat="urn:oasis:names:tc:SAML:2.0:attrname-format:basic">
        <saml:AttributeValue>user@example.com</saml:AttributeValue>
      </saml:Attribute>
      <saml:Attribute Name="name" NameFormat="urn:oasis:names:tc:SAML:2.0:attrname-format:basic">
        <saml:AttributeValue>Test User</saml:AttributeValue>
      </saml:Attribute>
    </saml:AttributeStatement>
  </saml:Assertion>
</samlp:Response>
"""

        try:
            from defusedxml import ElementTree as DET

            # This should parse successfully
            root = DET.fromstring(valid_saml_xml)
            assert root is not None, "Fix applied: Valid SAML can be parsed"

        except ImportError:
            pytest.skip("defusedxml not installed")

        except Exception as e:
            pytest.fail(f"Fix failed: Valid SAML should parse: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
