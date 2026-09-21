#
# This file is part of Glances.
#
# SPDX-FileCopyrightText: 2024 Nicolas Hennion <nicolas@nicolargo.com>
#
# SPDX-License-Identifier: LGPL-3.0-only
#

"""Focused mixins composing the Glances plugin model.

Each mixin implements a single responsibility and can be unit tested
independently. Plugins normally inherit from the composed
:class:`glances.plugins.plugin.GlancesPlugin` base class, but the mixins
can also be combined selectively:

    class MyPlugin(StatsStorageMixin, SerializationMixin):
        ...
"""

from glances.plugins.plugin.mixins.action import ActionMixin
from glances.plugins.plugin.mixins.history import HistoryMixin
from glances.plugins.plugin.mixins.mmm import MMMMixin
from glances.plugins.plugin.mixins.serialization import SerializationMixin
from glances.plugins.plugin.mixins.stats_storage import StatsStorageMixin
from glances.plugins.plugin.mixins.threshold import ThresholdMixin
from glances.plugins.plugin.mixins.view import ViewMixin

__all__ = [
    'StatsStorageMixin',
    'HistoryMixin',
    'ThresholdMixin',
    'ActionMixin',
    'MMMMixin',
    'ViewMixin',
    'SerializationMixin',
]
