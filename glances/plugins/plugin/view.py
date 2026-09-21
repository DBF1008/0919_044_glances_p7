#
# This file is part of Glances.
#
# SPDX-FileCopyrightText: 2024 Nicolas Hennion <nicolas@nicolargo.com>
#
# SPDX-License-Identifier: LGPL-3.0-only
#

"""View mixin.

Provide the view rendering responsibilities of the Glances plugin
model (the V of MVC): views dict, curses messages and display helpers.
"""

from glances.globals import auto_unit, json_dumps, listkeys
from glances.outputs.glances_unicode import unicode_message

fields_unit_short = {'percent': '%'}

fields_unit_type = {
    'percent': 'float',
    'percents': 'float',
    'number': 'int',
    'numbers': 'int',
    'int': 'int',
    'ints': 'int',
    'float': 'float',
    'floats': 'float',
    'second': 'int',
    'seconds': 'int',
    'byte': 'int',
    'bytes': 'int',
}


class ViewMixin:
    """Mixin class to manage the plugin views (rendering)."""

    def _build_field_decoration(self, field):
        """Return the field decoration.

        The decoration is used to display the field in the UI.
        """
        # Manage the decoration
        if self.fields_description and field in self.fields_description:
            if (
                self.fields_description[field].get('rate') is True
                and isinstance(self.stats, dict)
                and self.stats.get('time_since_update', 0) == 0
            ):
                return 'DEFAULT'
            if self.fields_description[field].get('log') is True:
                return self.get_alert_log(self.stats[field], header=field)
            if self.fields_description[field].get('alert') is True:
                return self.get_alert(self.stats[field], header=field)
        return 'DEFAULT'

    def _build_field_optional(self, field):
        """Return true if the field is optional."""
        if self.fields_description and field in self.fields_description:
            return self.fields_description[field].get('optional', False)
        return False

    def _build_view_for_field(self, key=None, field=None):
        view = {
            'decoration': self._build_field_decoration(field),
            'optional': self._build_field_optional(field),
            'additional': False,
            'splittable': False,
            'hidden': False,
        }

        # Manage the hidden feature
        # Allow to automatically hide fields when values is never different than 0
        # Refactoring done for #2929
        if not self.hide_zero:
            view['hidden'] = False
        elif key and key in self.views and field in self.views[key] and 'hidden' in self.views[key][field]:
            view['hidden'] = self.views[key][field]['hidden']
            if (
                field in self.hide_zero_fields
                and self.get_raw_stats_key(item=field, key=key).get(field) >= self.hide_threshold_bytes
            ):
                view['hidden'] = False
            # logger.info(f'{key=} {field=} {view["hidden"]=}')
        else:
            view['hidden'] = field in self.hide_zero_fields

        return view

    def update_views(self):
        """Update the stats views.

        The V of MVC
        A dict of dict with the needed information to display the stats.
        Example for the stat xxx:
        'xxx': {'decoration': 'DEFAULT',  >>> The decoration of the stats
                'optional': False,        >>> Is the stat optional
                'additional': False,      >>> Is the stat provide additional information
                'splittable': False,      >>> Is the stat can be cut (like process lon name)
                'hidden': False}          >>> Is the stats should be hidden in the UI
        """
        ret = {}

        if self.get_raw() is not None and isinstance(self.get_raw(), list) and self.get_key() is not None:
            # Stats are stored in a list of dict (ex: DISKIO, NETWORK, FS...)
            for i in self.get_raw():
                key = i[self.get_key()]
                ret[key] = {}
                for field in listkeys(i):
                    ret[key][field] = self._build_view_for_field(key=key, field=field)
        elif isinstance(self.get_raw(), dict) and self.get_raw() is not None:
            # Stats are stored in a dict (ex: CPU, LOAD...)
            for field in listkeys(self.get_raw()):
                ret[field] = self._build_view_for_field(key=None, field=field)

        self.views = ret

        return self.views

    def set_views(self, input_views):
        """Set the views to input_views."""
        self.views = input_views

    def reset_views(self):
        """Reset the views to input_views."""
        self.views = {}

    def get_views(self, item=None, key=None, option=None):
        """Return the views object.

        If key is None, return all the view for the current plugin
        else if option is None return the view for the specific key (all option)
        else return the view of the specific key/option

        Specify item if the stats are stored in a dict of dict (ex: NETWORK, FS...)
        """
        if item is None:
            item_views = self.views
        else:
            item_views = self.views[item]
        if key is None:
            return item_views
        if key not in item_views:
            return 'DEFAULT'
        if option is None:
            return item_views[key]
        if option in item_views[key]:
            return item_views[key][option]
        return 'DEFAULT'

    def get_json_views(self, item=None, key=None, option=None):
        """Return the views (in JSON)."""
        return json_dumps(self.get_views(item, key, option))

    def msg_curse(self, args=None, max_width=None):
        """Return default string to display in the curse interface."""
        return [self.curse_add_line(str(self.stats))]

    def get_stats_display(self, args=None, max_width=None):
        """Return a dict with all the information needed to display the stat.

        key     | description
        ----------------------------
        display | Display the stat (True or False)
        msgdict | Message to display (list of dict [{ 'msg': msg, 'decoration': decoration } ... ])
        align   | Message position
        """
        display_curse = False

        if hasattr(self, 'display_curse'):
            display_curse = self.display_curse
        if hasattr(self, 'align'):
            align_curse = self._align

        if max_width is not None:
            ret = {'display': display_curse, 'msgdict': self.msg_curse(args, max_width=max_width), 'align': align_curse}
        else:
            ret = {'display': display_curse, 'msgdict': self.msg_curse(args), 'align': align_curse}

        return ret

    def curse_add_line(self, msg, decoration="DEFAULT", optional=False, additional=False, splittable=False):
        """Return a dict with.

        Where:
            msg: string
            decoration:
                DEFAULT: no decoration
                UNDERLINE: underline
                BOLD: bold
                TITLE: for stat title
                PROCESS: for process name
                STATUS: for process status
                CPU_TIME: for process cpu time
                OK: Value is OK and non logged
                OK_LOG: Value is OK and logged
                CAREFUL: Value is CAREFUL and non logged
                CAREFUL_LOG: Value is CAREFUL and logged
                WARNING: Value is WARNING and non logged
                WARNING_LOG: Value is WARNING and logged
                CRITICAL: Value is CRITICAL and non logged
                CRITICAL_LOG: Value is CRITICAL and logged
            optional: True if the stat is optional (display only if space is available)
            additional: True if the stat is additional (display only if space is available after optional)
            spittable: Line can be split to fit on the screen (default is not)
        """
        return {
            'msg': msg,
            'decoration': decoration,
            'optional': optional,
            'additional': additional,
            'splittable': splittable,
        }

    def curse_new_line(self):
        """Go to a new line."""
        return self.curse_add_line('\n')

    def curse_add_stat(self, key, width=None, header='', display_key=True, separator='', trailer=''):
        """Return a list of dict messages with the 'key: value' result

          <=== width ===>
        __key     : 80.5%__
        | |       | |    |_ trailer
        | |       | |_ self.stats[key]
        | |       |_ separator
        | |_ 'short_name' description or key or nothing if display_key is True
        |_ header

        Instead of:
            msg = '  {:8}'.format('idle:')
            ret.append(self.curse_add_line(msg, optional=self.get_views(key='idle', option='optional')))
            msg = '{:5.1f}%'.format(self.stats['idle'])
            ret.append(self.curse_add_line(msg, optional=self.get_views(key='idle', option='optional')))

        Use:
            ret.extend(self.curse_add_stat('idle', width=15, header='  '))

        """
        if key not in self.stats:
            return []

        # Check if a shortname is defined
        if not display_key:
            key_name = ''
        elif key in self.fields_description and 'short_name' in self.fields_description[key]:
            key_name = self.fields_description[key]['short_name']
        else:
            key_name = key

        # Check if unit is defined and get the short unit char in the unit_sort dict
        if (
            key in self.fields_description
            and 'unit' in self.fields_description[key]
            and self.fields_description[key]['unit'] in fields_unit_short
        ):
            # Get the shortname
            unit_short = fields_unit_short[self.fields_description[key]['unit']]
        else:
            unit_short = ''

        # Check if unit is defined and get the unit type unit_type dict
        if (
            key in self.fields_description
            and 'unit' in self.fields_description[key]
            and self.fields_description[key]['unit'] in fields_unit_type
        ):
            # Get the shortname
            unit_type = fields_unit_type[self.fields_description[key]['unit']]
        else:
            unit_type = 'float'

        # Is it a rate ? Yes, get the pre-computed rate value
        if key in self.fields_description and self.fields_description[key].get('rate', False) is True:
            value = self.stats.get(key + '_rate_per_sec', None)
        else:
            value = self.stats.get(key, None)

        if width is None:
            msg_item = header + f'{key_name}' + separator
            msg_template_float = '{:.1f}{}'
            msg_template = '{}{}'
        else:
            # Define the size of the message
            # item will be on the left
            # value will be on the right
            msg_item = header + '{:{width}}'.format(key_name, width=width - 7) + separator
            msg_template_float = '{:5.1f}{}'
            msg_template = '{:>5}{}'

        if value is None:
            msg_value = msg_template.format('-', '')
        elif unit_type == 'float':
            msg_value = msg_template_float.format(value, unit_short)
        elif 'min_symbol' in self.fields_description[key]:
            msg_value = msg_template.format(
                self.auto_unit(int(value), min_symbol=self.fields_description[key]['min_symbol']), unit_short
            )
        else:
            msg_value = msg_template.format(int(value), unit_short)

        # Add the trailer
        msg_value = msg_value + trailer

        decoration = self.get_views(key=key, option='decoration') if value is not None else 'DEFAULT'
        optional = self.get_views(key=key, option='optional')

        return [
            self.curse_add_line(msg_item, optional=optional),
            self.curse_add_line(msg_value, decoration=decoration, optional=optional),
        ]

    @property
    def align(self):
        """Get the curse align."""
        return self._align

    @align.setter
    def align(self, value):
        """Set the curse align.

        value: left, right, bottom.
        """
        self._align = value

    def auto_unit(self, number, low_precision=False, min_symbol='K', none_symbol='-'):
        """Return a nice human-readable string out of number."""
        return auto_unit(number, low_precision=low_precision, min_symbol=min_symbol, none_symbol=none_symbol)

    def trend_msg(self, trend, significant=1):
        """Return the trend message.

        Do not take into account if trend < significant
        """
        ret = '-'
        if trend is None:
            ret = ' '
        elif trend > significant:
            ret = unicode_message('ARROW_UP', self.args)
        elif trend < -significant:
            ret = unicode_message('ARROW_DOWN', self.args)
        return ret
