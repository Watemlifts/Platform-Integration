"""Test Home Assistant template helper methods."""
import math
import random
from datetime import datetime
from unittest.mock import patch

import pytest
import pytz

import homeassistant.util.dt as dt_util
from homeassistant.components import group
from homeassistant.const import (LENGTH_METERS, MASS_GRAMS, MATCH_ALL,
                                 PRESSURE_PA, TEMP_CELSIUS, VOLUME_LITERS)
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import template
from homeassistant.util.unit_system import UnitSystem


def _set_up_units(hass):
    """Set up the tests."""
    hass.config.units = UnitSystem('custom', TEMP_CELSIUS,
                                   LENGTH_METERS, VOLUME_LITERS,
                                   MASS_GRAMS, PRESSURE_PA)


def render_to_info(hass, template_str, variables=None):
    """Create render info from template."""
    tmp = template.Template(template_str, hass)
    return tmp.async_render_to_info(variables)


def extract_entities(hass, template_str, variables=None):
    """Extract entities from a template."""
    info = render_to_info(hass, template_str, variables)
    # pylint: disable=protected-access
    assert not hasattr(info, '_domains')
    return info._entities


def assert_result_info(
        info, result, entities=None, domains=None, all_states=False):
    """Check result info."""
    assert info.result == result
    # pylint: disable=protected-access
    assert info._all_states == all_states
    assert info.filter_lifecycle('invalid_entity_name.somewhere') == all_states
    if entities is not None:
        assert info._entities == frozenset(entities)
        assert all([info.filter(entity) for entity in entities])
        assert not info.filter('invalid_entity_name.somewhere')
    else:
        assert not info._entities
    if domains is not None:
        assert info._domains == frozenset(domains)
        assert all([info.filter_lifecycle(domain + ".entity")
                    for domain in domains])
    else:
        assert not hasattr(info, '_domains')


def test_template_equality():
    """Test template comparison and hashing."""
    template_one = template.Template("{{ template_one }}")
    template_one_1 = template.Template("{{ template_" + "one }}")
    template_two = template.Template("{{ template_two }}")

    assert template_one == template_one_1
    assert template_one != template_two
    assert hash(template_one) == hash(template_one_1)
    assert hash(template_one) != hash(template_two)

    assert str(template_one_1) == 'Template("{{ template_one }}")'

    with pytest.raises(TypeError):
        template.Template(["{{ template_one }}"])


def test_invalid_template(hass):
    """Invalid template raises error."""
    tmpl = template.Template("{{", hass)

    with pytest.raises(TemplateError):
        tmpl.ensure_valid()

    with pytest.raises(TemplateError):
        tmpl.async_render()

    info = tmpl.async_render_to_info()
    with pytest.raises(TemplateError):
        assert info.result == "impossible"

    tmpl = template.Template("{{states(keyword)}}", hass)

    tmpl.ensure_valid()

    with pytest.raises(TemplateError):
        tmpl.async_render()


def test_referring_states_by_entity_id(hass):
    """Test referring states by entity id."""
    hass.states.async_set('test.object', 'happy')
    assert template.Template(
        '{{ states.test.object.state }}', hass).async_render() == 'happy'

    assert template.Template(
        '{{ states["test.object"].state }}',
        hass).async_render() == 'happy'

    assert template.Template(
        '{{ states("test.object") }}', hass).async_render() == 'happy'


def test_invalid_entity_id(hass):
    """Test referring states by entity id."""
    with pytest.raises(TemplateError):
        template.Template(
            '{{ states["big.fat..."] }}', hass).async_render()
    with pytest.raises(TemplateError):
        template.Template(
            '{{ states.test["big.fat..."] }}', hass).async_render()
    with pytest.raises(TemplateError):
        template.Template(
            '{{ states["invalid/domain"] }}', hass).async_render()


def test_raise_exception_on_error(hass):
    """Test raising an exception on error."""
    with pytest.raises(TemplateError):
        template.Template('{{ invalid_syntax').ensure_valid()


def test_iterating_all_states(hass):
    """Test iterating all states."""
    tmpl_str = '{% for state in states %}{{ state.state }}{% endfor %}'

    info = render_to_info(hass, tmpl_str)
    assert_result_info(info, '', all_states=True)

    hass.states.async_set('test.object', 'happy')
    hass.states.async_set('sensor.temperature', 10)

    info = render_to_info(hass, tmpl_str)
    assert_result_info(
        info, '10happy',
        entities=['test.object', 'sensor.temperature'],
        all_states=True)


def test_iterating_domain_states(hass):
    """Test iterating domain states."""
    tmpl_str = \
        "{% for state in states.sensor %}" \
        "{{ state.state }}{% endfor %}"

    info = render_to_info(hass, tmpl_str)
    assert_result_info(info, '', domains=['sensor'])

    hass.states.async_set('test.object', 'happy')
    hass.states.async_set('sensor.back_door', 'open')
    hass.states.async_set('sensor.temperature', 10)

    info = render_to_info(hass, tmpl_str)
    assert_result_info(
        info, 'open10',
        entities=['sensor.back_door', 'sensor.temperature'],
        domains=['sensor'])


def test_float(hass):
    """Test float."""
    hass.states.async_set('sensor.temperature', '12')

    assert template.Template(
        '{{ float(states.sensor.temperature.state) }}',
        hass).async_render() == '12.0'

    assert template.Template(
        '{{ float(states.sensor.temperature.state) > 11 }}',
        hass).async_render() == 'True'

    assert template.Template(
        '{{ float(\'forgiving\') }}',
        hass).async_render() == 'forgiving'


