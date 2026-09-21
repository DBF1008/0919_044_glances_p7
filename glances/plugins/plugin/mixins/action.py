#
# This file is part of Glances.
#
# SPDX-FileCopyrightText: 2024 Nicolas Hennion <nicolas@nicolargo.com>
#
# SPDX-License-Identifier: LGPL-3.0-only
#

"""Alert / action execution mixin.

Single responsibility: compute the alert status of a stat and trigger the
configured actions (command lines, logs and threshold events).
Can be unit tested independently from the other plugin responsibilities.
"""

import copy
from datetime import datetime

from glances.actions import GlancesActions
from glances.events_list import glances_events
from glances.logger import logger
from glances.thresholds import glances_thresholds


class ActionMixin:
    """Provide threshold detection and alert action execution to the plugin model."""

    def _init_actions(self, args=None):
        """Initialize the alert action executor."""
        self.actions = GlancesActions(args=args)

    def get_stats_action(self):
        """Return stats for the action.

        By default return all the stats.
        Can be overwrite by plugins implementation.
        For example, Docker will return self.stats['containers']
        """
        return self.stats

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

    def get_alert_log(self, current=0, minimum=0, maximum=100, header="", action_key=None):
        """Get the alert log."""
        return self.get_alert(
            current=current, minimum=minimum, maximum=maximum, header=header, action_key=action_key, log=True
        )
