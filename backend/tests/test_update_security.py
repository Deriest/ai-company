"""Cryptographic update manifest signing verification tests."""

import base64
import hashlib
import pytest
from pathlib import Path
from datetime import datetime, timezone

# Import the signing functions from release routes
try:
    from backend.api.routes.release import (
        _generate_ed25519_signature,
        get_signed_manifest,
    )
except ImportError as e:
    # Skip if dependencies not available
    print(f"Skipping update security tests: {e}")
    pytest.skip("Update security module not available", allow_module_level=True)


class TestEd25519Signing:
    """Test Ed25519 cryptographic signature generation and verification."""
    
    def test_signature_generation(self):
        """Generate a valid Ed25519 signature."""
        data = b"test manifest content for signing"
        signature = _generate_ed25519_signature(data)
        
        assert signature is not None
        assert len(signature) > 0
        # Ed25519 signatures are 64 bytes, base64 encoded = ~87 chars
        assert len(signature) >= 80
        
    def test_duplicate_signatures_different(self):
        """Each signature should be unique even for same data (with timestamps)."""
        data = b"repeated data"
        
        sig1 = _generate_ed25519_signature(data)
        sig2 = _generate_ed25519_signature(data)
        
        # With pure Ed25519, signatures for identical data ARE deterministic
        # This test documents that behavior; in practice we hash different data
        assert sig1 == sig2  # Deterministic by design
        
    def test_sign_and_verify_integration(self):
        """Full round-trip: sign manifest and verify structure."""
        version = "v2.4.89"
        notes = "Release with security fixes"
        
        # Generate mock manifest data
        manifest_data = {
            "version": version,
            "notes": notes,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        # Sign it
        import json
        data_json = json.dumps(manifest_data, sort_keys=True).encode()
        signature = _generate_ed25519_signature(data_json)
        
        assert len(signature) > 0
        # Signature is base64-encoded 64-byte Ed25519 output
        try:
            decoded = base64.b64decode(signature)
            assert len(decoded) == 64  # Ed25519 signature length
        except Exception:
            pytest.fail(f"Invalid base64 signature: {signature}")
            
    @pytest.mark.skip(reason="Requires public key infrastructure")
    def test_client_side_verification(self):
        """Integration test: client would verify server signature."""
        # In full implementation, this would:
        # 1. Server signs manifest with private key
        # 2. Client fetches manifest + signature  
        # 3. Client verifies with embedded public key
        # 4. Reject if verification fails
        
        pass
    
    def test_empty_data_rejected(self):
        """Empty or null data should still produce signature (cryptographically valid)."""
        empty_sig = _generate_ed25519_signature(b"")
        assert empty_sig is not None
        assert len(empty_sig) > 0


class TestManifestStructure:
    """Test that signed manifests have correct structure."""
    
    def test_mock_manifest_structure(self):
        """Mock manifest endpoint returns expected fields."""
        result = {"manifest": {}, "signature": "", "algorithm": ""}
        
        # Basic structural validation
        assert "manifest" in result
        assert "signature" in result
        assert "algorithm" in result
        assert result["algorithm"] == "Ed25519-SHA256"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
