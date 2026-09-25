"""
GUI Components package.
"""

from .download_card import DownloadCard
from .add_dialog import AddDownloadDialog
from .batch_add_dialog import BatchAddDialog
from .details_dialog import DetailsDialog
from .settings_dialog import SettingsDialog

__all__ = [
    "DownloadCard",
    "AddDownloadDialog",
    "BatchAddDialog",
    "DetailsDialog",
    "SettingsDialog"
]
