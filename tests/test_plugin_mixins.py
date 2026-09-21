#!/usr/bin/env python
#
# Glances - An eye on your system
#
# SPDX-FileCopyrightText: 2024 Nicolas Hennion <nicolas@nicolargo.com>
#
# SPDX-License-Identifier: LGPL-3.0-only
#

"""Unit tests for the focused plugin mixins.

Each mixin implements a single responsibility and is tested in isolation
(no full GlancesPlugin instance, no psutil call). The composed
``GlancesPlugin`` and the deprecated ``GlancesPluginModel`` wrapper are
covered at the end of the file.
"""

import json
from types import SimpleNamespace

import pytest

from glances.plugins.plugin import (
    ActionMixin,
    GlancesPlugin,
    GlancesPluginModel,
    HistoryMixin,
    MMMMixin,
    SerializationMixin,
    StatsStorageMixin,
    ThresholdMixin,
    ViewMixin,
)


def make_args(disable_history=False, time=2):
    """Return a minimal args namespace."""
    return SimpleNamespace(disable_history=disable_history, time=time, disable_all=False)


class StorageOnly(StatsStorageMixin):
    """Plugin composed of the storage responsibility only."""


class SerializationOnly(StatsStorageMixin, SerializationMixin):
    """Plugin composed of the storage and serialization responsibilities."""


class TestStatsStorageMixin:
    """Stats read/write and reset responsibility."""

    def test_default_init_value_is_empty_dict(self):
        plugin = StorageOnly()
        plugin._init_storage()
        assert plugin.stats == {}
        assert plugin.stats_previous is None

    def test_init_value_can_be_a_list(self):
        plugin = StorageOnly()
        plugin._init_storage(stats_init_value=[])
        assert plugin.stats == []

    def test_reset_restore_a_copy_of_the_init_value(self):
        plugin = StorageOnly()
        plugin._init_storage(stats_init_value={'a': 1})
        plugin.stats['b'] = 2
        plugin.reset()
        assert plugin.stats == {'a': 1}

    def test_set_stats_and_mapping_accessors(self):
        plugin = StorageOnly()
        plugin._init_storage()
        plugin.set_stats({'cpu': 12.5})
        assert plugin.stats['cpu'] == 12.5
        assert plugin['cpu'] == 12.5
        assert plugin.get('missing', 0) == 0
        assert plugin.keys() == ['cpu']
        assert repr(plugin) and str(plugin)
        with pytest.raises(KeyError):
            plugin['nope']

    def test_list_stats_accessors(self):
        plugin = StorageOnly()
        plugin._init_storage(stats_init_value=[])
        plugin.set_stats(
            [
                {'key': 'interface_name', 'interface_name': 'eth0', 'rx': 1},
                {'key': 'interface_name', 'interface_name': 'eth1', 'rx': 2},
            ]
        )
        assert sorted(plugin.keys()) == ['eth0', 'eth1']
        assert plugin['eth0'] == {'key': 'interface_name', 'interface_name': 'eth0', 'rx': 1}

    def test_filter_stats(self):
        plugin = StorageOnly()
        plugin._init_storage()
        plugin.fields_description = {'a': {}, 'b': {}}
        assert plugin.filter_stats({'a': 1, 'z': 2}) == {'a': 1}
        assert plugin.filter_stats([{'a': 1, 'z': 2}]) == [{'a': 1}]
        assert plugin.filter_stats(42) == 42


class TestSerializationMixin:
    """JSON / export formatting responsibility."""

    def setup_method(self):
        self.plugin = SerializationOnly()
        self.plugin._init_storage()

    def test_get_raw_get_api_get_export_defaults(self):
        self.plugin.set_stats({'a': 1})
        assert self.plugin.get_raw() == {'a': 1}
        assert self.plugin.get_api() == {'a': 1}
        assert self.plugin.get_export() == {'a': 1}

    def test_get_json_returns_json_encoded_stats(self):
        self.plugin.set_stats({'a': 1})
        decoded = json.loads(self.plugin.get_json().decode('utf-8'))
        assert decoded == {'a': 1}

    def test_get_stats_item_and_value(self):
        self.plugin.set_stats([{'key': 'eth0', 'rx': 10}, {'key': 'eth1', 'rx': 20}])
        decoded = json.loads(self.plugin.get_stats_item('rx').decode('utf-8'))
        assert decoded == {'rx': [10, 20]}
        assert self.plugin.get_raw_stats_value('key', 'eth0') == {
            'eth0': [{'key': 'eth0', 'rx': 10}]
        }

    def test_get_raw_stats_value_returns_none_for_dict(self):
        self.plugin.set_stats({'a': 1})
        assert self.plugin.get_raw_stats_value('a', 1) is None

    def test_get_stats_value_json(self):
        self.plugin.set_stats([{'key': 'eth0', 'rx': 10}])
        decoded = json.loads(self.plugin.get_stats_value('key', 'eth0').decode('utf-8'))
        assert 'eth0' in decoded