def test_rounding_value(hass):
    """Test rounding value."""
    hass.states.async_set('sensor.temperature', 12.78)

    assert template.Template(
        '{{ states.sensor.temperature.state | round(1) }}',
        hass).async_render() == '12.8'

    assert template.Template(
        '{{ states.sensor.temperature.state | multiply(10) | round }}',
        hass).async_render() == '128'

    assert template.Template(
        '{{ states.sensor.temperature.state | round(1, "floor") }}',
        hass).async_render() == '12.7'

    assert template.Template(
        '{{ states.sensor.temperature.state | round(1, "ceil") }}',
        hass).async_render() == '12.8'


def test_rounding_value_get_original_value_on_error(hass):
    """Test rounding value get original value on error."""
    assert template.Template('{{ None | round }}', hass).async_render() == \
        'None'

    assert template.Template(
        '{{ "no_number" | round }}', hass).async_render() == 'no_number'


def test_multiply(hass):
    """Test multiply."""
    tests = {
        None: 'None',
        10: '100',
        '"abcd"': 'abcd'
    }

    for inp, out in tests.items():
        assert template.Template('{{ %s | multiply(10) | round }}' % inp,
                                 hass).async_render() == out


def test_logarithm(hass):
    """Test logarithm."""
    tests = [
        (4, 2, '2.0'),
        (1000, 10, '3.0'),
        (math.e, '', '1.0'),
        ('"invalid"', '_', 'invalid'),
        (10, '"invalid"', '10.0'),
    ]

    for value, base, expected in tests:
        assert template.Template(
            '{{ %s | log(%s) | round(1) }}' % (value, base),
            hass).async_render() == expected

        assert template.Template(
            '{{ log(%s, %s) | round(1) }}' % (value, base),
            hass).async_render() == expected


def test_sine(hass):
    """Test sine."""
    tests = [
        (0, '0.0'),
        (math.pi / 2, '1.0'),
        (math.pi, '0.0'),
        (math.pi * 1.5, '-1.0'),
        (math.pi / 10, '0.309'),
        ('"duck"', 'duck'),
    ]

    for value, expected in tests:
        assert template.Template(
            '{{ %s | sin | round(3) }}' % value,
            hass).async_render() == expected


def test_cos(hass):
    """Test cosine."""
    tests = [
        (0, '1.0'),
        (math.pi / 2, '0.0'),
        (math.pi, '-1.0'),
        (math.pi * 1.5, '-0.0'),
        (math.pi / 10, '0.951'),
        ("'error'", 'error'),
    ]

    for value, expected in tests:
        assert template.Template(
            '{{ %s | cos | round(3) }}' % value,
            hass).async_render() == expected


def test_tan(hass):
    """Test tangent."""
    tests = [
        (0, '0.0'),
        (math.pi, '-0.0'),
        (math.pi / 180 * 45, '1.0'),
        (math.pi / 180 * 90, '1.633123935319537e+16'),
        (math.pi / 180 * 135, '-1.0'),
        ("'error'", 'error'),
    ]

    for value, expected in tests:
        assert template.Template(
            '{{ %s | tan | round(3) }}' % value,
            hass).async_render() == expected


def test_sqrt(hass):
    """Test square root."""
    tests = [
        (0, '0.0'),
        (1, '1.0'),
        (2, '1.414'),
        (10, '3.162'),
        (100, '10.0'),
        ("'error'", 'error'),
    ]

    for value, expected in tests:
        assert template.Template(
            '{{ %s | sqrt | round(3) }}' % value,
            hass).async_render() == expected


def test_strptime(hass):
    """Test the parse timestamp method."""
    tests = [
        ('2016-10-19 15:22:05.588122 UTC',
         '%Y-%m-%d %H:%M:%S.%f %Z', None),
        ('2016-10-19 15:22:05.588122+0100',
         '%Y-%m-%d %H:%M:%S.%f%z', None),
        ('2016-10-19 15:22:05.588122',
         '%Y-%m-%d %H:%M:%S.%f', None),
        ('2016-10-19', '%Y-%m-%d', None),
        ('2016', '%Y', None),
        ('15:22:05', '%H:%M:%S', None),
        ('1469119144', '%Y', '1469119144'),
        ('invalid', '%Y', 'invalid')
    ]

    for inp, fmt, expected in tests:
        if expected is None:
            expected = datetime.strptime(inp, fmt)

        temp = '{{ strptime(\'%s\', \'%s\') }}' % (inp, fmt)

        assert template.Template(temp, hass).async_render() == str(expected)


def test_timestamp_custom(hass):
    """Test the timestamps to custom filter."""
    now = dt_util.utcnow()
    tests = [
        (None, None, None, 'None'),
        (1469119144, None, True, '2016-07-21 16:39:04'),
        (1469119144, '%Y', True, '2016'),
        (1469119144, 'invalid', True, 'invalid'),
        (dt_util.as_timestamp(now), None, False,
         now.strftime('%Y-%m-%d %H:%M:%S'))
    ]

    for inp, fmt, local, out in tests:
        if fmt:
            fil = 'timestamp_custom(\'{}\')'.format(fmt)
        elif fmt and local:
            fil = 'timestamp_custom(\'{0}\', {1})'.format(fmt, local)
        else:
            fil = 'timestamp_custom'

        assert template.Template(
            '{{ %s | %s }}' % (inp, fil), hass).async_render() == out


def test_timestamp_local(hass):
    """Test the timestamps to local filter."""
    tests = {
        None: 'None',
        1469119144: '2016-07-21 16:39:04',
    }

    for inp, out in tests.items():
        assert template.Template('{{ %s | timestamp_local }}' % inp,
                                 hass).async_render() == out


def test_min(hass):
    """Test the min filter."""
    assert template.Template('{{ [1, 2, 3] | min }}',
                             hass).async_render() == '1'


