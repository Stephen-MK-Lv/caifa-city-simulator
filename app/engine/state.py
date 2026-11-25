"""JSON-only checkpoints; never unpickle browser or database contents."""
import copy
import random
from collections import defaultdict
from .legacy_city import City
from .jingzhou import JingzhouCity

ENGINE_VERSION = 'textbook-city-1.0-web-1'


def dump_city(city: City) -> dict:
    data = {k: copy.deepcopy(v) for k, v in city.__dict__.items()
            if k not in {'rng', 'journals', 'events', 'year_reports', 'seen', 'closed'}}
    data['rng_state'] = city.rng.getstate()
    data['closed'] = sorted(city.closed)
    data['schema_version'] = 1
    data['engine_version'] = ENGINE_VERSION
    return data


def tuple_tree(value):
    return tuple(tuple_tree(x) for x in value) if isinstance(value, list) else value


def load_city(data: dict, events: list, journals: list, reports: list) -> City:
    if data.get('schema_version') != 1 or data.get('engine_version') != ENGINE_VERSION:
        raise ValueError('账套规则版本不兼容，请先备份并迁移数据')
    profile = data.get('profile_id', 'textbook')
    if profile not in {'textbook', 'jingzhou2025'}:
        raise ValueError('未知仿真方案，请勿用旧版本打开新方案')
    cls = JingzhouCity if profile == 'jingzhou2025' else City
    city = cls.__new__(cls)
    city.__dict__.update(copy.deepcopy({k: v for k, v in data.items()
                                      if k not in {'rng_state', 'schema_version', 'engine_version'}}))
    city.rng = random.Random()
    city.rng.setstate(tuple_tree(data['rng_state']))
    city.closed = set(city.closed)
    city.ledger = {k: defaultdict(int, v) for k, v in city.ledger.items()}
    city.budget = {k: defaultdict(int, v) for k, v in city.budget.items()}
    city.stats = defaultdict(int, city.stats)
    city.spent = defaultdict(int, city.spent)
    city.events = copy.deepcopy(events)
    city.journals = copy.deepcopy(journals)
    city.year_reports = copy.deepcopy(reports)
    city.seen = {v['id'] for v in events}
    city.check()
    return city