class HistoryOnly(StatsStorageMixin, SerializationMixin, HistoryMixin):
    """Plugin composed of storage, serialization and history responsibilities."""

    plugin_name = 'historyonly'

    def __init__(self, args=None, items_history_list=None):
        self.args = args
        self._limits = {'history_size': 28800}
        self._init_storage(stats_init_value={})
        self._init_history(items_history_list=items_history_list)

    def get_key(self):
        return None


class TestHistoryMixin:
    """History data management responsibility."""

    def test_history_disabled_by_default_without_items(self):
        plugin = HistoryOnly(args=make_args())
        assert plugin.history_enable() is False
        assert plugin.get_raw_history() == {}

    def test_history_enable_requires_args_items_and_flag(self):
        items = [{'name': 'total', 'description': 'total cpu', 'value': 0}]
        plugin = HistoryOnly(args=make_args(), items_history_list=items)
        assert plugin.history_enable() is True
        plugin_disabled = HistoryOnly(args=make_args(disable_history=True), items_history_list=items)
        assert plugin_disabled.history_enable() is False

    def test_update_and_read_raw_history(self):
        items = [{'name': 'total', 'description': 'total cpu', 'value': 0}]
        plugin = HistoryOnly(args=make_args(), items_history_list=items)
        plugin.set_stats({'total': 10.0})
        plugin.update_stats_history()
        plugin.set_stats({'total': 20.0})
        plugin.update_stats_history()
        raw = plugin.get_raw_history(item='total')
        assert len(raw) == 2
        assert [v[1] for v in raw] == [10.0, 20.0]
        assert plugin.get_raw_history(item='missing') is None

    def test_history_for_list_of_stats(self):
        items = [{'name': 'rx', 'description': 'rx bytes', 'value': 0}]

        class ListHistory(HistoryOnly):
            def get_key(self):
                return 'key'

        plugin = ListHistory(args=make_args(), items_history_list=items)
        plugin.set_stats([{'key': 'eth0', 'rx': 1}, {'key': 'eth1', 'rx': 2}])
        plugin.update_stats_history()
        raw = plugin.get_raw_history()
        assert set(raw.keys()) == {'eth0_rx', 'eth1_rx'}

    def test_stats_history_json_and_trend(self):
        items = [{'name': 'total', 'description': 'total cpu', 'value': 0}]
        plugin = HistoryOnly(args=make_args(), items_history_list=items)
        for value in range(1, 41):
            plugin.set_stats({'total': float(value)})
            plugin.update_stats_history()
        decoded = json.loads(plugin.get_stats_history(item='total').decode('utf-8'))
        assert 'total' in decoded
        assert plugin.get_trend('total', nb=40) is not None
        assert plugin.get_trend('total', nb=40) > 0
        assert plugin.get_trend('missing', nb=40) is None

    def test_reset_stats_history(self):
        items = [{'name': 'total', 'description': 'total cpu', 'value': 0}]
        plugin = HistoryOnly(args=make_args(), items_history_list=items)
        plugin.set_stats({'total': 1.0})
        plugin.update_stats_history()
        assert plugin.get_raw_history(item='total')
        plugin.reset_stats_history()
        assert len(plugin.get_raw_history(item='total')) == 0


class ThresholdOnly(ThresholdMixin):
    """Plugin composed of the threshold responsibility only."""

    plugin_name = 'cpu'

    def __init__(self, args=None):
        self.args = args
        self._init_thresholds(config=_EmptyConfig())

    def get_key(self):
        return None