def test_max(hass):
    """Test the max filter."""
    assert template.Template('{{ [1, 2, 3] | max }}',
                             hass).async_render() == '3'


def test_base64_encode(hass):
    """Test the base64_encode filter."""
    assert template.Template('{{ "homeassistant" | base64_encode }}',
                             hass).async_render() == 'aG9tZWFzc2lzdGFudA=='


def test_base64_decode(hass):
    """Test the base64_decode filter."""
    assert template.Template('{{ "aG9tZWFzc2lzdGFudA==" | base64_decode }}',
                             hass).async_render() == 'homeassistant'


def test_ordinal(hass):
    """Test the ordinal filter."""
    tests = [
        (1, '1st'),
        (2, '2nd'),
        (3, '3rd'),
        (4, '4th'),
        (5, '5th'),
        (12, '12th'),
        (100, '100th'),
        (101, '101st'),
    ]

    for value, expected in tests:
        assert template.Template(
            '{{ %s | ordinal }}' % value,
            hass).async_render() == expected


def test_timestamp_utc(hass):
    """Test the timestamps to local filter."""
    now = dt_util.utcnow()
    tests = {
        None: 'None',
        1469119144: '2016-07-21 16:39:04',
        dt_util.as_timestamp(now):
            now.strftime('%Y-%m-%d %H:%M:%S')
    }

    for inp, out in tests.items():
        assert template.Template('{{ %s | timestamp_utc }}' % inp,
                                 hass).async_render() == out


def test_as_timestamp(hass):
    """Test the as_timestamp function."""
    assert template.Template('{{ as_timestamp("invalid") }}',
                             hass).async_render() == "None"
    hass.mock = None
    assert template.Template('{{ as_timestamp(states.mock) }}',
                             hass).async_render() == "None"

    tpl = '{{ as_timestamp(strptime("2024-02-03T09:10:24+0000", ' \
        '"%Y-%m-%dT%H:%M:%S%z")) }}'
    assert template.Template(tpl, hass).async_render() == "1706951424.0"


@patch.object(random, 'choice')
def test_random_every_time(test_choice, hass):
    """Ensure the random filter runs every time, not just once."""
    tpl = template.Template('{{ [1,2] | random }}', hass)
    test_choice.return_value = 'foo'
    assert tpl.async_render() == 'foo'
    test_choice.return_value = 'bar'
    assert tpl.async_render() == 'bar'


def test_passing_vars_as_keywords(hass):
    """Test passing variables as keywords."""
    assert template.Template(
        '{{ hello }}', hass).async_render(hello=127) == '127'


def test_passing_vars_as_vars(hass):
    """Test passing variables as variables."""
    assert template.Template(
        '{{ hello }}', hass).async_render({'hello': 127}) == '127'


def test_passing_vars_as_list(hass):
    """Test passing variables as list."""
    assert template.render_complex(
        template.Template('{{ hello }}',
                          hass), {'hello': ['foo', 'bar']}) == "['foo', 'bar']"


def test_passing_vars_as_list_element(hass):
    """Test passing variables as list."""
    assert template.render_complex(template.Template('{{ hello[1] }}',
                                                     hass),
                                   {'hello': ['foo', 'bar']}) == 'bar'


def test_passing_vars_as_dict_element(hass):
    """Test passing variables as list."""
    assert template.render_complex(template.Template('{{ hello.foo }}',
                                                     hass),
                                   {'hello': {'foo': 'bar'}}) == 'bar'


def test_passing_vars_as_dict(hass):
    """Test passing variables as list."""
    assert template.render_complex(
        template.Template('{{ hello }}',
                          hass), {'hello': {'foo': 'bar'}}) == "{'foo': 'bar'}"


def test_render_with_possible_json_value_with_valid_json(hass):
    """Render with possible JSON value with valid JSON."""
    tpl = template.Template('{{ value_json.hello }}', hass)
    assert tpl.async_render_with_possible_json_value(
        '{"hello": "world"}') == 'world'


def test_render_with_possible_json_value_with_invalid_json(hass):
    """Render with possible JSON value with invalid JSON."""
    tpl = template.Template('{{ value_json }}', hass)
    assert tpl.async_render_with_possible_json_value('{ I AM NOT JSON }') == ''


def test_render_with_possible_json_value_with_template_error_value(hass):
    """Render with possible JSON value with template error value."""
    tpl = template.Template('{{ non_existing.variable }}', hass)
    assert tpl.async_render_with_possible_json_value('hello', '-') == '-'


def test_render_with_possible_json_value_with_missing_json_value(hass):
    """Render with possible JSON value with unknown JSON object."""
    tpl = template.Template('{{ value_json.goodbye }}', hass)
    assert tpl.async_render_with_possible_json_value(
        '{"hello": "world"}') == ''


def test_render_with_possible_json_value_valid_with_is_defined(hass):
    """Render with possible JSON value with known JSON object."""
    tpl = template.Template('{{ value_json.hello|is_defined }}', hass)
    assert tpl.async_render_with_possible_json_value(
        '{"hello": "world"}') == 'world'


def test_render_with_possible_json_value_undefined_json(hass):
    """Render with possible JSON value with unknown JSON object."""
    tpl = template.Template('{{ value_json.bye|is_defined }}', hass)
    assert tpl.async_render_with_possible_json_value(
        '{"hello": "world"}') == '{"hello": "world"}'


def test_render_with_possible_json_value_undefined_json_error_value(hass):
    """Render with possible JSON value with unknown JSON object."""
    tpl = template.Template('{{ value_json.bye|is_defined }}', hass)
    assert tpl.async_render_with_possible_json_value(
        '{"hello": "world"}', '') == ''


