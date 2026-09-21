#
# This file is part of Glances.
#
# SPDX-FileCopyrightText: 2024 Nicolas Hennion <nicolas@nicolargo.com>
#
# SPDX-License-Identifier: LGPL-3.0-only
#

"""
I am your father...

...of all Glances model plugins.

GlancesPlugin is the composed base class for all Glances plugins.
It combines the following mixins (each one is independently testable):

- StatsStorageMixin: stats read/write and reset
- HistoryMixin: stats history management
- ThresholdMixin: thresholds detection and alerts
- ActionMixin: alert actions execution
- MMMMixin: Min/Max/Mean computation
- ViewMixin: views rendering
- SerializationMixin: JSON serialization and export formatting
"""

from glances.actions import GlancesActions
from glances.logger import logger
from glances.plugins.plugin.action import ActionMixin
from glances.plugins.plugin.history import HistoryMixin
from glances.plugins.plugin.mmm import MMMMixin
from glances.plugins.plugin.serialization import SerializationMixin
from glances.plugins.plugin.stats_storage import StatsStorageMixin
from glances.plugins.plugin.threshold import ThresholdMixin
from glances.plugins.plugin.view import ViewMixin
from glances.timer import Timer


class GlancesPlugin(
    StatsStorageMixin,
    HistoryMixin,
    ThresholdMixin,
    ActionMixin,
    MMMMixin,
    ViewMixin,
    SerializationMixin,
):
    """Main class for Glances plugin model (composed of mixins)."""

    def __init__(self, args=None, config=None, items_history_list=None, stats_init_value={}, fields_description=None):
        """Init the plugin of plugins model class.

        All Glances' plugins model should inherit from this class. Most of the
        methods are already implemented in the father classes.

        Your plugin should return a dict or a list of dicts (stored in the
        self.stats). As an example, you can have a look on the mem plugin
        (for dict) or network (for list of dicts).

        From version 4 of the API, the plugin should return a dict.

        A plugin should implement:
        - the reset method: to set your self.stats variable to {} or []
        - the update method: where your self.stats variable is set
        and optionally:
        - the get_key method: set the key of the dict (only for list of dict)
        - all others methods you want to overwrite

        :args: args parameters
        :config: configuration parameters
        :items_history_list: list of items to store in the history
        :stats_init_value: Default value for a stats item
        """
        # Build the plugin name
        # Internal or external module (former prefixed by 'glances.plugins')
        _mod = self.__class__.__module__.replace('glances.plugins.', '')
        self.plugin_name = _mod.split('.')[0]

        if self.plugin_name.startswith('glances_'):
            self.plugin_name = self.plugin_name.split('glances_')[1]
        logger.debug(f"Init {self.plugin_name} plugin")

        # Init the args
        self.args = args

        # Init the default alignment (for curses)
        self._align = 'left'

        # Init the input method
        self._input_method = 'local'
        self._short_system_name = None

        # Init the history list
        self.items_history_list = items_history_list
        self.stats_history = self.init_stats_history()

        # Init the limits (configuration keys) dictionary
        self._limits = {}
        if config is not None:
            logger.debug(f'Load section {self.plugin_name} in Glances configuration file')
            self.load_limits(config=config)

        # Init the alias (dictionary)
        self.alias = self.read_alias()

        # Init the actions
        self.actions = GlancesActions(args=args)

        # Init the views
        self.views = {}

        # Hide stats if all the hide_zero_fields has never been != 0
        # Default is False, always display stats
        self.hide_zero = False
        # The threshold needed to display a value if hide_zero is true.
        # Only hide a value if it is less than hide_threshold_bytes.
        self.hide_threshold_bytes = 0
        self.hide_zero_fields = []

        # Set the initial refresh time to display stats the first time
        self.refresh_timer = Timer(0)

        # Init stats description
        self.fields_description = fields_description

        # Init MMM (Min/Max/Mean) tracking for fields with mmm=True
        self._mmm_fields = self._init_mmm_fields()

        # Init the stats
        self.stats_init_value = stats_init_value
        self.time_since_last_update = None
        self.stats = None
        self.stats_previous = None
        self.reset()
