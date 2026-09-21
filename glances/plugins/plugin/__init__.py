#
# This file is part of Glances.
#
# SPDX-FileCopyrightText: 2024 Nicolas Hennion <nicolas@nicolargo.com>
#
# SPDX-License-Identifier: LGPL-3.0-only
#

"""Glances plugin model package.

Export the composed plugin base class (GlancesPlugin) and the mixins
it is made of. Each mixin is independently testable and plugins can
compose only the responsibilities they need.
"""

from glances.plugins.plugin.action import ActionMixin
from glances.plugins.plugin.base import GlancesPlugin
from glances.plugins.plugin.history import HistoryMixin
from glances.plugins.plugin.mmm import MMMMixin
from glances.plugins.plugin.serialization import SerializationMixin
from glances.plugins.plugin.stats_storage import StatsStorageMixin
from glances.plugins.plugin.threshold import ThresholdMixin
from glances.plugins.plugin.view import ViewMixin

__all__ = [
    'ActionMixin',
    'GlancesPlugin',
    'HistoryMixin',
    'MMMMixin',
    'SerializationMixin',
    'StatsStorageMixin',
    'ThresholdMixin',
    'ViewMixin',
]
