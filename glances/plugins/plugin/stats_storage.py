#
# This file is part of Glances.
#
# SPDX-FileCopyrightText: 2024 Nicolas Hennion <nicolas@nicolargo.com>
#
# SPDX-License-Identifier: LGPL-3.0-only
#

"""Stats storage mixin.

Provide the stats read/write/reset responsibilities of the Glances
plugin model (the M of MVC).
"""

import copy
import re

from glances.globals import list_to_dict, listkeys
from glances.logger import logger
from glances.timer import Counter, getTimeSinceLastUpdate


class StatsStorageMixin:
    """Mixin class to manage the plugin stats storage (read/write/reset)."""

    def __str__(self):
        """Return the human-readable stats."""
        return str(self.stats)

    def __repr__(self):
        """Return the raw stats."""
        if isinstance(self.stats, list):
            return str(list_to_dict(self.stats))
        return str(self.stats)

    def __getitem__(self, item):
        """Return the stats item."""
        if isinstance(self.stats, dict) and item in self.stats:
            return self.stats[item]

        if isinstance(self.stats, list):
            ltd = list_to_dict(self.stats)
            if item in ltd:
                return ltd[item]

        raise KeyError(f"'{self.__class__.__name__}' object has no key '{item}'")

    def keys(self):
        """Return the keys of the stats."""
        if isinstance(self.stats, dict):
            return listkeys(self.stats)
        if isinstance(self.stats, list):
            return listkeys(list_to_dict(self.stats))
        return []

    def get(self, item, default=None):
        """Return the stats item or default if not found."""
        try:
            return self[item]
        except KeyError:
            return default

    def get_init_value(self):
        """Return a copy of the init value."""
        return copy.copy(self.stats_init_value)

    def reset(self):
        """Reset the stats.

        This method should be overwritten by child classes.
        """
        self.stats = self.get_init_value()

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

    def sorted_stats(self):
        """Get the stats sorted by an alias (if present) or key."""
        key = self.get_key()
        if key is None:
            return self.stats
        try:
            return sorted(
                self.stats,
                key=lambda stat: tuple(
                    int(part) if part.isdigit() else part.lower()
                    for part in re.split(r"(\d+|\D+)", self.has_alias(stat[key]) or stat[key])
                ),
            )
        except TypeError:
            # Correct "Starting an alias with a number causes a crash #1885"
            return sorted(
                self.stats,
                key=lambda stat: tuple(
                    part.lower() for part in re.split(r"(\d+|\D+)", self.has_alias(stat[key]) or stat[key])
                ),
            )

    def set_stats(self, input_stats):
        """Set the stats to input_stats."""
        self.stats = input_stats

    def get_stats_snmp(self, bulk=False, snmp_oid=None):
        """Update stats using SNMP.

        If bulk=True, use a bulk request instead of a get request.
        """
        snmp_oid = snmp_oid or {}

        from glances.snmp import GlancesSNMPClient

        # Init the SNMP request
        snmp_client = GlancesSNMPClient(
            host=self.args.client,
            port=self.args.snmp_port,
            version=self.args.snmp_version,
            community=self.args.snmp_community,
        )

        # Process the SNMP request
        ret = {}
        if bulk:
            # Bulk request
            snmp_result = snmp_client.getbulk_by_oid(0, 10, *list(snmp_oid.values()))
            logger.info(snmp_result)
            if len(snmp_oid) == 1:
                # Bulk command for only one OID
                # Note: key is the item indexed but the OID result
                for item in snmp_result:
                    if item.keys()[0].startswith(snmp_oid.values()[0]):
                        ret[snmp_oid.keys()[0] + item.keys()[0].split(snmp_oid.values()[0])[1]] = item.values()[0]
            else:
                # Build the internal dict with the SNMP result
                # Note: key is the first item in the snmp_oid
                index = 1
                for item in snmp_result:
                    item_stats = {}
                    item_key = None
                    for key in snmp_oid:
                        oid = snmp_oid[key] + '.' + str(index)
                        if oid in item:
                            if item_key is None:
                                item_key = item[oid]
                            else:
                                item_stats[key] = item[oid]
                    if item_stats:
                        ret[item_key] = item_stats
                    index += 1
        else:
            # Simple get request
            snmp_result = snmp_client.get_by_oid(*list(snmp_oid.values()))

            # Build the internal dict with the SNMP result
            for key in snmp_oid:
                ret[key] = snmp_result[snmp_oid[key]]

        return ret

    def get_raw(self):
        """Return the stats object."""
        return self.stats

    def get_api(self):
        """Return the stats object for the API.
        By default, return the raw stats."""
        return self.get_raw()

    def get_item_info(self, item, key, default=None):
        """Return the item info grabbed into self.fields_description."""
        if self.fields_description is None or item not in self.fields_description:
            return default
        return self.fields_description[item].get(key, default)

    def filter_stats(self, stats):
        """Filter the stats to keep only the fields we want (the one defined in fields_description)."""
        if hasattr(stats, '_asdict'):
            return {k: v for k, v in stats._asdict().items() if k in self.fields_description}
        if isinstance(stats, dict):
            return {k: v for k, v in stats.items() if k in self.fields_description}
        if isinstance(stats, list):
            return [self.filter_stats(s) for s in stats]
        return stats

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
