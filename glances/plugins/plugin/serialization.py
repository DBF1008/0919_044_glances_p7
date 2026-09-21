#
# This file is part of Glances.
#
# SPDX-FileCopyrightText: 2024 Nicolas Hennion <nicolas@nicolargo.com>
#
# SPDX-License-Identifier: LGPL-3.0-only
#

"""Serialization mixin.

Provide the JSON serialization and export formatting responsibilities
of the Glances plugin model.
"""

from glances.globals import dictlist, dictlist_json_dumps, json_dumps
from glances.logger import logger


class SerializationMixin:
    """Mixin class to manage the plugin stats serialization (JSON/export)."""

    def get_export(self):
        """Return the stats object to export.
        By default, return the raw stats.
        Note: this method could be overwritten by the plugin if a specific format is needed (ex: processlist)
        """
        return self.get_raw()

    def get_stats(self):
        """Return the stats object in JSON format."""
        return json_dumps(self.get_raw())

    def get_json(self):
        """Return the stats object in JSON format."""
        return self.get_stats()

    def get_raw_stats_item(self, item):
        """Return the stats object for a specific item in RAW format.

        Stats should be a list of dict (processlist, network...)
        """
        return dictlist(self.get_raw(), item)

    def get_raw_stats_key(self, item, key):
        """Return the stats object for a specific item in RAW format.

        Stats should be a list of dict (processlist, network...)
        """
        return {item: [i for i in self.get_raw() if 'key' in i and i[i['key']] == key][0].get(item)}

    def get_stats_item(self, item):
        """Return the stats object for a specific item in JSON format.

        Stats should be a list of dict (processlist, network...)
        """
        return dictlist_json_dumps(self.get_raw(), item)

    def get_raw_stats_value(self, item, value):
        """Return the stats object for a specific item=value.

        Return None if the item=value does not exist
        Return None if the item is not a list of dict
        """
        if not isinstance(self.get_raw(), list):
            return None

        if (not isinstance(value, int) and not isinstance(value, float)) and value.isdigit():
            value = int(value)
        try:
            return {value: [i for i in self.get_raw() if i[item] == value]}
        except (KeyError, ValueError) as e:
            logger.error(f"Cannot get item({item})=value({value}) ({e})")
            return None

    def get_stats_value(self, item, value):
        """Return the stats object for a specific item=value in JSON format.

        Stats should be a list of dict (processlist, network...)
        """
        rsv = self.get_raw_stats_value(item, value)
        if rsv is None:
            return None
        return json_dumps(rsv)
