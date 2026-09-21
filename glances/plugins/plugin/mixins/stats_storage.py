#
# This file is part of Glances.
#
# SPDX-FileCopyrightText: 2024 Nicolas Hennion <nicolas@nicolargo.com>
#
# SPDX-License-Identifier: LGPL-3.0-only
#

"""Stats storage mixin.

Single responsibility: hold and reset the ``stats`` attribute.
Can be unit tested independently from the other plugin responsibilities.
"""

import copy

from glances.globals import list_to_dict
from glances.logger import logger


class StatsStorageMixin:
    """Provide the stats storage (read/write/reset) to the plugin model."""

    def _init_storage(self, stats_init_value=None):
        """Initialize the stats storage attributes."""
        self.stats_init_value = stats_init_value if stats_init_value is not None else {}
        self.time_since_last_update = None
        self.stats = None
        self.stats_previous = None
        self.reset()

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
            return list(self.stats.keys())
        if isinstance(self.stats, list):
            return list(list_to_dict(self.stats).keys())
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
                    if list(item.keys())[0].startswith(list(snmp_oid.values())[0]):
                        ret[list(snmp_oid.keys())[0] + list(item.keys())[0].split(
                            list(snmp_oid.values())[0]
                        )[1]] = list(item.values())[0]
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

    def filter_stats(self, stats):
        """Filter the stats to keep only the fields we want (the one defined in fields_description)."""
        if hasattr(stats, '_asdict'):
            return {k: v for k, v in stats._asdict().items() if k in self.fields_description}
        if isinstance(stats, dict):
            return {k: v for k, v in stats.items() if k in self.fields_description}
        if isinstance(stats, list):
            return [self.filter_stats(s) for s in stats]
        return stats