def test_render_with_possible_json_value_non_string_value(hass):
    """Render with possible JSON value with non-string value."""
    tpl = template.Template("""
{{ strptime(value~'+0000', '%Y-%m-%d %H:%M:%S%z') }}
        """, hass)
    value = datetime(2019, 1, 18, 12, 13, 14)
    expected = str(pytz.utc.localize(value))
    assert tpl.async_render_with_possible_json_value(value) == expected


def test_if_state_exists(hass):
    """Test if state exists works."""
    hass.states.async_set('test.object', 'available')
    tpl = template.Template(
        '{% if states.test.object %}exists{% else %}not exists{% endif %}',
        hass)
    assert tpl.async_render() == 'exists'


def test_is_state(hass):
    """Test is_state method."""
    hass.states.async_set('test.object', 'available')
    tpl = template.Template("""
{% if is_state("test.object", "available") %}yes{% else %}no{% endif %}
        """, hass)
    assert tpl.async_render() == 'yes'

    tpl = template.Template("""
{{ is_state("test.noobject", "available") }}
        """, hass)
    assert tpl.async_render() == 'False'


def test_is_state_attr(hass):
    """Test is_state_attr method."""
    hass.states.async_set('test.object', 'available', {'mode': 'on'})
    tpl = template.Template("""
{% if is_state_attr("test.object", "mode", "on") %}yes{% else %}no{% endif %}
            """, hass)
    assert tpl.async_render() == 'yes'

    tpl = template.Template("""
{{ is_state_attr("test.noobject", "mode", "on") }}
            """, hass)
    assert tpl.async_render() == 'False'


def test_state_attr(hass):
    """Test state_attr method."""
    hass.states.async_set('test.object', 'available', {'mode': 'on'})
    tpl = template.Template("""
{% if state_attr("test.object", "mode") == "on" %}yes{% else %}no{% endif %}
            """, hass)
    assert tpl.async_render() == 'yes'

    tpl = template.Template("""
{{ state_attr("test.noobject", "mode") == None }}
            """, hass)
    assert tpl.async_render() == 'True'


def test_states_function(hass):
    """Test using states as a function."""
    hass.states.async_set('test.object', 'available')
    tpl = template.Template('{{ states("test.object") }}', hass)
    assert tpl.async_render() == 'available'

    tpl2 = template.Template('{{ states("test.object2") }}', hass)
    assert tpl2.async_render() == 'unknown'


@patch('homeassistant.helpers.template.TemplateEnvironment.'
       'is_safe_callable', return_value=True)
def test_now(mock_is_safe, hass):
    """Test now method."""
    now = dt_util.now()
    with patch('homeassistant.util.dt.now', return_value=now):
        assert now.isoformat() == \
            template.Template('{{ now().isoformat() }}',
                              hass).async_render()


@patch('homeassistant.helpers.template.TemplateEnvironment.'
       'is_safe_callable', return_value=True)
def test_utcnow(mock_is_safe, hass):
    """Test utcnow method."""
    now = dt_util.utcnow()
    with patch('homeassistant.util.dt.utcnow', return_value=now):
        assert now.isoformat() == \
            template.Template('{{ utcnow().isoformat() }}',
                              hass).async_render()


def test_regex_match(hass):
    """Test regex_match method."""
    tpl = template.Template(r"""
{{ '123-456-7890' | regex_match('(\\d{3})-(\\d{3})-(\\d{4})') }}
            """, hass)
    assert tpl.async_render() == 'True'

    tpl = template.Template("""
{{ 'home assistant test' | regex_match('Home', True) }}
            """, hass)
    assert tpl.async_render() == 'True'

    tpl = template.Template("""
    {{ 'Another home assistant test' | regex_match('home') }}
                    """, hass)
    assert tpl.async_render() == 'False'

    tpl = template.Template("""
{{ ['home assistant test'] | regex_match('.*assist') }}
            """, hass)
    assert tpl.async_render() == 'True'


def test_regex_search(hass):
    """Test regex_search method."""
    tpl = template.Template(r"""
{{ '123-456-7890' | regex_search('(\\d{3})-(\\d{3})-(\\d{4})') }}
            """, hass)
    assert tpl.async_render() == 'True'

    tpl = template.Template("""
{{ 'home assistant test' | regex_search('Home', True) }}
            """, hass)
    assert tpl.async_render() == 'True'

    tpl = template.Template("""
    {{ 'Another home assistant test' | regex_search('home') }}
                    """, hass)
    assert tpl.async_render() == 'True'

    tpl = template.Template("""
{{ ['home assistant test'] | regex_search('assist') }}
            """, hass)
    assert tpl.async_render() == 'True'


def test_regex_replace(hass):
    """Test regex_replace method."""
    tpl = template.Template(r"""
{{ 'Hello World' | regex_replace('(Hello\\s)',) }}
            """, hass)
    assert tpl.async_render() == 'World'

    tpl = template.Template("""
{{ ['home hinderant test'] | regex_replace('hinder', 'assist') }}
            """, hass)
    assert tpl.async_render() == "['home assistant test']"


def test_regex_findall_index(hass):
    """Test regex_findall_index method."""
    tpl = template.Template("""
{{ 'Flight from JFK to LHR' | regex_findall_index('([A-Z]{3})', 0) }}
            """, hass)
    assert tpl.async_render() == 'JFK'

    tpl = template.Template("""
{{ 'Flight from JFK to LHR' | regex_findall_index('([A-Z]{3})', 1) }}
            """, hass)
    assert tpl.async_render() == 'LHR'

    tpl = template.Template("""
{{ ['JFK', 'LHR'] | regex_findall_index('([A-Z]{3})', 1) }}
            """, hass)
    assert tpl.async_render() == 'LHR'