class _EmptyConfig:
    """Minimal configuration object exposing the API used by load_limits."""

    def has_section(self, section):
        return False


class TestThresholdMixin:
    """Threshold detection configuration responsibility."""

    def setup_method(self):
        self.plugin = ThresholdOnly(args=make_args())

    def test_default_history_size(self):
        assert self.plugin._limits['history_size'] == 28800

    def test_set_and_get_limits(self):
        self.plugin.set_limits('careful', 50)
        assert self.plugin.get_limits('careful') == 50
        assert self.plugin.get_limit('careful', stat_name='cpu') == 50

    def test_get_limit_fallback_on_plugin_name(self):
        self.plugin._limits['cpu_critical'] = 90
        assert self.plugin.get_limit('critical', stat_name='cpu_steal') == 90
        # Fallback on the plugin name: any cpu_* stat without a specific
        # limit uses the plugin-wide cpu_critical limit.
        assert self.plugin.get_limit('critical', stat_name='cpu_something_else') == 90
        # A non-cpu stat name without matching key returns None
        self.plugin.plugin_name = 'mem'
        assert self.plugin.get_limit('critical', stat_name='diskio') is None
        self.plugin.plugin_name = 'cpu'
        assert self.plugin.get_limit() is self.plugin._limits

    def test_get_stat_name(self):
        assert self.plugin.get_stat_name() == 'cpu'
        assert self.plugin.get_stat_name(header='steal') == 'cpu_steal'
        assert self.plugin.get_stat_name(header='x', action_key='y') == 'cpu_y_x'

    def test_get_limit_action_and_repeat(self):
        self.plugin._limits['cpu_careful_action'] = 'echo ok'
        action, repeat = self.plugin.get_limit_action('careful', stat_name='cpu')
        assert action == 'echo ok'
        assert repeat is False
        self.plugin._limits['cpu_critical_action_repeat'] = 'echo ko'
        action, repeat = self.plugin.get_limit_action('critical', stat_name='cpu')
        assert action == 'echo ko'
        assert repeat is True
        assert self.plugin.get_limit_action('warning', stat_name='cpu') == (None, None)

    def test_get_limit_log(self):
        assert self.plugin.get_limit_log('cpu') is False
        self.plugin._limits['cpu_log'] = ['True']
        assert self.plugin.get_limit_log('cpu') is True

    def test_refresh_rate(self):
        assert self.plugin.get_refresh() == 2
        self.plugin.set_refresh(5)
        assert self.plugin.get_refresh() == 5
        assert self.plugin.get_refresh_time() == 5

    def test_conf_value_show_hide_and_display(self):
        self.plugin._limits['diskio_hide'] = ['sda2', 'loop.*']
        assert self.plugin.plugin_name == 'cpu'
        self.plugin.plugin_name = 'diskio'
        self.plugin.alias = self.plugin.read_alias()
        assert self.plugin.is_hide('sda2') is True
        assert self.plugin.is_hide('sda1') is False
        assert self.plugin.is_display('sda1') is True
        self.plugin._limits['diskio_show'] = ['sda.*']
        assert self.plugin.is_display('sda1') is True
        assert self.plugin.is_display('nvme0') is False
        assert self.plugin.is_display_any('sda1', 'nvme0') is True

    def test_alias(self):
        self.plugin._limits['cpu_alias'] = ['eth0:lan']
        self.plugin.alias = self.plugin.read_alias()
        assert self.plugin.has_alias('ETH0') == 'lan'
        assert self.plugin.has_alias('wlan0') is None


class ActionOnly(StatsStorageMixin, SerializationMixin, ThresholdMixin, ActionMixin):
    """Plugin composed of the alert/action responsibility (plus its needs)."""

    plugin_name = 'cpu'

    def __init__(self, args=None):
        self.args = args
        self._init_thresholds(config=None)
        self._init_actions(args=args)
        self._init_storage(stats_init_value={})
        self.fields_description = None

    def get_key(self):
        return None


