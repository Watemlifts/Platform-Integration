"""Custom dumper and representers."""
from collections import OrderedDict
import yaml

from .objects import NodeListClass


def dump(_dict: dict) -> str:
    """Dump YAML to a string and remove null."""
    return yaml.safe_dump(
        _dict, default_flow_style=False, allow_unicode=True) \
        .replace(': null\n', ':\n')


def save_yaml(path: str, data: dict) -> None:
    """Save YAML to a file."""
    # Dump before writing to not truncate the file if dumping fails
    str_data = dump(data)
    with open(path, 'w', encoding='utf-8') as outfile:
        outfile.write(str_data)


# From: https://gist.github.com/miracle2k/3184458
# pylint: disable=redefined-outer-name
def represent_odict(dump, tag, mapping,  # type: ignore
                    flow_style=None) -> yaml.MappingNode:
    """Like BaseRepresenter.represent_mapping but does not issue the sort()."""
    value = []  # type: list
    node = yaml.MappingNode(tag, value, flow_style=flow_style)
    if dump.alias_key is not None:
        dump.represented_objects[dump.alias_key] = node
    best_style = True
    if hasattr(mapping, 'items'):
        mapping = mapping.items()
    for item_key, item_value in mapping:
        node_key = dump.represent_data(item_key)
        node_value = dump.represent_data(item_value)
        if not (isinstance(node_key, yaml.ScalarNode) and not node_key.style):
            best_style = False
        if not (isinstance(node_value, yaml.ScalarNode) and
                not node_value.style):
            best_style = False
        value.append((node_key, node_value))
    if flow_style is None:
        if dump.default_flow_style is not None:
            node.flow_style = dump.default_flow_style
        else:
            node.flow_style = best_style
    return node


yaml.SafeDumper.add_representer(
    OrderedDict,
    lambda dumper, value:
    represent_odict(dumper, 'tag:yaml.org,2002:map', value))

yaml.SafeDumper.add_representer(
    NodeListClass,
    lambda dumper, value:
    dumper.represent_sequence('tag:yaml.org,2002:seq', value))