def test_bitwise_and(hass):
    """Test bitwise_and method."""
    tpl = template.Template("""
{{ 8 | bitwise_and(8) }}
            """, hass)
    assert tpl.async_render() == str(8 & 8)
    tpl = template.Template("""
{{ 10 | bitwise_and(2) }}
            """, hass)
    assert tpl.async_render() == str(10 & 2)
    tpl = template.Template("""
{{ 8 | bitwise_and(2) }}
            """, hass)
    assert tpl.async_render() == str(8 & 2)


def test_bitwise_or(hass):
    """Test bitwise_or method."""
    tpl = template.Template("""
{{ 8 | bitwise_or(8) }}
            """, hass)
    assert tpl.async_render() == str(8 | 8)
    tpl = template.Template("""
{{ 10 | bitwise_or(2) }}
            """, hass)
    assert tpl.async_render() == str(10 | 2)
    tpl = template.Template("""
{{ 8 | bitwise_or(2) }}
            """, hass)
    assert tpl.async_render() == str(8 | 2)


def test_distance_function_with_1_state(hass):
    """Test distance function with 1 state."""
    _set_up_units(hass)
    hass.states.async_set('test.object', 'happy', {
        'latitude': 32.87336,
        'longitude': -117.22943,
    })
    tpl = template.Template('{{ distance(states.test.object) | round }}',
                            hass)
    assert tpl.async_render() == '187'


def test_distance_function_with_2_states(hass):
    """Test distance function with 2 states."""
    _set_up_units(hass)
    hass.states.async_set('test.object', 'happy', {
        'latitude': 32.87336,
        'longitude': -117.22943,
    })
    hass.states.async_set('test.object_2', 'happy', {
        'latitude': hass.config.latitude,
        'longitude': hass.config.longitude,
    })
    tpl = template.Template(
        '{{ distance(states.test.object, states.test.object_2) | round }}',
        hass)
    assert tpl.async_render() == '187'


def test_distance_function_with_1_coord(hass):
    """Test distance function with 1 coord."""
    _set_up_units(hass)
    tpl = template.Template(
        '{{ distance("32.87336", "-117.22943") | round }}', hass)
    assert tpl.async_render() == '187'


def test_distance_function_with_2_coords(hass):
    """Test distance function with 2 coords."""
    _set_up_units(hass)
    assert template.Template(
        '{{ distance("32.87336", "-117.22943", %s, %s) | round }}'
        % (hass.config.latitude, hass.config.longitude),
        hass).async_render() == '187'


def test_distance_function_with_1_state_1_coord(hass):
    """Test distance function with 1 state 1 coord."""
    _set_up_units(hass)
    hass.states.async_set('test.object_2', 'happy', {
        'latitude': hass.config.latitude,
        'longitude': hass.config.longitude,
    })
    tpl = template.Template(
        '{{ distance("32.87336", "-117.22943", states.test.object_2) '
        '| round }}', hass)
    assert tpl.async_render() == '187'

    tpl2 = template.Template(
        '{{ distance(states.test.object_2, "32.87336", "-117.22943") '
        '| round }}', hass)
    assert tpl2.async_render() == '187'


def test_distance_function_return_none_if_invalid_state(hass):
    """Test distance function return None if invalid state."""
    hass.states.async_set('test.object_2', 'happy', {
        'latitude': 10,
    })
    tpl = template.Template('{{ distance(states.test.object_2) | round }}',
                            hass)
    assert tpl.async_render() == 'None'


def test_distance_function_return_none_if_invalid_coord(hass):
    """Test distance function return None if invalid coord."""
    assert template.Template(
        '{{ distance("123", "abc") }}', hass).async_render() == 'None'

    assert template.Template('{{ distance("123") }}', hass).async_render() == \
        'None'

    hass.states.async_set('test.object_2', 'happy', {
        'latitude': hass.config.latitude,
        'longitude': hass.config.longitude,
    })
    tpl = template.Template('{{ distance("123", states.test_object_2) }}',
                            hass)
    assert tpl.async_render() == 'None'


def test_distance_function_with_2_entity_ids(hass):
    """Test distance function with 2 entity ids."""
    _set_up_units(hass)
    hass.states.async_set('test.object', 'happy', {
        'latitude': 32.87336,
        'longitude': -117.22943,
    })
    hass.states.async_set('test.object_2', 'happy', {
        'latitude': hass.config.latitude,
        'longitude': hass.config.longitude,
    })
    tpl = template.Template(
        '{{ distance("test.object", "test.object_2") | round }}',
        hass)
    assert tpl.async_render() == '187'


def test_distance_function_with_1_entity_1_coord(hass):
    """Test distance function with 1 entity_id and 1 coord."""
    _set_up_units(hass)
    hass.states.async_set('test.object', 'happy', {
        'latitude': hass.config.latitude,
        'longitude': hass.config.longitude,
    })
    tpl = template.Template(
        '{{ distance("test.object", "32.87336", "-117.22943") | round }}',
        hass)
    assert tpl.async_render() == '187'


def test_closest_function_home_vs_domain(hass):
    """Test closest function home vs domain."""
    hass.states.async_set('test_domain.object', 'happy', {
        'latitude': hass.config.latitude + 0.1,
        'longitude': hass.config.longitude + 0.1,
    })

    hass.states.async_set('not_test_domain.but_closer', 'happy', {
        'latitude': hass.config.latitude,
        'longitude': hass.config.longitude,
    })

    assert template.Template('{{ closest(states.test_domain).entity_id }}',
                             hass).async_render() == 'test_domain.object'

    assert template.Template('{{ (states.test_domain | closest).entity_id }}',
                             hass).async_render() == 'test_domain.object'