class TestActionMixin:
    """Threshold detection and alert action execution responsibility."""

    def setup_method(self):
        self.plugin = ActionOnly(args=make_args())

    def test_default_alert_without_limits(self):
        assert self.plugin.get_alert(50, maximum=100) == 'DEFAULT'

    def test_alert_levels(self):
        self.plugin._limits.update({'cpu_careful': 50, 'cpu_warning': 70, 'cpu_critical': 90})
        assert self.plugin.get_alert(40, maximum=100) == 'OK'
        assert self.plugin.get_alert(55, maximum=100) == 'CAREFUL'
        assert self.plugin.get_alert(75, maximum=100) == 'WARNING'
        assert self.plugin.get_alert(95, maximum=100) == 'CRITICAL'

    def test_alert_zero_not_highlighted(self):
        self.plugin._limits.update({'cpu_careful': 50})
        assert self.plugin.get_alert(0, maximum=100, highlight_zero=False) == 'DEFAULT'

    def test_alert_with_header_uses_specific_limit(self):
        self.plugin._limits['cpu_steal_careful'] = 10
        assert self.plugin.get_alert(20, maximum=100, header='steal') == 'CAREFUL'

    def test_alert_below_minimum(self):
        assert self.plugin.get_alert(-5, minimum=0, maximum=100) == 'CAREFUL'

    def test_alert_bad_type_returns_default(self):
        assert self.plugin.get_alert(None, maximum=100) == 'DEFAULT'
        assert self.plugin.get_alert(1, maximum=0) == 'DEFAULT'

    def test_get_alert_log_suffix(self, monkeypatch):
        self.plugin._limits.update({'cpu_warning': 70, 'cpu_log': ['true']})
        monkeypatch.setattr(self.plugin, 'manage_action', lambda *a, **kw: None)
        assert self.plugin.get_alert_log(80, maximum=100) == 'WARNING_LOG'

    def test_manage_threshold_records_event(self):
        from glances.thresholds import glances_thresholds

        self.plugin.manage_threshold('cpu_test_stat', 'WARNING')
        recorded = glances_thresholds.get('cpu_test_stat')
        assert recorded is not None
        assert recorded.description() == 'WARNING'

    def test_get_stats_action_defaults_to_stats(self):
        self.plugin.set_stats({'a': 1})
        assert self.plugin.get_stats_action() == {'a': 1}


class MMMOnly(MMMMixin):
    """Plugin composed of the Min/Max/Mean responsibility only."""

    def __init__(self, fields_description):
        self.fields_description = fields_description
        self._init_mmm()


class TestMMMMixin:
    """Min/Max/Mean computation responsibility."""

    def test_init_generates_field_descriptions(self):
        plugin = MMMOnly({'total': {'description': 'cpu total', 'unit': 'percent', 'mmm': True}})
        assert 'total_min' in plugin.fields_description
        assert 'total_max' in plugin.fields_description
        assert 'total_mean' in plugin.fields_description
        assert set(plugin._mmm_fields['total'].keys()) == {'values', 'min', 'max', 'unit'}

    def test_update_mmm_fields_dict(self):
        plugin = MMMOnly({'total': {'description': 'cpu total', 'unit': 'percent', 'mmm': True}})
        stats = {'total': 10.0}
        plugin._update_mmm_fields(stats)
        plugin._update_mmm_fields({'total': 30.0})
        out = {'total': 20.0}
        plugin._update_mmm_fields(out)
        assert out['total_min'] == 10.0
        assert out['total_max'] == 30.0
        assert out['total_mean'] == 20.0

    def test_update_mmm_ignores_none_and_non_numeric(self):
        plugin = MMMOnly({'total': {'description': 'cpu total', 'mmm': True}})
        stats = {'total': None}
        assert plugin._update_mmm_fields(stats) == {'total': None}
        stats = {'total': 'n/a'}
        assert plugin._update_mmm_fields(stats) == {'total': 'n/a'}
        assert plugin._mmm_fields['total']['min'] is None

    def test_update_mmm_fields_on_list(self):
        plugin = MMMOnly({'rx': {'description': 'rx', 'mmm': True}})
        data = [{'key': 'eth0', 'rx': 5}, {'key': 'eth0', 'rx': 15}]
        plugin._update_mmm_fields_on_list(data)
        assert data[0]['rx_min'] == 5
        assert data[1]['rx_max'] == 15

    def test_manage_mmm_decorator(self):
        class Plugin(MMMOnly):
            plugin_name = 'mmm'

            @MMMMixin._manage_mmm
            def update(self):
                return self.stats

        plugin = Plugin({'total': {'description': 't', 'mmm': True}})
        plugin.stats = {'total': 42.0}
        result = plugin.update()
        assert result['total_max'] == 42.0
        assert result['total_mean'] == 42.0


