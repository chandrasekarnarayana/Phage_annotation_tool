"""Export and project save/load helpers - aggregator."""
from __future__ import annotations

from phage_annotator.ui_qt.utils.export_mixin_data import ExportMixinDataMixin
from phage_annotator.ui_qt.utils.export_mixin_relink import ExportMixinRelinkMixin
from phage_annotator.ui_qt.utils.export_mixin_view_export import ExportMixinViewExportMixin
from phage_annotator.ui_qt.utils.export_mixin_images import ExportMixinImagesMixin
from phage_annotator.ui_qt.utils.export_mixin_reports import ExportMixinReportsMixin
from phage_annotator.ui_qt.utils.export_mixin_layers import ExportMixinLayersMixin


class ExportMixin(
    ExportMixinDataMixin,
    ExportMixinRelinkMixin,
    ExportMixinViewExportMixin,
    ExportMixinImagesMixin,
    ExportMixinReportsMixin,
    ExportMixinLayersMixin,
):
    """Aggregated mixin for all export and save/load helpers."""
    pass
