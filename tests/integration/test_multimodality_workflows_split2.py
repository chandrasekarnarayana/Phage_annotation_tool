"""Split definitions from test_multimodality_workflows.py."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from phage_annotator.annotation.core import Keypoint
from phage_annotator.data.display_mapping import DisplayMapping
from phage_annotator.session.modality import ModalityManager


from tests.integration.test_multimodality_workflows_split1 import _make_keypoint, _visible_annotations

from tests.integration.test_multimodality_workflows_split2_methods1 import _TestMultiModalityWorkflowsMethods1
from tests.integration.test_multimodality_workflows_split2_methods2 import _TestMultiModalityWorkflowsMethods2

class TestMultiModalityWorkflows(_TestMultiModalityWorkflowsMethods1, _TestMultiModalityWorkflowsMethods2):
    """Test complete multi-modality workflows."""

    pass
