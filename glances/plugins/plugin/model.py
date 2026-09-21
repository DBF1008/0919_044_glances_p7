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

The former ``GlancesPluginModel`` god class has been split into focused,
independently testable mixins (see :mod:`glances.plugins.plugin.mixins`):

- StatsStorageMixin: stats read/write and reset
- HistoryMixin: history data management
- ThresholdMixin: thresholds / limits configuration
- ActionMixin: threshold detection and alert action execution
- MMMMixin: Min/Max/Mean computation
- ViewMixin: view rendering (curses helpers)
- SerializationMixin: JSON / export formatting

``GlancesPlugin`` composes all of them so plugins keep on inheriting from a
single base class. Plugins may also combine only the mixins they need.
"""

import copy

from glances.logger import logger
from glances.timer import Counter, Timer, getTimeSinceLastUpdate

from glances.plugins.plugin.mixins import (
    ActionMixin,
    HistoryMixin,
    MMMMixin,
    SerializationMixin,
    StatsStorageMixin,
    ThresholdMixin,
    ViewMixin,
)

# Kept for backward compatibility (external plugins may import these constants)
from glances.plugins.plugin.mixins.view import fields_unit_short, fields_unit_type  # noqa: F401


class GlancesPlugin(
    StatsStorageMixin,
    HistoryMixin,
    ThresholdMixin,
    ActionMixin,
    MMMMixin,
    ViewMixin,
    SerializationMixin,
):
    """Main class for Glances plugin model.

    This class only wires together the focused mixins. Every behaviour it
    exposes is implemented in one of the mixins declared above, so each
    responsibility can be unit tested independently.
    """

    def __init__(
        self,
        args=None,
        config=None,
        items_history_list=None,
        stats_init_value={},
        fields_description=None,
    ):
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

        # Init the input method
        self._input_method = 'local'
        self._short_system_name = None

        # Init the limits (configuration keys) dictionary and the aliases
        self._init_thresholds(config=config)

        # Init the views
        self._init_view()

        # Init the actions
        self._init_actions(args=args)

        # Set the initial refresh time to display stats the first time
        self.refresh_timer = Timer(0)

        # Init stats description
        self.fields_description = fields_description

        # Init MMM (Min/Max/Mean) tracking for fields with mmm=True
        self._init_mmm()

        # Init the history list and the stats storage
        self._init_history(items_history_list=items_history_list)
        self._init_storage(stats_init_value=stats_init_value)

    def exit(self):
        """Just log an event when Glances exit."""
        logger.debug(f"Stop the {self.plugin_name} plugin")

    def get_key(self):
        """Return the key of the list."""
        return

    def is_enabled(self, plugin_name=None):
        """Return true if plugin is enabled."""
        if not plugin_name:
            plugin_name = self.plugin_name
        try:
            d = getattr(self.args, 'disable_' + plugin_name)
        except AttributeError:
            d = getattr(self.args, 'enable_' + plugin_name, True)
        return d is False

    def is_disabled(self, plugin_name=None):
        """Return true if plugin is disabled."""
        return not self.is_enabled(plugin_name=plugin_name)

    @property
    def input_method(self):
        """Get the input method."""
        return self._input_method

    @input_method.setter
    def input_method(self, input_method):
        """Set the input method.

        * local: system local grab (psutil or direct access)
        * snmp: Client server mode via SNMP
        * glances: Client server mode via Glances API
        """
        self._input_method = input_method

    @property
    def short_system_name(self):
        """Get the short detected OS name (SNMP)."""
        return self._short_system_name

    @short_system_name.setter
    def short_system_name(self, short_name):
        """Set the short detected OS name (SNMP)."""
        self._short_system_name = short_name

    def _check_decorator(fct):
        """Check decorator for update method.

        It checks:
        - if the plugin is enabled.
        - if the refresh_timer is finished
        """

        def wrapper(self, *args, **kw):
            if self.is_enabled() and (self.refresh_timer.finished() or self.stats == self.get_init_value):
                # Run the method
                ret = fct(self, *args, **kw)
                # Reset the timer
                self.refresh_timer.set(self.get_refresh())
                self.refresh_timer.reset()
            else:
                # No need to call the method
                # Return the last result available
                ret = self.stats
            return ret

        return wrapper

    def _log_result_decorator(fct):
        """Log (DEBUG) the result of the function fct."""

        def wrapper(*args, **kw):
            counter = Counter()
            ret = fct(*args, **kw)
            duration = counter.get()
            class_name = args[0].__class__.__name__
            class_module = args[0].__class__.__module__
            logger.debug(f"{class_name} {class_module} {fct.__name__} return {ret} in {duration} seconds")
            return ret

        return wrapper

    def _manage_rate(fct):
        """Manage rate decorator for update method."""

        def compute_rate(self, stat, stat_previous):
            if stat_previous is None:
                return stat

            # 1) set _gauge for all the rate fields
            # 2) compute the _rate_per_sec
            # 3) set the original field to the delta between the current and the previous value
            for field in self.fields_description:
                # Check if the field exist (avoid error on some OS where some fields are not available)
                if field not in stat:
                    continue
                # For all the field with the rate=True flag
                # if 'rate' in self.fields_description[field] and self.fields_description[field]['rate'] is True:
                if self.fields_description[field].get('rate', False):
                    # Create a new metadata with the gauge
                    stat['time_since_update'] = self.time_since_last_update
                    stat[field + '_gauge'] = stat[field]
                    if field + '_gauge' in stat_previous and stat[field] and stat_previous[field + '_gauge']:
                        # The stat becomes the delta between the current and the previous value
                        stat[field] = stat[field] - stat_previous[field + '_gauge']
                        # Compute the rate
                        if self.time_since_last_update > 0:
                            stat[field + '_rate_per_sec'] = stat[field] // self.time_since_last_update
                        else:
                            stat[field] = 0
                            stat[field + '_rate_per_sec'] = 0
                    else:
                        # Avoid strange rate at the first run
                        stat[field] = 0
                        stat[field + '_rate_per_sec'] = 0
            return stat

        def compute_rate_on_list(self, stats, stats_previous):
            if stats_previous is None:
                return stats

            key = self.get_key()
            previous_by_key = {s[key]: s for s in stats_previous}
            for stat in stats:
                old = previous_by_key.get(stat[key])
                if old is not None:
                    compute_rate(self, stat, old)
            return stats

        def wrapper(self, *args, **kw):
            # Call the father method
            stats = fct(self, *args, **kw)

            # Get the time since the last update
            self.time_since_last_update = getTimeSinceLastUpdate(self.plugin_name)

            # Compute the rate
            if isinstance(stats, dict):
                # Stats is a dict
                compute_rate(self, stats, self.stats_previous)
            elif isinstance(stats, list):
                # Stats is a list
                compute_rate_on_list(self, stats, self.stats_previous)

            # Memorized the current stats for next run
            self.stats_previous = copy.deepcopy(stats)

            return stats

        return wrapper

    # Mandatory to call the decorator in child classes
    _check_decorator = staticmethod(_check_decorator)
    _log_result_decorator = staticmethod(_log_result_decorator)
    _manage_rate = staticmethod(_manage_rate)


class GlancesPluginModel(GlancesPlugin):
    """Deprecated alias of :class:`GlancesPlugin`.

    The historical god class used to aggregate every plugin responsibility.
    It is kept as a thin backward compatible wrapper so that external
    plugins and third party code importing ``GlancesPluginModel`` keep on
    working. New code should inherit from :class:`GlancesPlugin` (or combine
    the focused mixins) directly.
    """
