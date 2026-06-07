"""ROI tags system tests."""

import pytest
from phage_annotator.roi.manager import Roi, RoiManager
from phage_annotator.roi.commands import AddTagCommand, RemoveTagCommand


from tests.unit.test_roi_tags_methods1 import _TestRoiTagsMethods1
from tests.unit.test_roi_tags_methods2 import _TestRoiTagsMethods2

class TestRoiTags(_TestRoiTagsMethods1, _TestRoiTagsMethods2):
    """Test ROI tags system."""

    pass
