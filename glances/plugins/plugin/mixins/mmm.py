#
# This file is part of Glances.
#
# SPDX-FileCopyrightText: 2024 Nicolas Hennion <nicolas@nicolargo.com>
#
# SPDX-License-Identifier: LGPL-3.0-only
#

"""Min / Max / Mean (MMM) tracking mixin.

Single responsibility: compute the min, max and mean values of the fields
flagged with ``mmm=True`` in the plugin ``fields_description``.
Can be unit tested independently from the other plugin responsibilities.
"""

from glances.globals import mean


class MMMMixin:
    """Provide Min/Max/Mean computation to the plugin model."""

    def _init_mmm(self):
        """Initialize MMM (Min/Max/Mean) tracking."""
        self._mmm_fields = self._init_mmm_fields()

    def _init_mmm_fields(self):
        """Initialize MMM (Min/Max/Mean) field tracking.

        Scan fields_description for fields with mmm=True and create tracking structures.
        Also automatically add field descriptions for the generated fields.

        Returns a dictionary with mmm field tracking info.
        """
        mmm_fields = {}

        if self.fields_description is None:
            return mmm_fields

        # Find all fields with mmm=True (iterate over keys to avoid dict size change during iteration)
        mmm_field_names = [
            field_name for field_name, field_info in self.fields_description.items() if field_info.get('mmm', False)
        ]

        # Now process the mmm fields
        for field_name in mmm_field_names:
            field_info = self.fields_description[field_name]

            # Initialize tracking for this field
            mmm_fields[field_name] = {
                'values': [],  # Keep history for mean calculation
                'min': None,
                'max': None,
                'unit': field_info.get('unit', ''),
            }

            # Automatically add field descriptions for the generated fields if not already present
            suffix_map = {
                '_min': f"Minimum {field_name} observed since Glances startup.",
                '_max': f"Maximum {field_name} observed since Glances startup.",
                '_mean': f"Mean (average) {field_name} computed from the history.",
            }

            for suffix, description in suffix_map.items():
                generated_field = field_name + suffix
                if generated_field not in self.fields_description:
                    self.fields_description[generated_field] = {
                        'description': description,
                        'unit': field_info.get('unit', ''),
                    }

        return mmm_fields

    def _update_mmm_fields(self, stats):
        """Update MMM (Min/Max/Mean) fields for all fields with mmm=True.

        This method should be called after the plugin's update method.
        It will compute and add _min, _max, and _mean fields to stats.

        Args:
            stats: The stats dictionary to update (should be a dict or dict from list item)

        Returns:
            The stats dictionary with mmm fields added
        """
        if not isinstance(stats, dict) or not self._mmm_fields:
            return stats

        # Update mmm fields for each tracked field
        for field_name, mmm_info in self._mmm_fields.items():
            if field_name not in stats:
                continue

            current_value = stats[field_name]

            # Only process numeric values
            if current_value is None or (not isinstance(current_value, (int, float))):
                continue

            # Keep history for mean calculation (limit to reasonable size to avoid memory growth)
            max_history_size = 28800  # ~1 day at 1 sample/sec
            mmm_info['values'].append(current_value)
            if len(mmm_info['values']) > max_history_size:
                mmm_info['values'].pop(0)

            # Update min and max
            if mmm_info['min'] is None or current_value < mmm_info['min']:
                mmm_info['min'] = current_value
            if mmm_info['max'] is None or current_value > mmm_info['max']:
                mmm_info['max'] = current_value

            # Add generated fields to stats
            stats[field_name + '_min'] = mmm_info['min']
            stats[field_name + '_max'] = mmm_info['max']

            # Compute mean from history
            if mmm_info['values']:
                stats[field_name + '_mean'] = round(mean(mmm_info['values']), 2)

        return stats

    def _update_mmm_fields_on_list(self, stats_list):
        """Update MMM fields for a list of stats dictionaries.

        Args:
            stats_list: A list of stats dictionaries

        Returns:
            The list with mmm fields updated for each item
        """
        if not isinstance(stats_list, list):
            return stats_list

        for stat in stats_list:
            if isinstance(stat, dict):
                self._update_mmm_fields(stat)

        return stats_list

    def _manage_mmm(fct):
        """Manage MMM (Min/Max/Mean) decorator for update method.

        Automatically computes and adds min/max/mean fields for any field with mmm=True.
        """

        def wrapper(self, *args, **kw):
            # Call the father method
            stats = fct(self, *args, **kw)

            # Update MMM fields
            if isinstance(stats, dict):
                # Stats is a dict
                self._update_mmm_fields(stats)
            elif isinstance(stats, list):
                # Stats is a list
                self._update_mmm_fields_on_list(stats)

            return stats

        return wrapper

    # Mandatory to call the decorator in child classes
    _manage_mmm = staticmethod(_manage_mmm)
