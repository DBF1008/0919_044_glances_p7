#
# This file is part of Glances.
#
# SPDX-FileCopyrightText: 2024 Nicolas Hennion <nicolas@nicolargo.com>
#
# SPDX-License-Identifier: LGPL-3.0-only
#

"""History mixin.

Provide the stats history management responsibilities of the Glances
plugin model.
"""

from glances.globals import dictlist_json_dumps, json_dumps, mean, nativestr
from glances.history import GlancesHistory
from glances.logger import logger


class HistoryMixin:
    """Mixin class to manage the plugin stats history."""

    def history_enable(self):
        return self.args is not None and not self.args.disable_history and self.get_items_history_list() is not None

    def init_stats_history(self):
        """Init the stats history (dict of GlancesAttribute)."""
        if self.history_enable():
            init_list = [a['name'] for a in self.get_items_history_list()]
            logger.debug(f"Stats history activated for plugin {self.plugin_name} (items: {init_list})")
        return GlancesHistory()

    def reset_stats_history(self):
        """Reset the stats history (dict of GlancesAttribute)."""
        if self.history_enable():
            reset_list = [a['name'] for a in self.get_items_history_list()]
            logger.debug(f"Reset history for plugin {self.plugin_name} (items: {reset_list})")
            self.stats_history.reset()

    def update_stats_history(self):
        """Update stats history."""
        # Exit if no history
        if not self.history_enable():
            return
        # Build the history
        _get_export = self.get_export()
        if not (_get_export and self.history_enable()):
            return
        # Itern through items history
        item_name = '' if self.get_key() is None else self.get_key()
        for i in self.get_items_history_list():
            if isinstance(_get_export, list):
                # Stats is a list of data
                # Iter through stats (for example, iter through network interface)
                for l_export in _get_export:
                    if i['name'] in l_export:
                        self.stats_history.add(
                            nativestr(l_export[item_name]) + '_' + nativestr(i['name']),
                            l_export[i['name']],
                            description=i['description'],
                            history_max_size=self._limits['history_size'],
                        )
            else:
                # Stats is not a list
                # Add the item to the history directly
                self.stats_history.add(
                    nativestr(i['name']),
                    _get_export[i['name']],
                    description=i['description'],
                    history_max_size=self._limits['history_size'],
                )

    def get_items_history_list(self):
        """Return the items history list."""
        return self.items_history_list

    def get_raw_history(self, item=None, nb=0):
        """Return the history (RAW format).

        - the stats history (dict of list) if item is None
        - the stats history for the given item (list) instead
        - None if item did not exist in the history
        """
        s = self.stats_history.get(nb=nb)
        if item is None:
            return s
        if item in s:
            return s[item]
        return None

    def get_export_history(self, item=None):
        """Return the stats history object to export."""
        return self.get_raw_history(item=item)

    def get_stats_history(self, item=None, nb=0):
        """Return the stats history (JSON format)."""
        s = self.stats_history.get_json(nb=nb)

        if item is None:
            return json_dumps(s)

        return dictlist_json_dumps(s, item)

    def get_trend(self, item, nb=30):
        """Get the trend regarding to the last nb values.

        The trend is the diffirence between the mean of the last 0 to nb / 2
        and nb / 2 to nb values.
        """
        raw_history = self.get_raw_history(item=item, nb=nb)
        if raw_history is None or len(raw_history) < nb:
            return None
        last_nb = [v[1] for v in raw_history]
        return mean(last_nb[nb // 2 :]) - mean(last_nb[: nb // 2])
