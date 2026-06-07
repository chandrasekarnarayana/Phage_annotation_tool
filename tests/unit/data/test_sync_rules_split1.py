"""Split definitions from test_sync_rules.py."""


from phage_annotator.data.display_mapping import (
    DisplayMapping,
    mapping_from_dict,
    mapping_to_dict,
)


class TestDisplayMappingSyncRules:
    """Test sync rule flags and methods on DisplayMapping."""

    def test_sync_rule_initialization(self):
        """Verify sync rules initialize to False."""
        mapping = DisplayMapping(min_val=0.0, max_val=1.0)
        assert mapping.sync_vmin is False
        assert mapping.sync_vmax is False
        assert mapping.sync_contrast is False

    def test_set_sync_rules_vmin(self):
        """Test setting only vmin sync rule."""
        mapping = DisplayMapping(min_val=0.0, max_val=1.0)
        mapping.set_sync_rules(sync_vmin=True)
        assert mapping.sync_vmin is True
        assert mapping.sync_vmax is False
        assert mapping.sync_contrast is False

    def test_set_sync_rules_vmax(self):
        """Test setting only vmax sync rule."""
        mapping = DisplayMapping(min_val=0.0, max_val=1.0)
        mapping.set_sync_rules(sync_vmax=True)
        assert mapping.sync_vmin is False
        assert mapping.sync_vmax is True
        assert mapping.sync_contrast is False

    def test_set_sync_rules_vmin_vmax(self):
        """Test setting both vmin and vmax sync rules."""
        mapping = DisplayMapping(min_val=0.0, max_val=1.0)
        mapping.set_sync_rules(sync_vmin=True, sync_vmax=True)
        assert mapping.sync_vmin is True
        assert mapping.sync_vmax is True
        assert mapping.sync_contrast is False

    def test_set_sync_rules_contrast_implies_vmin_vmax(self):
        """Test that sync_contrast=True implies sync_vmin and sync_vmax."""
        mapping = DisplayMapping(min_val=0.0, max_val=1.0)
        mapping.set_sync_rules(sync_contrast=True)
        assert mapping.sync_vmin is True
        assert mapping.sync_vmax is True
        assert mapping.sync_contrast is True

    def test_set_sync_rules_contrast_overrides_individual_false(self):
        """Test that setting contrast=True overrides individual False flags."""
        mapping = DisplayMapping(min_val=0.0, max_val=1.0)
        mapping.set_sync_rules(sync_vmin=False, sync_vmax=False, sync_contrast=True)
        # sync_contrast should force vmin/vmax to True
        assert mapping.sync_vmin is True
        assert mapping.sync_vmax is True
        assert mapping.sync_contrast is True

    def test_set_sync_rules_multiple_calls(self):
        """Test that multiple calls to set_sync_rules work correctly."""
        mapping = DisplayMapping(min_val=0.0, max_val=1.0)
        mapping.set_sync_rules(sync_vmin=True)
        assert mapping.sync_vmin is True
        # Second call with different rules
        mapping.set_sync_rules(sync_vmax=True, sync_vmin=False)
        assert mapping.sync_vmin is False
        assert mapping.sync_vmax is True

    def test_is_sync_enabled_when_all_false(self):
        """Test is_sync_enabled returns False when no rules are enabled."""
        mapping = DisplayMapping(min_val=0.0, max_val=1.0)
        assert mapping.is_sync_enabled() is False

    def test_is_sync_enabled_when_vmin_true(self):
        """Test is_sync_enabled returns True when vmin is enabled."""
        mapping = DisplayMapping(min_val=0.0, max_val=1.0)
        mapping.set_sync_rules(sync_vmin=True)
        assert mapping.is_sync_enabled() is True

    def test_is_sync_enabled_when_vmax_true(self):
        """Test is_sync_enabled returns True when vmax is enabled."""
        mapping = DisplayMapping(min_val=0.0, max_val=1.0)
        mapping.set_sync_rules(sync_vmax=True)
        assert mapping.is_sync_enabled() is True

    def test_is_sync_enabled_when_contrast_true(self):
        """Test is_sync_enabled returns True when contrast is enabled."""
        mapping = DisplayMapping(min_val=0.0, max_val=1.0)
        mapping.set_sync_rules(sync_contrast=True)
        assert mapping.is_sync_enabled() is True

    def test_sync_state_code_none(self):
        """Test sync_state_code returns 'NONE' when all rules are disabled."""
        mapping = DisplayMapping(min_val=0.0, max_val=1.0)
        assert mapping.sync_state_code() == "NONE"

    def test_sync_state_code_vmin(self):
        """Test sync_state_code returns 'VMIN' when only vmin is enabled."""
        mapping = DisplayMapping(min_val=0.0, max_val=1.0)
        mapping.set_sync_rules(sync_vmin=True)
        assert mapping.sync_state_code() == "VMIN"

    def test_sync_state_code_vmax(self):
        """Test sync_state_code returns 'VMAX' when only vmax is enabled."""
        mapping = DisplayMapping(min_val=0.0, max_val=1.0)
        mapping.set_sync_rules(sync_vmax=True)
        assert mapping.sync_state_code() == "VMAX"

    def test_sync_state_code_vmin_vmax(self):
        """Test sync_state_code returns 'VMIN+VMAX' when both are enabled."""
        mapping = DisplayMapping(min_val=0.0, max_val=1.0)
        mapping.set_sync_rules(sync_vmin=True, sync_vmax=True)
        assert mapping.sync_state_code() == "VMIN+VMAX"

    def test_sync_state_code_contrast(self):
        """Test sync_state_code returns 'CONTRAST' when contrast is enabled."""
        mapping = DisplayMapping(min_val=0.0, max_val=1.0)
        mapping.set_sync_rules(sync_contrast=True)
        assert mapping.sync_state_code() == "CONTRAST"

    def test_sync_state_code_priority(self):
        """Test sync_state_code prioritizes CONTRAST over VMIN+VMAX."""
        mapping = DisplayMapping(
            min_val=0.0,
            max_val=1.0,
            sync_vmin=True,
            sync_vmax=True,
            sync_contrast=True,
        )
        # CONTRAST should take priority
        assert mapping.sync_state_code() == "CONTRAST"

