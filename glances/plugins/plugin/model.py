#
# This file is part of Glances.
#
# SPDX-FileCopyrightText: 2024 Nicolas Hennion <nicolas@nicolargo.com>
#
# SPDX-License-Identifier: LGPL-3.0-only
#

"""Deprecated module kept for backward compatibility.

The GlancesPluginModel god class has been split into mixins (see
glances.plugins.plugin package):

- StatsStorageMixin: stats read/write and reset
- HistoryMixin: stats history management
- ThresholdMixin: thresholds detection and alerts
- ActionMixin: alert actions execution
- MMMMixin: Min/Max/Mean computation
- ViewMixin: views rendering
- SerializationMixin: JSON serialization and export formatting

New code should inherit from glances.plugins.plugin.GlancesPlugin.
"""

import warnings

from glances.plugins.plugin.base import GlancesPlugin
from glances.plugins.plugin.view import fields_unit_short, fields_unit_type

__all__ = ['GlancesPluginModel', 'fields_unit_short', 'fields_unit_type']


class GlancesPluginModel(GlancesPlugin):
    """Deprecated wrapper around GlancesPlugin (kept for backward compatibility).

    .. deprecated::
        Use glances.plugins.plugin.GlancesPlugin instead.
    """

    def __init__(self, *args, **kwargs):
        warnings.warn(
            "GlancesPluginModel is deprecated, use glances.plugins.plugin.GlancesPlugin instead",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(*args, **kwargs)
