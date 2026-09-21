#
# This file is part of Glances.
#
# SPDX-FileCopyrightText: 2024 Nicolas Hennion <nicolas@nicolargo.com>
#
# SPDX-License-Identifier: LGPL-3.0-only
#

"""Action mixin.

Provide the alert action execution responsibilities of the Glances
plugin model (run command lines when a threshold is reached).
"""

import copy
from datetime import datetime


class ActionMixin:
    """Mixin class to manage the plugin alert actions."""

    def get_stats_action(self):
        """Return stats for the action.

        By default return all the stats.
        Can be overwrite by plugins implementation.
        For example, Docker will return self.stats['containers']
        """
        return self.stats

    def manage_action(self, stat_name, trigger, header, action_key):
        """Manage the action for the current stat."""
        # Here is a command line for the current trigger ?
        command, repeat = self.get_limit_action(trigger, stat_name=stat_name)
        if not command and not repeat:
            # Reset the trigger
            self.actions.set(stat_name, trigger)
        else:
            # Define the action key for the stats dict
            # If not define, then it sets to header
            if action_key is None:
                action_key = header

            # A command line is available for the current alert
            # 1) Build the {{mustache}} dictionary
            stats_action = copy.deepcopy(self.get_stats_action())
            if isinstance(stats_action, list):
                # If the stats are stored in a list of dict (fs plugin for example)
                mustache_dict = {}
                for item in stats_action:
                    # Add the limit to the mustache dict
                    item['critical'] = self.get_limit('critical', stat_name=stat_name)
                    item['warning'] = self.get_limit('warning', stat_name=stat_name)
                    item['careful'] = self.get_limit('careful', stat_name=stat_name)
                    # Add the current time (now)
                    item['time'] = datetime.now().isoformat()
                    if item[self.get_key()] == action_key:
                        mustache_dict = item
                        break
            else:
                # Use the stats dict
                # Add the limit to the mustache dict
                stats_action['critical'] = self.get_limit('critical', stat_name=stat_name)
                stats_action['warning'] = self.get_limit('warning', stat_name=stat_name)
                stats_action['careful'] = self.get_limit('careful', stat_name=stat_name)
                # Add the current time (now)
                stats_action['time'] = datetime.now().isoformat()
                mustache_dict = stats_action
            # 2) Run the action
            self.actions.run(stat_name, trigger, command, repeat, mustache_dict=mustache_dict)

    def get_limit_action(self, criticality, stat_name=""):
        """Return the tuple (action, repeat) for the alert.

        - action is a command line
        - repeat is a bool
        """
        # Get the action for stat + header
        # Example: network_wlan0_rx_careful_action
        # Action key available ?
        ret = [
            (stat_name + '_' + criticality + '_action', False),
            (stat_name + '_' + criticality + '_action_repeat', True),
            (self.plugin_name + '_' + criticality + '_action', False),
            (self.plugin_name + '_' + criticality + '_action_repeat', True),
        ]
        for r in ret:
            if r[0] in self._limits:
                return self._limits[r[0]], r[1]

        # No key found, return None
        return None, None
