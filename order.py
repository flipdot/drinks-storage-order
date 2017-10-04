#!/usr/bin/env python3
# Manages orders for flipdot's drinks storage system

import datetime
import pypandoc
import random
import requests
import yaml
import os


CWD = os.path.dirname(os.path.realpath(__file__))
FILE_CACHE = os.path.join(CWD, 'cache.yaml')
FILE_CONFIG = os.path.join(CWD, 'config.yaml')
FILE_TEMPLATE = os.path.join(CWD, 'order_template.latex')
FILE_TMP = '/tmp/order.yaml'


def get_config():
    with open(FILE_CONFIG, 'r') as f:
        config = yaml.load(f)
    return config


def get_supply(config):
    r = requests.get(config.get('url_api'))
    if r.status_code != 200:
        return False
    supply = {}
    for drink in r.json().get('state').get('sensors').get('beverage_supply'):
        if drink.get('location') != 'cellar' or drink.get('unit') != 'crt':
            continue
        supply[drink.get('name')] = drink.get('value')
    return supply


def get_sample_supply(config, demand):
    supply = {}
    for k, v in demand.items():
        supply[k] = random.randint(0, v)

    return supply


def get_demand(config):
    return config.get('demand')


def get_diff(supply, demand):
    diff = {}
    for k, vd in demand.items():
        vs = supply.get(k)
        if not vs:
            diff[k] = vd
        else:
            diff[k] = vd - vs
    return diff


def get_order(diff):
    ret = {'order': {}}
    order = ret['order']
    for k, v in diff.items():
        if v <= 0:
            continue
        order[k] = v
    return ret


if __name__ == '__main__':
    config = get_config()
    demand = get_demand(config)
    # supply = get_supply(config)
    supply = get_sample_supply(config, demand)
    diff = get_diff(supply, demand)
    order = get_order(diff)

    supplier = config['template']['supplier']
    supplier_filename = supplier.split(' ')[1].lower().strip()
    file_out = '/tmp/{}-bestellung-{}.pdf'.format(
        datetime.date.today().isoformat(),
        supplier_filename,
    )

    # Write order data to temporary yaml file
    with open(FILE_TMP, 'w') as f:
        f.write('---\n')
        f.write(yaml.dump(order, default_flow_style=False))
        f.write('...\n')

    # Create order document
    output = pypandoc.convert_file(
        'empty.md', 'pdf',
        outputfile=file_out,
        extra_args=['-s',
                    '--template={}'.format(FILE_TEMPLATE),
                    FILE_TMP,
                    FILE_CACHE,
                    FILE_CONFIG,
                    ]
        )
    assert output == ''

    # Increment order id on success
    with open(FILE_CACHE, 'r+') as f:
        cache = yaml.load(f)
        cache['cache']['order_id'] += 1
        f.seek(0)
        f.write('---\n')
        f.write(yaml.dump(cache, default_flow_style=False))
        f.write('...\n')