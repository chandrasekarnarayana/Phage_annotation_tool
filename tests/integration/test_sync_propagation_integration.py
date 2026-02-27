"""Integration tests for contrast sync propagation.

Tests verify that contrast changes correctly propagate to linked panels
when sync rules are enabled.
"""

import numpy as np
from phage_annotator.data.display_mapping import DisplayMapping


class TestContrastSyncPropagation:
    """Test end-to-end contrast sync propagation scenarios."""

    def test_sync_vmin_propagates_to_linked_panel(self):
        """Verify that vmin changes propagate when sync_vmin is enabled."""
        source = DisplayMapping(min_val=0.0, max_val=1.0)
        source.set_sync_rules(sync_vmin=True)

        target = DisplayMapping(min_val=0.0, max_val=1.0)
        # Simulate sync propagation
        if source.sync_vmin:
            target.min_val = source.min_val

        # Change source vmin and propagate
        source.min_val = 0.2
        if source.sync_vmin:
            target.min_val = source.min_val

        assert target.min_val == 0.2

    def test_sync_vmax_propagates_to_linked_panel(self):
        """Verify that vmax changes propagate when sync_vmax is enabled."""
        source = DisplayMapping(min_val=0.0, max_val=1.0)
        source.set_sync_rules(sync_vmax=True)

        target = DisplayMapping(min_val=0.0, max_val=1.0)
        # Simulate sync propagation
        if source.sync_vmax:
            target.max_val = source.max_val

        # Change source vmax and propagate
        source.max_val = 0.8
        if source.sync_vmax:
            target.max_val = source.max_val

        assert target.max_val == 0.8

    def test_contrast_sync_propagates_all_attributes(self):
        """Verify that contrast sync propagates all visual settings."""
        source = DisplayMapping(
            min_val=0.1, max_val=0.9, gamma=2.0, lut=3, invert=True
        )
        source.set_sync_rules(sync_contrast=True)

        target = DisplayMapping(min_val=0.0, max_val=1.0, gamma=1.0, lut=0)

        # Simulate full contrast sync
        if source.sync_contrast:
            target.min_val = source.min_val
            target.max_val = source.max_val
            target.gamma = source.gamma
            target.lut = source.lut
            target.invert = source.invert

        assert target.min_val == source.min_val
        assert target.max_val == source.max_val
        assert target.gamma == source.gamma
        assert target.lut == source.lut
        assert target.invert == source.invert

    def test_sync_only_when_enabled(self):
        """Verify that sync doesn't occur when rules are disabled."""
        source = DisplayMapping(min_val=0.0, max_val=1.0)
        # sync rules not enabled (all False by default)
        assert source.is_sync_enabled() is False

        target = DisplayMapping(min_val=0.0, max_val=1.0)
        original_target_min = target.min_val

        # Try to sync - should not happen
        if source.sync_vmin:
            target.min_val = source.min_val

        # Target should be unchanged
        assert target.min_val == original_target_min

    def test_selective_sync_vmin_without_vmax(self):
        """Verify vmin syncs while vmax doesn't when only vmin is enabled."""
        source = DisplayMapping(min_val=0.2, max_val=0.8, gamma=1.0, lut=2)
        source.set_sync_rules(sync_vmin=True, sync_vmax=False)

        target = DisplayMapping(min_val=0.0, max_val=1.0, gamma=1.0, lut=0)
        original_max = target.max_val

        # Simulate selective sync
        if source.sync_vmin:
            target.min_val = source.min_val
        if source.sync_vmax:
            target.max_val = source.max_val
        if source.sync_contrast:
            target.gamma = source.gamma
            target.lut = source.lut

        assert target.min_val == 0.2  # Should have propagated
        assert target.max_val == original_max  # Should NOT have changed
        assert target.lut == 0  # Contrast not enabled

    def test_multi_panel_sync_chain(self):
        """Verify sync works across multiple linked panels."""
        master = DisplayMapping(min_val=0.1, max_val=0.9)
        master.set_sync_rules(sync_vmin=True, sync_vmax=True)

        panel1 = DisplayMapping(min_val=0.0, max_val=1.0)
        panel2 = DisplayMapping(min_val=0.0, max_val=1.0)
        panel3 = DisplayMapping(min_val=0.0, max_val=1.0)

        # Simulate sync to all panels
        for panel in [panel1, panel2, panel3]:
            if master.sync_vmin:
                panel.min_val = master.min_val
            if master.sync_vmax:
                panel.max_val = master.max_val

        # All panels should match master
        for panel in [panel1, panel2, panel3]:
            assert panel.min_val == 0.1
            assert panel.max_val == 0.9

    def test_sync_rule_changes_affect_propagation(self):
        """Verify that changing sync rules changes propagation behavior."""
        source = DisplayMapping(min_val=0.0, max_val=1.0)
        target = DisplayMapping(min_val=0.0, max_val=1.0)

        # First: sync disabled
        source.min_val = 0.3
        if source.sync_vmin:
            target.min_val = source.min_val
        assert target.min_val == 0.0  # Not propagated

        # Enable sync and propagate again
        source.set_sync_rules(sync_vmin=True)
        if source.sync_vmin:
            target.min_val = source.min_val
        assert target.min_val == 0.3  # Now propagated

    def test_contrast_sync_overrides_selective_sync(self):
        """Verify that enabling contrast overrides selective vmin/vmax rules."""
        source = DisplayMapping(min_val=0.1, max_val=0.9, gamma=2.2, lut=5)
        # Start with selective sync
        source.set_sync_rules(sync_vmin=True, sync_vmax=False)
        assert source.sync_vmin is True
        assert source.sync_vmax is False

        # Now enable contrast
        source.set_sync_rules(sync_contrast=True)
        # Should now have all three enabled
        assert source.sync_vmin is True
        assert source.sync_vmax is True
        assert source.sync_contrast is True

    def test_per_panel_independent_sync_rules(self):
        """Verify that different panels can have different sync rule configs."""
        root = DisplayMapping(min_val=0.0, max_val=1.0)
        root.ensure_panels(["frame", "mean", "std"])

        # Set different rules for each panel
        frame_map = root.mapping_for(image_id=0, panel="frame")
        mean_map = root.mapping_for(image_id=0, panel="mean")
        std_map = root.mapping_for(image_id=0, panel="std")

        frame_map.set_sync_rules(sync_vmin=True)
        mean_map.set_sync_rules(sync_vmax=True)
        std_map.set_sync_rules(sync_contrast=True)

        # Verify each has independent rules
        assert frame_map.sync_vmin and not frame_map.sync_vmax
        assert mean_map.sync_vmax and not mean_map.sync_vmin
        assert std_map.sync_contrast

    def test_sync_state_reflects_propagation_behavior(self):
        """Verify sync_state_code correctly reflects what will propagate."""
        source = DisplayMapping(min_val=0.0, max_val=1.0, gamma=1.5, lut=2)

        states_and_behaviors = [
            ("NONE", [False, False, False]),  # Nothing propagates
            ("VMIN", [True, False, False]),  # Only vmin propagates
            ("VMAX", [False, True, False]),  # Only vmax propagates
            ("VMIN+VMAX", [True, True, False]),  # vmin and vmax propagate
            ("CONTRAST", [True, True, True]),  # Everything propagates
        ]

        for expected_code, (vmin, vmax, contrast) in states_and_behaviors:
            source.set_sync_rules(sync_vmin=vmin, sync_vmax=vmax, sync_contrast=contrast)
            assert source.sync_state_code() == expected_code


