#
# This file is part of Glances.
#
# SPDX-FileCopyrightText: 2024 Nicolas Hennion <nicolas@nicolargo.com>
#
# SPDX-License-Identifier: LGPL-3.0-only
#

"""Glances plugin base package.

Exports the composed plugin base class :class:`GlancesPlugin` together with
the focused mixins so plugins can either inherit from the full base class or
combine only the responsibilities they need.
"""

from glances.plugins.plugin.mixins import (
    ActionMixin,
    HistoryMixin,
    MMMMixin,
    SerializationMixin,
    StatsStorageMixin,
    ThresholdMixin,
    ViewMixin,
)
from glances.plugins.plugin.model import GlancesPlugin, GlancesPluginModel

__all__ = [
    'GlancesPlugin',
    'GlancesPluginModel',
    'StatsStorageMixin',
    'HistoryMixin',
    'ThresholdMixin',
    'ActionMixin',
    'MMMMixin',
    'ViewMixin',
    'SerializationMixin',
]
