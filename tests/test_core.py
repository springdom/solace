import pytest

from backend.core.fingerprint import generate_fingerprint


class TestFingerprint:
    """Tests for the alert fingerprinting engine."""

    def test_same_inputs_produce_same_fingerprint(self):
        fp1 = generate_fingerprint(source="prometheus", name="HighCPU", service="api")
        fp2 = generate_fingerprint(source="prometheus", name="HighCPU", service="api")
        assert fp1 == fp2

    def test_different_name_produces_different_fingerprint(self):
        fp1 = generate_fingerprint(source="prometheus", name="HighCPU", service="api")
        fp2 = generate_fingerprint(source="prometheus", name="HighMemory", service="api")
        assert fp1 != fp2

    def test_different_host_produces_different_fingerprint(self):
        fp1 = generate_fingerprint(source="prometheus", name="HighCPU", host="web-01")
        fp2 = generate_fingerprint(source="prometheus", name="HighCPU", host="web-02")
        assert fp1 != fp2

    def test_none_and_missing_fields_are_equivalent(self):
        fp1 = generate_fingerprint(source="prometheus", name="HighCPU", service=None)
        fp2 = generate_fingerprint(source="prometheus", name="HighCPU")
        assert fp1 == fp2

    def test_labels_affect_fingerprint(self):
        fp1 = generate_fingerprint(
            source="prometheus", name="HighCPU",
            labels={"cluster": "us-east-1"},
        )
        fp2 = generate_fingerprint(
            source="prometheus", name="HighCPU",
            labels={"cluster": "eu-west-1"},
        )
        assert fp1 != fp2

    def test_volatile_labels_are_excluded(self):
        fp1 = generate_fingerprint(
            source="prometheus", name="HighCPU",
            labels={"cluster": "us-east-1", "timestamp": "12345"},
        )
        fp2 = generate_fingerprint(
            source="prometheus", name="HighCPU",
            labels={"cluster": "us-east-1", "timestamp": "67890"},
        )
        assert fp1 == fp2

    def test_fingerprint_is_16_chars(self):
        fp = generate_fingerprint(source="test", name="test")
        assert len(fp) == 16

    def test_label_order_does_not_matter(self):
        fp1 = generate_fingerprint(
            source="prometheus", name="HighCPU",
            labels={"z_key": "1", "a_key": "2"},
        )
        fp2 = generate_fingerprint(
            source="prometheus", name="HighCPU",
            labels={"a_key": "2", "z_key": "1"},
        )
        assert fp1 == fp2


class TestNormalizer:
    """Tests for the generic webhook normalizer."""

    def test_generic_normalizer_valid_payload(self):
        from backend.integrations import GenericNormalizer

        normalizer = GenericNormalizer()
        payload = {
            "name": "TestAlert",
            "severity": "critical",
            "service": "api",
        }

        assert normalizer.validate(payload) is True

        alerts = normalizer.normalize(payload)
        assert len(alerts) == 1
        assert alerts[0].name == "TestAlert"
        assert alerts[0].severity == "critical"
        assert alerts[0].service == "api"
        assert alerts[0].source == "generic"

    def test_generic_normalizer_minimal_payload(self):
        from backend.integrations import GenericNormalizer

        normalizer = GenericNormalizer()
        payload = {"name": "MinimalAlert"}

        assert normalizer.validate(payload) is True

        alerts = normalizer.normalize(payload)
        assert len(alerts) == 1
        assert alerts[0].severity == "warning"  # default
        assert alerts[0].status == "firing"  # default

    def test_generic_normalizer_invalid_payload(self):
        from backend.integrations import GenericNormalizer

        normalizer = GenericNormalizer()
        payload = {"not_a_valid_field": "nope"}

        assert normalizer.validate(payload) is False

    def test_normalizer_registry(self):
        from backend.integrations import get_normalizer

        normalizer = get_normalizer("generic")
        assert normalizer is not None

    def test_normalizer_registry_unknown_provider(self):
        from backend.integrations import get_normalizer

        with pytest.raises(ValueError, match="Unknown provider"):
            get_normalizer("nonexistent")