class ViewOnly(StatsStorageMixin, SerializationMixin, ThresholdMixin, ActionMixin, ViewMixin):
    """Plugin composed of the view responsibility (plus its needs)."""

    plugin_name = 'cpu'

    def __init__(self, args=None, fields_description=None):
        self.args = args
        self._init_thresholds(config=None)
        self._init_actions(args=args)
        self._init_storage(stats_init_value={})
        self.fields_description = fields_description
        self._init_view()

    def get_key(self):
        return None


class TestViewMixin:
    """View rendering responsibility."""

    def setup_method(self):
        self.fields = {
            'total': {'description': 'cpu total', 'unit': 'percent'},
            'nice': {'description': 'nice', 'unit': 'percent', 'optional': True},
        }
        self.plugin = ViewOnly(args=make_args(), fields_description=self.fields)

    def test_init_view_defaults(self):
        assert self.plugin.views == {}
        assert self.plugin.align == 'left'
        assert self.plugin.hide_zero is False
        self.plugin.align = 'right'
        assert self.plugin.align == 'right'

    def test_update_views_for_dict_stats(self):
        self.plugin.set_stats({'total': 12.5, 'nice': 0.0})
        views = self.plugin.update_views()
        assert views['total']['decoration'] == 'DEFAULT'
        assert views['total']['optional'] is False
        assert views['nice']['optional'] is True
        assert views['total']['hidden'] is False

    def test_update_views_for_list_stats(self):
        class ListView(ViewOnly):
            plugin_name = 'network'

            def get_key(self):
                return 'key'

        plugin = ListView(args=make_args(), fields_description={'rx': {'description': 'rx'}})
        plugin.set_stats([{'key': 'eth0', 'rx': 1}, {'key': 'eth1', 'rx': 2}])
        views = plugin.update_views()
        assert set(views.keys()) == {'eth0', 'eth1'}
        assert plugin.get_views(item='eth0', key='rx', option='decoration') == 'DEFAULT'
        assert plugin.get_views(item='eth0', key='missing') == 'DEFAULT'
        assert plugin.get_views(item='eth0', key='missing', option='x') == 'DEFAULT'

    def test_set_reset_and_json_views(self):
        self.plugin.set_views({'total': {'decoration': 'OK'}})
        assert self.plugin.get_views(key='total', option='decoration') == 'OK'
        decoded = json.loads(self.plugin.get_json_views().decode('utf-8'))
        assert decoded == {'total': {'decoration': 'OK'}}
        self.plugin.reset_views()
        assert self.plugin.views == {}

    def test_curse_helpers(self):
        line = self.plugin.curse_add_line('hello', decoration='BOLD', optional=True)
        assert line == {
            'msg': 'hello',
            'decoration': 'BOLD',
            'optional': True,
            'additional': False,
            'splittable': False,
        }
        assert self.plugin.curse_new_line()['msg'] == '\n'

    def test_curse_add_stat(self):
        self.plugin.set_stats({'total': 12.5})
        self.plugin.update_views()
        messages = self.plugin.curse_add_stat('total', header='  ')
        assert len(messages) == 2
        assert 'total' in messages[0]['msg']

    def test_curse_add_stat_unknown_key_returns_empty(self):
        self.plugin.set_stats({'total': 12.5})
        assert self.plugin.curse_add_stat('nope') == []

    def test_get_item_info(self):
        assert self.plugin.get_item_info('total', 'unit') == 'percent'
        assert self.plugin.get_item_info('nope', 'unit', default='?') == '?'

    def test_get_stats_display(self):
        ret = self.plugin.get_stats_display()
        assert ret['display'] is False
        assert 'msgdict' in ret
        assert ret['align'] == 'left'

    def test_auto_unit_and_trend_msg(self):
        assert self.plugin.auto_unit(1024)
        assert self.plugin.trend_msg(None) == ' '
        assert self.plugin.trend_msg(0) == '-'

    def test_msg_curse_default(self):
        self.plugin.set_stats({'total': 1})
        messages = self.plugin.msg_curse()
        assert isinstance(messages, list)
        assert messages[0]['msg'] == str(self.plugin.stats)