class TestDisplayMappingCloneWithSyncRules:
    """Test that clone() properly preserves sync rules."""

    def test_clone_preserves_sync_rules(self):
        """Test that clone copies sync rule flags."""
        original = DisplayMapping(min_val=0.0, max_val=1.0)
        original.set_sync_rules(sync_vmin=True, sync_vmax=True, sync_contrast=False)
        cloned = original.clone()
        assert cloned.sync_vmin is True
        assert cloned.sync_vmax is True
        assert cloned.sync_contrast is False

    def test_clone_is_independent(self):
        """Test that modifying cloned rules doesn't affect original."""
        original = DisplayMapping(min_val=0.0, max_val=1.0)
        original.set_sync_rules(sync_vmin=True)
        cloned = original.clone()
        # Modify the clone
        cloned.set_sync_rules(sync_contrast=True)
        # Original should be unchanged
        assert original.sync_contrast is False
        assert cloned.sync_contrast is True

class TestDisplayMappingSerialization:
    """Test that sync rules are properly serialized and deserialized."""

    def test_mapping_to_dict_includes_sync_rules(self):
        """Test that mapping_to_dict includes all sync rule fields."""
        mapping = DisplayMapping(min_val=0.5, max_val=1.5, lut=2, invert=True)
        mapping.set_sync_rules(sync_vmin=True, sync_vmax=True)
        result = mapping_to_dict(mapping)
        assert "sync_vmin" in result
        assert "sync_vmax" in result
        assert "sync_contrast" in result
        assert result["sync_vmin"] is True
        assert result["sync_vmax"] is True
        assert result["sync_contrast"] is False

    def test_mapping_from_dict_restores_sync_rules(self):
        """Test that mapping_from_dict restores sync rule flags."""
        data = {
            "min_val": 0.5,
            "max_val": 1.5,
            "gamma": 1.2,
            "mode": "linear",
            "lut": 2,
            "invert": True,
            "sync_vmin": True,
            "sync_vmax": True,
            "sync_contrast": False,
        }
        mapping = mapping_from_dict(data)
        assert mapping.sync_vmin is True
        assert mapping.sync_vmax is True
        assert mapping.sync_contrast is False

    def test_roundtrip_preserves_sync_rules(self):
        """Test that serialization roundtrip preserves all data including sync rules."""
        original = DisplayMapping(min_val=0.2, max_val=0.9, gamma=1.5, lut=3)
        original.set_sync_rules(sync_contrast=True)
        # Serialize and deserialize
        data = mapping_to_dict(original)
        restored = mapping_from_dict(data)
        assert restored.min_val == original.min_val
        assert restored.max_val == original.max_val
        assert restored.gamma == original.gamma
        assert restored.lut == original.lut
        assert restored.sync_vmin == original.sync_vmin
        assert restored.sync_vmax == original.sync_vmax
        assert restored.sync_contrast == original.sync_contrast

    def test_mapping_from_dict_with_missing_sync_fields(self):
        """Test that old data without sync fields defaults to False."""
        # Simulate old data format missing sync fields
        data = {
            "min_val": 0.5,
            "max_val": 1.5,
            "gamma": 1.0,
            "mode": "linear",
            "lut": 0,
            "invert": False,
        }
        mapping = mapping_from_dict(data)
        # Should default to False when missing
        assert mapping.sync_vmin is False
        assert mapping.sync_vmax is False
        assert mapping.sync_contrast is False

