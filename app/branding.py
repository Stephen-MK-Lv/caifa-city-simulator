"""Display-name compatibility without modifying historical accounting records."""
import copy
from .engine import NAMES


def account_name(name):
    # Preserve custom names except their legacy city-name prefix.
    if name.startswith('明川市'):
        return '彩珐市'+name[3:]
    return '彩珐市'+name[2:] if name.startswith('明川') else name


def report_names(report):
    result = copy.deepcopy(report)
    for key, entity in result.get('entities', {}).items():
        if key in NAMES:
            entity['name'] = NAMES[key]
    return result


def command_result(result):
    result = copy.deepcopy(result)
    if 'simulation' in result:
        result['simulation']['name'] = account_name(result['simulation']['name'])
    return result