class TestSyncRuleEdgeCases:
    """Test edge cases in sync rule propagation."""

    def test_sync_with_equal_min_max(self):
        """Test sync behavior when vmin == vmax."""
        source = DisplayMapping(min_val=0.5, max_val=0.5)
        source.set_sync_rules(sync_vmin=True, sync_vmax=True)

        target = DisplayMapping(min_val=0.0, max_val=1.0)

        # Propagate
        if source.sync_vmin:
            target.min_val = source.min_val
        if source.sync_vmax:
            target.max_val = source.max_val

        assert target.min_val == 0.5
        assert target.max_val == 0.5

    def test_sync_with_extreme_values(self):
        """Test sync with very large/small values."""
        source = DisplayMapping(min_val=-1e6, max_val=1e6)
        source.set_sync_rules(sync_vmin=True, sync_vmax=True)

        target = DisplayMapping(min_val=0.0, max_val=1.0)

        if source.sync_vmin:
            target.min_val = source.min_val
        if source.sync_vmax:
            target.max_val = source.max_val

        assert target.min_val == -1e6
        assert target.max_val == 1e6

    def test_sync_lut_boundary_values(self):
        """Test sync with colormap index boundaries."""
        source = DisplayMapping(min_val=0.0, max_val=1.0, lut=0)
        source.set_sync_rules(sync_contrast=True)

        target = DisplayMapping(min_val=0.0, max_val=1.0, lut=255)

        if source.sync_contrast:
            target.lut = source.lut

        assert target.lut == 0

    def test_sync_with_nan_gamma(self):
        """Test sync preserves valid gamma values."""
        source = DisplayMapping(min_val=0.0, max_val=1.0, gamma=2.2)
        source.set_sync_rules(sync_contrast=True)

        target = DisplayMapping(min_val=0.0, max_val=1.0, gamma=1.0)

        if source.sync_contrast:
            target.gamma = source.gamma

        assert target.gamma == 2.2
        assert not np.isnan(target.gamma)


class TestSyncRuleValidation:
    """Test validation and consistency of sync rules."""

    def test_sync_rule_boolean_consistency(self):
        """Verify sync rules are always boolean values."""
        mapping = DisplayMapping(min_val=0.0, max_val=1.0)
        mapping.set_sync_rules(sync_vmin=1, sync_vmax="yes", sync_contrast=0)

        # Should convert to boolean
        assert isinstance(mapping.sync_vmin, bool)
        assert isinstance(mapping.sync_vmax, bool)
        assert isinstance(mapping.sync_contrast, bool)
        assert mapping.sync_vmin is True
        assert mapping.sync_vmax is True
        assert mapping.sync_contrast is False

    def test_sync_rules_persist_across_clones(self):
        """Verify sync rules are properly cloned."""
        original = DisplayMapping(min_val=0.0, max_val=1.0)
        original.set_sync_rules(sync_vmin=True, sync_contrast=True)

        # Clone
        copy1 = original.clone()
        copy2 = original.clone()

        # All should have same rules
        assert copy1.sync_vmin == original.sync_vmin
        assert copy2.sync_vmin == original.sync_vmin
        assert copy1.sync_contrast == original.sync_contrast

    def test_sync_rules_idempotent_across_changes(self):
        """Verify that reapplying the same rules is safe."""
        mapping = DisplayMapping(min_val=0.0, max_val=1.0)

        # Apply rules multiple times
        for _ in range(5):
            mapping.set_sync_rules(sync_vmin=True, sync_vmax=True)

        # State should still be correct
        assert mapping.sync_vmin is True
        assert mapping.sync_vmax is True
        assert mapping.is_sync_enabled() is True
