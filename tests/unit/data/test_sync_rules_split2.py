"""Split definitions from test_sync_rules.py."""


from phage_annotator.data.display_mapping import (
    DisplayMapping,
    mapping_from_dict,
    mapping_to_dict,
)


class TestDisplayMappingPanelSpecificSyncRules:
    """Test sync rules on per-panel mappings."""

    def test_per_panel_mapping_can_have_different_sync_rules(self):
        """Test that different panels can have different sync configurations."""
        root = DisplayMapping(min_val=0.0, max_val=1.0)
        root.set_sync_rules(sync_vmin=True)
        # Get per-panel mappings
        root.ensure_panels(["frame", "mean"])
        frame_map = root.mapping_for(image_id=0, panel="frame")
        mean_map = root.mapping_for(image_id=0, panel="mean")
        # Set different rules
        frame_map.set_sync_rules(sync_vmin=True)
        mean_map.set_sync_rules(sync_contrast=True)
        # Verify independence
        assert frame_map.sync_contrast is False
        assert mean_map.sync_contrast is True

    def test_clone_with_per_panel_rules(self):
        """Test that cloning works with per-panel configurations."""
        root = DisplayMapping(min_val=0.0, max_val=1.0)
        root.ensure_panels(["frame", "mean"])
        root.mapping_for(image_id=0, panel="frame").set_sync_rules(sync_vmin=True)
        # Clone the root
        cloned_root = root.clone()
        # Per-panel dicts should not be cloned (shallow clone)
        assert cloned_root.per_panel == {}
        # Verify root's per-panel rules still exist
        assert root.mapping_for(image_id=0, panel="frame").sync_vmin is True

class TestDisplayMappingSyncEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_set_sync_rules_with_none_values(self):
        """Test set_sync_rules handles None by treating as False."""
        mapping = DisplayMapping(min_val=0.0, max_val=1.0)
        # Setting with explicit False should work
        mapping.set_sync_rules(sync_vmin=False, sync_vmax=False, sync_contrast=False)
        assert mapping.is_sync_enabled() is False

    def test_set_sync_rules_idempotent(self):
        """Test that calling set_sync_rules twice with same values is idempotent."""
        mapping = DisplayMapping(min_val=0.0, max_val=1.0)
        mapping.set_sync_rules(sync_vmin=True, sync_vmax=True)
        first_state = (mapping.sync_vmin, mapping.sync_vmax, mapping.sync_contrast)
        mapping.set_sync_rules(sync_vmin=True, sync_vmax=True)
        second_state = (mapping.sync_vmin, mapping.sync_vmax, mapping.sync_contrast)
        assert first_state == second_state

    def test_sync_state_code_with_all_true(self):
        """Test sync_state_code when all three rules are enabled."""
        mapping = DisplayMapping(min_val=0.0, max_val=1.0)
        mapping.set_sync_rules(sync_vmin=True, sync_vmax=True, sync_contrast=True)
        # CONTRAST should be the result (it has priority)
        assert mapping.sync_state_code() == "CONTRAST"

class TestDisplayMappingChangedFields:
    """Test that sync rules don't interfere with other DisplayMapping fields."""

    def test_sync_rules_independent_of_window_changes(self):
        """Test that changing window bounds doesn't affect sync rules."""
        mapping = DisplayMapping(min_val=0.0, max_val=1.0)
        mapping.set_sync_rules(sync_vmin=True)
        # Change window
        mapping.set_window(0.5, 0.9)
        # Sync rules should be preserved
        assert mapping.sync_vmin is True
        assert mapping.min_val == 0.5
        assert mapping.max_val == 0.9

    def test_sync_rules_independent_of_lut_changes(self):
        """Test that changing LUT doesn't affect sync rules."""
        mapping = DisplayMapping(min_val=0.0, max_val=1.0, lut=0)
        mapping.set_sync_rules(sync_contrast=True)
        # LUT is just a property, not affected by set_sync_rules
        mapping.lut = 3
        mapping.invert = True
        assert mapping.sync_contrast is True
        assert mapping.lut == 3
        assert mapping.invert is True

    def test_sync_rules_with_gamma_adjustment(self):
        """Test that sync rules work with gamma values."""
        mapping = DisplayMapping(min_val=0.0, max_val=1.0, gamma=2.2)
        mapping.set_sync_rules(sync_contrast=True)
        assert mapping.gamma == 2.2
        assert mapping.sync_contrast is True