def test_closest_function_home_vs_all_states(hass):
    """Test closest function home vs all states."""
    hass.states.async_set('test_domain.object', 'happy', {
        'latitude': hass.config.latitude + 0.1,
        'longitude': hass.config.longitude + 0.1,
    })

    hass.states.async_set('test_domain_2.and_closer', 'happy', {
        'latitude': hass.config.latitude,
        'longitude': hass.config.longitude,
    })

    assert template.Template('{{ closest(states).entity_id }}',
                             hass).async_render() == 'test_domain_2.and_closer'

    assert template.Template('{{ (states | closest).entity_id }}',
                             hass).async_render() == 'test_domain_2.and_closer'


async def test_closest_function_home_vs_group_entity_id(hass):
    """Test closest function home vs group entity id."""
    hass.states.async_set('test_domain.object', 'happy', {
        'latitude': hass.config.latitude + 0.1,
        'longitude': hass.config.longitude + 0.1,
    })

    hass.states.async_set('not_in_group.but_closer', 'happy', {
        'latitude': hass.config.latitude,
        'longitude': hass.config.longitude,
    })

    await group.Group.async_create_group(
        hass, 'location group', ['test_domain.object'])

    info = render_to_info(
        hass, '{{ closest("group.location_group").entity_id }}')
    assert_result_info(info, 'test_domain.object', [
        'test_domain.object', 'group.location_group'])


async def test_closest_function_home_vs_group_state(hass):
    """Test closest function home vs group state."""
    hass.states.async_set('test_domain.object', 'happy', {
        'latitude': hass.config.latitude + 0.1,
        'longitude': hass.config.longitude + 0.1,
    })

    hass.states.async_set('not_in_group.but_closer', 'happy', {
        'latitude': hass.config.latitude,
        'longitude': hass.config.longitude,
    })

    await group.Group.async_create_group(
        hass, 'location group', ['test_domain.object'])

    info = render_to_info(
        hass, '{{ closest("group.location_group").entity_id }}')
    assert_result_info(
        info, 'test_domain.object',
        ['test_domain.object', 'group.location_group'])

    info = render_to_info(
        hass, '{{ closest(states.group.location_group).entity_id }}')
    assert_result_info(
        info, 'test_domain.object',
        ['test_domain.object', 'group.location_group'])


async def test_expand(hass):
    """Test expand function."""
    info = render_to_info(
        hass, "{{ expand('test.object') }}")
    assert_result_info(
        info, '[]',
        ['test.object'])

    info = render_to_info(
        hass, "{{ expand(56) }}")
    assert_result_info(
        info, '[]')

    hass.states.async_set('test.object', 'happy')

    info = render_to_info(
        hass, "{{ expand('test.object') | map(attribute='entity_id')"
        " | join(', ') }}")
    assert_result_info(
        info, 'test.object',
        [])

    info = render_to_info(
        hass, "{{ expand('group.new_group') | map(attribute='entity_id')"
        " | join(', ') }}")
    assert_result_info(
        info, '',
        ['group.new_group'])

    info = render_to_info(
        hass, "{{ expand(states.group) | map(attribute='entity_id')"
        " | join(', ') }}")
    assert_result_info(
        info, '',
        [], ['group'])

    await group.Group.async_create_group(
        hass, 'new group', ['test.object'])

    info = render_to_info(
        hass, "{{ expand('group.new_group') | map(attribute='entity_id')"
        " | join(', ') }}")
    assert_result_info(
        info, 'test.object',
        ['group.new_group'])

    info = render_to_info(
        hass, "{{ expand(states.group) | map(attribute='entity_id')"
        " | join(', ') }}")
    assert_result_info(
        info, 'test.object',
        ['group.new_group'], ['group'])

    info = render_to_info(
        hass, "{{ expand('group.new_group', 'test.object')"
        " | map(attribute='entity_id') | join(', ') }}")
    assert_result_info(
        info, 'test.object',
        ['group.new_group'])

    info = render_to_info(
        hass, "{{ ['group.new_group', 'test.object'] | expand"
        " | map(attribute='entity_id') | join(', ') }}")
    assert_result_info(
        info, 'test.object',
        ['group.new_group'])


def test_closest_function_to_coord(hass):
    """Test closest function to coord."""
    hass.states.async_set('test_domain.closest_home', 'happy', {
        'latitude': hass.config.latitude + 0.1,
        'longitude': hass.config.longitude + 0.1,
    })

    hass.states.async_set('test_domain.closest_zone', 'happy', {
        'latitude': hass.config.latitude + 0.2,
        'longitude': hass.config.longitude + 0.2,
    })

    hass.states.async_set('zone.far_away', 'zoning', {
        'latitude': hass.config.latitude + 0.3,
        'longitude': hass.config.longitude + 0.3,
    })

    tpl = template.Template(
        '{{ closest("%s", %s, states.test_domain).entity_id }}'
        % (hass.config.latitude + 0.3,
           hass.config.longitude + 0.3), hass)

    assert tpl.async_render() == 'test_domain.closest_zone'

    tpl = template.Template(
        '{{ (states.test_domain | closest("%s", %s)).entity_id }}'
        % (hass.config.latitude + 0.3,
           hass.config.longitude + 0.3), hass)

    assert tpl.async_render() == 'test_domain.closest_zone'


