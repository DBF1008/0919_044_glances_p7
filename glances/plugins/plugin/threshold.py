#
# This file is part of Glances.
#
# SPDX-FileCopyrightText: 2024 Nicolas Hennion <nicolas@nicolargo.com>
#
# SPDX-License-Identifier: LGPL-3.0-only
#

"""Threshold mixin.

Provide the limits (thresholds) management and alert detection
responsibilities of the Glances plugin model.
"""

import re

from glances.events_list import glances_events
from glances.globals import split_esc
from glances.logger import logger
from glances.thresholds import glances_thresholds


class ThresholdMixin:
    """Mixin class to manage the plugin limits (thresholds) and alerts."""

    def load_limits(self, config):
        """Load limits from the configuration file, if it exists."""
        # By default set the history length to 3 points per second during one day
        self._limits['history_size'] = 28800

        if not hasattr(config, 'has_section'):
            return False

        # Read the global section
        # TODO: not optimized because this section is loaded for each plugin...
        if config.has_section('global'):
            self._limits['history_size'] = config.get_float_value('global', 'history_size', default=28800)
            logger.debug("Load configuration key: {} = {}".format('history_size', self._limits['history_size']))

        # Read the plugin specific section
        if config.has_section(self.plugin_name):
            for level, _ in config.items(self.plugin_name):
                # Read limits
                limit = '_'.join([self.plugin_name, level])
                try:
                    self._limits[limit] = config.get_float_value(self.plugin_name, level)
                except ValueError:
                    self._limits[limit] = config.get_value(self.plugin_name, level).split(",")
                logger.debug(f"Load limit: {limit} = {self._limits[limit]}")

        return True

    @property
    def limits(self):
        """Return the limits object."""
        return self._limits

    @limits.setter
    def limits(self, input_limits):
        """Set the limits to input_limits."""
        self._limits = input_limits

    def set_refresh(self, value):
        """Set the plugin refresh rate"""
        self.set_limits('refresh', value)

    def get_refresh(self):
        """Return the plugin refresh time"""
        ret = self.get_limits(item='refresh')
        if ret is None:
            ret = self.args.time if hasattr(self.args, 'time') else 2
        return ret

    def get_refresh_time(self):
        """Return the plugin refresh time"""
        return self.get_refresh()

    def set_limits(self, item, value):
        """Set the limits object."""
        self._limits[f'{self.plugin_name}_{item}'] = value

    def get_limits(self, item=None):
        """Return the limits object."""
        if item is None:
            return self._limits
        return self._limits.get(f'{self.plugin_name}_{item}', None)

    def get_stat_name(self, header=None, action_key=None):
        """Return the stat name with an optional action_key and header"""
        ret = self.plugin_name
        if action_key is not None and action_key != '':
            ret += '_' + action_key
        if header is not None and header != '':
            ret += '_' + header
        return ret

    def get_alert(
        self,
        current=0,
        minimum=0,
        maximum=100,
        highlight_zero=True,
        is_max=False,
        header=None,
        action_key=None,
        log=False,
    ):
        """Return the alert status relative to a current value.

        Use this function for minor stats.

        If current < CAREFUL of max then alert = OK
        If current > CAREFUL of max then alert = CAREFUL
        If current > WARNING of max then alert = WARNING
        If current > CRITICAL of max then alert = CRITICAL

        If highlight=True than 0.0 is highlighted

        If defined 'header' is added between the plugin name and the status.
        Only useful for stats with several alert status.

        If defined, 'action_key' define the key for the actions.
        By default, the action_key is equal to the header.

        If log=True than add log if necessary
        elif log=False than do not log
        elif log=None than apply the config given in the conf file
        """
        # Manage 0 (0.0) value if highlight_zero is not True
        if not highlight_zero and current == 0:
            return 'DEFAULT'

        # Compute the %
        try:
            value = (current * 100) / maximum
        except ZeroDivisionError:
            return 'DEFAULT'
        except TypeError:
            return 'DEFAULT'

        # Build the stat_name
        stat_name = self.get_stat_name(header=header, action_key=action_key).lower()

        # Manage limits
        # If is_max is set then default style is set to MAX else default is set to OK
        ret = 'MAX' if is_max else 'OK'

        # Iter through limits
        critical = self.get_limit('critical', stat_name=stat_name)
        warning = self.get_limit('warning', stat_name=stat_name)
        careful = self.get_limit('careful', stat_name=stat_name)
        if critical and value >= critical:
            ret = 'CRITICAL'
        elif warning and value >= warning:
            ret = 'WARNING'
        elif careful and value >= careful:
            ret = 'CAREFUL'
        elif not careful and not warning and not critical:
            ret = 'DEFAULT'
        else:
            ret = 'OK'

        if current < minimum:
            ret = 'CAREFUL'

        # Manage log
        log_str = ""
        if self.get_limit_log(stat_name=stat_name, default_action=log) and ret != 'DEFAULT':
            # Add _LOG to the return string
            # So stats will be highlighted with a specific color
            log_str = "_LOG"
            # Add the log to the events list
            glances_events.add(ret, stat_name.upper(), value)

        # Manage threshold
        self.manage_threshold(stat_name, ret)

        # Manage action
        self.manage_action(stat_name, ret.lower(), header, action_key)

        # Default is 'OK'
        return ret + log_str

    def manage_threshold(self, stat_name, trigger):
        """Manage the threshold for the current stat."""
        glances_thresholds.add(stat_name, trigger)

    def get_alert_log(self, current=0, minimum=0, maximum=100, header="", action_key=None):
        """Get the alert log."""
        return self.get_alert(
            current=current, minimum=minimum, maximum=maximum, header=header, action_key=action_key, log=True
        )

    def is_limit(self, criticality, stat_name=""):
        """Return true if the criticality limit exist for the given stat_name"""
        return self.get_stat_name(stat_name).lower() + '_' + criticality in self._limits

    def get_limit(self, criticality=None, stat_name=""):
        """Return the limit value for the given criticality.
        If criticality is None, return the dict of all the limits."""
        if criticality is None:
            return self._limits

        # Get the limit for stat + header
        # Example: network_wlan0_rx_careful
        stat_name = stat_name.lower()
        if stat_name + '_' + criticality in self._limits:
            return self._limits[stat_name + '_' + criticality]
        if self.plugin_name + '_' + criticality in self._limits:
            return self._limits[self.plugin_name + '_' + criticality]

        return None

    def get_limit_log(self, stat_name, default_action=False):
        """Return the log tag for the alert."""
        # Get the log tag for stat + header
        # Example: network_wlan0_rx_log
        if stat_name + '_log' in self._limits:
            return self._limits[stat_name + '_log'][0].lower() == 'true'
        if self.plugin_name + '_log' in self._limits:
            return self._limits[self.plugin_name + '_log'][0].lower() == 'true'
        return default_action

    def get_conf_value(self, value, header="", plugin_name=None, convert_bool=False, default=[]):
        """Return the configuration (header_) value for the current plugin.

        ...or the one given by the plugin_name var.
        """
        if plugin_name is None:
            # If not default use the current plugin name
            plugin_name = self.plugin_name

        if header != "":
            # Add the header
            plugin_name = plugin_name + '_' + header

        try:
            ret = self._limits[plugin_name + '_' + value]
            return bool(ret[0]) if convert_bool else ret
        except KeyError:
            return default

    def is_show(self, value, header=""):
        """Return True if the value is in the show configuration list.

        If the show value is empty, return True (show by default)

        The show configuration list is defined in the glances.conf file.
        It is a comma-separated list of regexp.

        Example for diskio:
        show=sda.*
        """
        return any(
            re.fullmatch(i, value, re.I)
            or (self.has_alias(value) is not None and re.fullmatch(i, self.has_alias(value), re.I))
            for i in self.get_conf_value('show', header=header)
        )

    def is_hide(self, value, header=""):
        """Return True if the value is in the hide configuration list.

        The hide configuration list is defined in the glances.conf file.
        It is a comma-separated list of regexp.

        Example for diskio:
        hide=sda2,sda5,loop.*
        """
        return any(
            re.fullmatch(i, value, re.I)
            or (self.has_alias(value) is not None and re.fullmatch(i, self.has_alias(value), re.I))
            for i in self.get_conf_value('hide', header=header)
        )

    def is_display(self, value, header=""):
        """Return True if the value should be displayed in the UI"""
        if self.get_conf_value('show', header=header) != []:
            return self.is_show(value, header=header)
        return not self.is_hide(value, header=header)

    def is_display_any(self, *values, header=""):
        """Return True if any of the values should be displayed in the UI"""
        if self.get_conf_value('show', header=header) != []:
            return any(self.is_show(value, header=header) for value in values)
        return not any(self.is_hide(value, header=header) for value in values)

    def read_alias(self):
        if self.plugin_name + '_' + 'alias' in self._limits:
            return {
                split_esc(i, ':')[0].lower(): split_esc(i, ':')[1]
                for i in self._limits[self.plugin_name + '_' + 'alias']
            }
        return {}

    def has_alias(self, header):
        """Return the alias name for the relative header if it exists, otherwise None."""
        if isinstance(header, str):
            header = header.lower()
        return self.alias.get(header, None)