class TestComposedGlancesPlugin:
    """The composed base class wires every mixin together."""

    def test_all_mixins_are_part_of_mro(self):
        names = [c.__name__ for c in GlancesPlugin.__mro__]
        for mixin in (
            'StatsStorageMixin',
            'HistoryMixin',
            'ThresholdMixin',
            'ActionMixin',
            'MMMMixin',
            'ViewMixin',
            'SerializationMixin',
        ):
            assert mixin in names

    def test_full_plugin_lifecycle(self):
        class FullPlugin(GlancesPlugin):
            def __init__(self, args=None):
                super().__init__(
                    args=args,
                    config=_EmptyConfig(),
                    items_history_list=[{'name': 'total', 'description': 'cpu total', 'value': 0}],
                    stats_init_value={},
                    fields_description={'total': {'description': 'cpu total', 'unit': 'percent', 'mmm': True}},
                )

            @GlancesPlugin._manage_mmm
            def update(self):
                self.stats['total'] = 25.0
                return self.stats

        lifecycle_args = make_args()
        setattr(lifecycle_args, 'disable_test_plugin_mixins', False)
        plugin = FullPlugin(args=lifecycle_args)
        assert plugin.plugin_name == 'test_plugin_mixins'
        plugin.update()
        assert plugin.get_raw()['total'] == 25.0
        assert plugin.get_raw()['total_mean'] == 25.0
        plugin.update_stats_history()
        assert plugin.get_raw_history(item='total')
        plugin.update_views()
        assert plugin.get_views(key='total')['decoration'] == 'DEFAULT'
        json.loads(plugin.get_json().decode('utf-8'))
        assert plugin.get_export() == plugin.get_raw()
        assert plugin.input_method == 'local'
        plugin.input_method = 'snmp'
        assert plugin.input_method == 'snmp'
        plugin.exit()

    def test_decorators_are_available(self):
        assert callable(GlancesPlugin._check_decorator)
        assert callable(GlancesPlugin._log_result_decorator)
        assert callable(GlancesPlugin._manage_rate)
        assert callable(GlancesPlugin._manage_mmm)

    def test_enabled_disabled(self):
        class EnabledPlugin(GlancesPlugin):
            pass

        enabled_args = make_args()
        plugin = EnabledPlugin(args=enabled_args)
        setattr(enabled_args, 'disable_' + plugin.plugin_name, False)
        assert plugin.is_enabled() is True
        assert plugin.is_disabled() is False

        setattr(enabled_args, 'disable_' + plugin.plugin_name, True)
        assert plugin.is_enabled() is False
        assert plugin.is_disabled() is True


class TestBackwardCompatibility:
    """The historical import path and class name keep on working."""

    def test_glances_plugin_model_alias_import(self):
        from glances.plugins.plugin.model import GlancesPluginModel as LegacyModel

        assert LegacyModel is GlancesPluginModel

    def test_legacy_class_is_subclass_of_new_base(self):
        assert issubclass(GlancesPluginModel, GlancesPlugin)

    def test_legacy_class_can_be_instantiated_like_before(self):
        class LegacyPlugin(GlancesPluginModel):
            pass

        plugin = LegacyPlugin(args=make_args())
        assert isinstance(plugin, GlancesPlugin)
        # Public API surface relied upon by the REST API, curses UI and exporters
        for method in (
            'get_json',
            'get_export',
            'get_views',
            'get_raw_history',
            'get_stats_history',
            'get_raw',
            'get_api',
            'update_views',
            'reset',
            'get_alert',
            'get_limit',
            'get_trend',
        ):
            assert callable(getattr(plugin, method)), method

    def test_constants_still_importable_from_model(self):
        from glances.plugins.plugin import model

        assert model.fields_unit_short == {'percent': '%'}
        assert 'percent' in model.fields_unit_type