def test_closest_function_to_entity_id(hass):
    """Test closest function to entity id."""
    hass.states.async_set('test_domain.closest_home', 'happy', {
        'latitude': hass.config.latitude + 0.1,
        'longitude': hass.config.longitude + 0.1,
    })

    hass.states.async_set('test_domain.closest_zone', 'happy', {
        'latitude': hass.config.latitude + 0.2,
        'longitude': hass.config.longitude + 0.2,
    })

    hass.states.async_set('zone.far_away', 'zoning', {
        'latitude': hass.config.latitude + 0.3,
        'longitude': hass.config.longitude + 0.3,
    })

    info = render_to_info(
        hass,
        '{{ closest(zone, states.test_domain).entity_id }}',
        {
            'zone': 'zone.far_away'
        })

    assert_result_info(
        info, 'test_domain.closest_zone',
        ['test_domain.closest_home', 'test_domain.closest_zone',
         'zone.far_away'],
        ["test_domain"])

    info = render_to_info(
        hass,
        "{{ ([states.test_domain, 'test_domain.closest_zone'] "
        "| closest(zone)).entity_id }}",
        {
            'zone': 'zone.far_away'
        })

    assert_result_info(
        info, 'test_domain.closest_zone',
        ['test_domain.closest_home', 'test_domain.closest_zone',
         'zone.far_away'],
        ["test_domain"])


def test_closest_function_to_state(hass):
    """Test closest function to state."""
    hass.states.async_set('test_domain.closest_home', 'happy', {
        'latitude': hass.config.latitude + 0.1,
        'longitude': hass.config.longitude + 0.1,
    })

    hass.states.async_set('test_domain.closest_zone', 'happy', {
        'latitude': hass.config.latitude + 0.2,
        'longitude': hass.config.longitude + 0.2,
    })

    hass.states.async_set('zone.far_away', 'zoning', {
        'latitude': hass.config.latitude + 0.3,
        'longitude': hass.config.longitude + 0.3,
    })

    assert template.Template(
        '{{ closest(states.zone.far_away, '
        'states.test_domain).entity_id }}', hass).async_render() == \
        'test_domain.closest_zone'


def test_closest_function_invalid_state(hass):
    """Test closest function invalid state."""
    hass.states.async_set('test_domain.closest_home', 'happy', {
        'latitude': hass.config.latitude + 0.1,
        'longitude': hass.config.longitude + 0.1,
    })

    for state in ('states.zone.non_existing', '"zone.non_existing"'):
        assert template.Template('{{ closest(%s, states) }}' % state,
                                 hass).async_render() == 'None'


def test_closest_function_state_with_invalid_location(hass):
    """Test closest function state with invalid location."""
    hass.states.async_set('test_domain.closest_home', 'happy', {
        'latitude': 'invalid latitude',
        'longitude': hass.config.longitude + 0.1,
    })

    assert template.Template(
                '{{ closest(states.test_domain.closest_home, '
                'states) }}', hass).async_render() == 'None'


def test_closest_function_invalid_coordinates(hass):
    """Test closest function invalid coordinates."""
    hass.states.async_set('test_domain.closest_home', 'happy', {
        'latitude': hass.config.latitude + 0.1,
        'longitude': hass.config.longitude + 0.1,
    })

    assert template.Template('{{ closest("invalid", "coord", states) }}',
                             hass).async_render() == 'None'
    assert template.Template('{{ states | closest("invalid", "coord") }}',
                             hass).async_render() == 'None'


def test_closest_function_no_location_states(hass):
    """Test closest function without location states."""
    assert template.Template('{{ closest(states).entity_id }}',
                             hass).async_render() == ''


def test_extract_entities_none_exclude_stuff(hass):
    """Test extract entities function with none or exclude stuff."""
    assert template.extract_entities(None) == []

    assert template.extract_entities("mdi:water") == []

    assert template.extract_entities(
        '{{ closest(states.zone.far_away, '
        'states.test_domain).entity_id }}') == MATCH_ALL

    assert template.extract_entities(
        '{{ distance("123", states.test_object_2) }}') == MATCH_ALL


def test_extract_entities_no_match_entities(hass):
    """Test extract entities function with none entities stuff."""
    assert template.extract_entities(
        "{{ value_json.tst | timestamp_custom('%Y' True) }}") == MATCH_ALL

    info = render_to_info(hass, """
{% for state in states.sensor %}
{{ state.entity_id }}={{ state.state }},d
{% endfor %}
            """)
    assert_result_info(info, '', domains=['sensor'])


def test_generate_filter_iterators(hass):
    """Test extract entities function with none entities stuff."""
    info = render_to_info(hass, """
        {% for state in states %}
        {{ state.entity_id }}
        {% endfor %}
        """)
    assert_result_info(info, '', all_states=True)

    info = render_to_info(hass, """
        {% for state in states.sensor %}
        {{ state.entity_id }}
        {% endfor %}
        """)
    assert_result_info(info, '', domains=['sensor'])

    hass.states.async_set('sensor.test_sensor', 'off', {
        'attr': 'value'})

    # Don't need the entity because the state is not accessed
    info = render_to_info(hass, """
        {% for state in states.sensor %}
        {{ state.entity_id }}
        {% endfor %}
        """)
    assert_result_info(info, 'sensor.test_sensor', domains=['sensor'])

    # But we do here because the state gets accessed
    info = render_to_info(hass, """
        {% for state in states.sensor %}
        {{ state.entity_id }}={{ state.state }},
        {% endfor %}
        """)
    assert_result_info(
        info, 'sensor.test_sensor=off,',
        ['sensor.test_sensor'],
        ['sensor'])

    info = render_to_info(hass, """
        {% for state in states.sensor %}
        {{ state.entity_id }}={{ state.attributes.attr }},
        {% endfor %}
        """)
    assert_result_info(
        info, 'sensor.test_sensor=value,',
        ['sensor.test_sensor'],
        ['sensor'])