class TestDisplayMappingSyncRulesLogic:
    """Test the logical behavior of sync rules."""

    def test_contrast_mode_enables_all_brightness_sync(self):
        """Test that enabling contrast also enables vmin/vmax sync."""
        mapping = DisplayMapping(min_val=0.0, max_val=1.0)
        # Start with no sync
        assert mapping.is_sync_enabled() is False
        # Enable only contrast
        mapping.set_sync_rules(sync_contrast=True)
        # Should enable vmin and vmax too
        assert mapping.sync_vmin is True
        assert mapping.sync_vmax is True
        assert mapping.sync_contrast is True

    def test_sync_rules_are_independent_until_contrast(self):
        """Test that vmin and vmax are independent until contrast is enabled."""
        mapping = DisplayMapping(min_val=0.0, max_val=1.0)
        mapping.set_sync_rules(sync_vmin=True, sync_vmax=False)
        assert mapping.sync_vmin is True
        assert mapping.sync_vmax is False
        assert mapping.sync_contrast is False
        # Now enable contrast
        mapping.set_sync_rules(sync_vmin=True, sync_vmax=False, sync_contrast=True)
        # Contrast should override
        assert mapping.sync_vmin is True
        assert mapping.sync_vmax is True
        assert mapping.sync_contrast is True

    def test_sync_state_reflects_current_rules(self):
        """Test that sync_state_code accurately reflects enabled rules."""
        mapping = DisplayMapping(min_val=0.0, max_val=1.0)
        # Test all possible states
        states = [
            ({}, "NONE"),
            ({"sync_vmin": True}, "VMIN"),
            ({"sync_vmax": True}, "VMAX"),
            ({"sync_vmin": True, "sync_vmax": True}, "VMIN+VMAX"),
            ({"sync_contrast": True}, "CONTRAST"),
        ]
        for rules, expected in states:
            mapping.set_sync_rules(**rules)
            assert mapping.sync_state_code() == expected