def test_generate_select(hass):
    """Test extract entities function with none entities stuff."""
    template_str = """
{{ states.sensor|selectattr("state","equalto","off")
|join(",", attribute="entity_id") }}
        """

    tmp = template.Template(template_str, hass)
    info = tmp.async_render_to_info()
    assert_result_info(info, '', [], ['sensor'])

    hass.states.async_set('sensor.test_sensor', 'off', {
        'attr': 'value'})
    hass.states.async_set('sensor.test_sensor_on', 'on')

    info = tmp.async_render_to_info()
    assert_result_info(
        info, 'sensor.test_sensor',
        ['sensor.test_sensor', 'sensor.test_sensor_on'],
        ['sensor'])


def test_extract_entities_match_entities(hass):
    """Test extract entities function with entities stuff."""
    assert template.extract_entities("""
{% if is_state('device_tracker.phone_1', 'home') %}
Ha, Hercules is home!
{% else %}
Hercules is at {{ states('device_tracker.phone_1') }}.
{% endif %}
        """) == ['device_tracker.phone_1']

    assert template.extract_entities("""
{{ as_timestamp(states.binary_sensor.garage_door.last_changed) }}
        """) == ['binary_sensor.garage_door']

    assert template.extract_entities("""
{{ states("binary_sensor.garage_door") }}
        """) == ['binary_sensor.garage_door']

    hass.states.async_set('device_tracker.phone_2', 'not_home', {
        'battery': 20
    })

    assert template.extract_entities("""
{{ is_state_attr('device_tracker.phone_2', 'battery', 40) }}
        """) == ['device_tracker.phone_2']

    assert sorted([
        'device_tracker.phone_1',
        'device_tracker.phone_2',
        ]) == \
        sorted(template.extract_entities("""
{% if is_state('device_tracker.phone_1', 'home') %}
Ha, Hercules is home!
{% elif states.device_tracker.phone_2.attributes.battery < 40 %}
Hercules you power goes done!.
{% endif %}
        """))

    assert sorted([
        'sensor.pick_humidity',
        'sensor.pick_temperature',
        ]) == \
        sorted(template.extract_entities("""
{{
states.sensor.pick_temperature.state ~ „°C (“ ~
states.sensor.pick_humidity.state ~ „ %“
}}
        """))

    assert sorted([
        'sensor.luftfeuchtigkeit_mean',
        'input_number.luftfeuchtigkeit',
        ]) == \
        sorted(template.extract_entities(
            "{% if (states('sensor.luftfeuchtigkeit_mean') | int)"
            " > (states('input_number.luftfeuchtigkeit') | int +1.5)"
            " %}true{% endif %}"
        ))


def test_extract_entities_with_variables(hass):
    """Test extract entities function with variables and entities stuff."""
    hass.states.async_set('input_boolean.switch', 'on')
    assert {'input_boolean.switch'} == \
        extract_entities(
            hass, "{{ is_state('input_boolean.switch', 'off') }}", {})

    assert {'input_boolean.switch'} == extract_entities(
        hass, "{{ is_state(trigger.entity_id, 'off') }}", {
            'trigger': {
                'entity_id': 'input_boolean.switch'
            }
        })

    assert {'no_state'} == extract_entities(
        hass,
        "{{ is_state(data, 'off') }}", {
            'data': 'no_state'
        })

    assert {'input_boolean.switch'} == \
        extract_entities(
            hass,
            "{{ is_state(data, 'off') }}",
            {'data': 'input_boolean.switch'})

    assert {'input_boolean.switch'} == \
        extract_entities(
            hass,
            "{{ is_state(trigger.entity_id, 'off') }}",
            {'trigger': {'entity_id': 'input_boolean.switch'}})

    hass.states.async_set('media_player.livingroom', 'off')
    assert {'media_player.livingroom'} == \
        extract_entities(
            hass,
            "{{ is_state('media_player.' ~ where , 'playing') }}",
            {'where': 'livingroom'})


def test_jinja_namespace(hass):
    """Test Jinja's namespace command can be used."""
    test_template = template.Template(
        (
            "{% set ns = namespace(a_key='') %}"
            "{% set ns.a_key = states.sensor.dummy.state %}"
            "{{ ns.a_key }}"
        ),
        hass
    )

    hass.states.async_set('sensor.dummy', 'a value')
    assert test_template.async_render() == 'a value'

    hass.states.async_set('sensor.dummy', 'another value')
    assert test_template.async_render() == 'another value'


def test_state_with_unit(hass):
    """Test the state_with_unit property helper."""
    hass.states.async_set('sensor.test', '23', {
        'unit_of_measurement': 'beers',
    })
    hass.states.async_set('sensor.test2', 'wow')

    tpl = template.Template(
        '{{ states.sensor.test.state_with_unit }}', hass)

    assert tpl.async_render() == '23 beers'

    tpl = template.Template(
        '{{ states.sensor.test2.state_with_unit }}', hass)

    assert tpl.async_render() == 'wow'

    tpl = template.Template(
        '{% for state in states %}{{ state.state_with_unit }} {% endfor %}',
        hass)

    assert tpl.async_render() == '23 beers wow'

    tpl = template.Template('{{ states.sensor.non_existing.state_with_unit }}',
                            hass)

    assert tpl.async_render() == ''


def test_length_of_states(hass):
    """Test fetching the length of states."""
    hass.states.async_set('sensor.test', '23')
    hass.states.async_set('sensor.test2', 'wow')
    hass.states.async_set('climate.test2', 'cooling')

    tpl = template.Template('{{ states | length }}', hass)
    assert tpl.async_render() == '3'

    tpl = template.Template('{{ states.sensor | length }}', hass)
    assert tpl.async_render() == '2'
