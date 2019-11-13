#!/usr/bin/env python3
# Manages orders for flipdot's drinks storage system

import datetime
import json
import os
import pypandoc
import random
import requests
import smtplib
import sys
import yaml

import dateutil.parser

from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from requests.exceptions import ConnectionError


CWD = os.path.dirname(os.path.realpath(__file__))
FILE_CACHE = os.path.join(CWD, 'cache.yaml')
FILE_CONFIG = os.path.join(CWD, 'config.yaml')
FILE_TEMPLATE = os.path.join(CWD, 'order_template.tex')
FILE_ORDER = '/tmp/order.yaml'
REQUESTS_TIMEOUT = 10


# https://stackoverflow.com/a/12343826
def max_key(d):
    """ a) create a list of the dict's keys and values;
        b) return the key with the max value"""
    v=list(d.values())
    k=list(d.keys())
    return k[v.index(max(v))]


def get_config():
    with open(FILE_CONFIG, 'r') as f:
        config = yaml.safe_load(f)
    return config


def get_supply(config):
    r = requests.get(config['url_api'])
    if r.status_code != 200:
        return False
    supply = {}
    timestamps = {}
    sensors = r.json().get('state').get('sensors')
    if not sensors.get('beverage_supply'):
        raise ValueError('Could not find beverage_supply data.')
    for drink in sensors.get('beverage_supply'):
        if drink['location'] != 'cellar' or drink['unit'] != 'crt':
            continue
        supply[drink['name']] = drink['value']
        timestamps[drink['name']] = dateutil.parser.parse(drink['ext_modified'])
    return supply, timestamps


def get_sample_supply(config, demand):
    supply = {}
    for k, v in demand.items():
        supply[k] = random.randint(0, v)

    return supply


def get_demand(config):
    return config['demand']


def get_diff(supply, demand, config):
    diff = {}
    missing = []
    for k, vd in demand.items():
        vs = None
        if k not in supply:
            missing.append(k)
        else:
            vs = supply[k]
        if not vs:
            diff[k] = vd
        else:
            diff[k] = vd - vs
        if diff[k] < 0:
            diff[k] = 0
    if len(missing) > 0:
        error = "The following crates have missing data: "
        error += ', '.join(missing)
        print(error)
        # Send IRC notification via webhook on failure
        print('Sending webhook alert... ', end='')
        if not send_webhook_alert(error, config):
            print('ERROR')
        else:
            print('OK')
        sys.exit(1)
    return diff


def get_order(diff):
    ret = {'order': {}}
    order = ret['order']
    for k, v in diff.items():
        if v <= 0:
            continue
        order[k] = v

    crate_count = sum(diff.values())
    order['total'] = crate_count
    return ret


def cap_order(order, max_crates):
    cap = order['order']
    cap['total'] = 0
    while sum(cap.values()) > max_crates:
        cap[max_key(cap)] -= 1

    cap['total'] = sum(cap.values())
    return order


def send_mail(config, cache, pdf_path):
    fqdn = config['mail']['server']['fqdn']
    port = config['mail']['server']['port']
    user = config['mail']['server']['user']
    password = config['mail']['server']['password']

    sender = '{} <{}>'.format(
        config['mail']['sender']['name'],
        config['mail']['sender']['address'],
    )
    recipient = '{} <{}>'.format(
        config['mail']['recipient']['name'],
        config['mail']['recipient']['address'],
    )
    cc = sender

    subject = '{}{} {}'.format(
        config['mail']['text']['subject1'],
        cache['cache']['order_id'],
        config['mail']['text']['subject2'],
    )
    body_text = config['mail']['text']['body']

    txt_attachment = MIMEText(body_text)

    with open(pdf_path, 'rb') as f:
        pdf_attachment = MIMEApplication(f.read(), 'pdf')

    # Construct MIME message
    msg = MIMEMultipart()
    msg.attach(txt_attachment)
    msg.attach(pdf_attachment)

    # Add additional headers
    msg['From'] = sender
    msg['To'] = recipient
    msg['CC'] = cc
    msg['Subject'] = subject

    # Initiate TLS connection
    mailer = smtplib.SMTP('{}:{}'.format(fqdn, port))
    mailer.starttls()

    # Login
    try:
        mailer.login(user, password)
    except smtplib.SMTPAuthenticationError as e:
        print("Error sending mail:\n  {}".format(e.smtp_error))
        sys.exit(1)

    # Actually send mail
    mailer.sendmail(sender, recipient, msg.as_string())
    mailer.quit()


def get_order_text(order, types, config, cache):

    order_text = ''
    for t in types:
        try:
            order_text += '{:2d} {}\n'.format(order['order'][t], t)
        except:
            pass

    order_text += '\n{:2d} TOTAL'.format(order['order']['total'])
    return order_text


def add_grafana_annotation(order_text, config, cache):
    # Order data
    order_id = cache['cache']['order_id']

    # Annotation specific data
    timestamp = int(datetime.datetime.now().timestamp() * 1000)  # Epoch * 1000
    ann_tags = ['Order', '№{}'.format(order_id)]
    ann_dashboard_id = config['grafana']['annotations']['dashboard_id']
    ann_panel_id = config['grafana']['annotations']['panel_id']
    ann_headers = {
        'content-type': 'application/json',
        'Authorization': 'Bearer {}'.format(config['grafana']['annotations']['api_key'])
        }

    ann_payload = {
        'dashboardId': ann_dashboard_id,
        'panelId': ann_panel_id,
        'time': timestamp,
        'tags': ann_tags,
        'text': order_text,
    }

    r = requests.post(
        config['grafana']['annotations']['url'],
        data=json.dumps(ann_payload),
        headers=ann_headers,
        timeout=REQUESTS_TIMEOUT,
    )

    if r.status_code != 200:
        return False
    return True

def send_webhook_alert(order_text, config):
    order_text = order_text.replace('\n\n', ', ').replace('\n', ', ').replace('  ', ' ')

    # Alert specific data
    alert_auth = config['grafana']['alerts']['auth']
    alert_headers = {
        'content-type': 'application/json',
        'Authorization': 'Basic {}'.format(alert_auth)
    }
    alert_payload = {
        'ruleName': 'Drinks order',
        'message': order_text,
        'state': 'alerting',
    }

    try:
        r = requests.post(
            config['grafana']['alerts']['url'],
            data=json.dumps(alert_payload),
            headers=alert_headers,
            timeout=REQUESTS_TIMEOUT,
        )

    except ConnectionError as e:
        return False

    if r.status_code != 200:
        return False
    return True


if __name__ == '__main__':
    # Print header for more convenience in logs
    print()
    print(datetime.datetime.now())

    config = get_config()

    # Check minimum wait
    with open(FILE_CACHE, 'r+') as f:
        cache = yaml.safe_load(f)
        last_date_str = cache['cache']['last_date']
        last_date = dateutil.parser.parse(last_date_str).date()
        now_date = datetime.date.today()
        diff_date = now_date - last_date
        wait_days = datetime.timedelta(days=config['wait_days'])

        if diff_date <= wait_days:
            print("The last order was {} days ago."
                  .format(diff_date.days))
            print("The earliest next order would be in {} days."
                  .format(abs(diff_date - wait_days).days))
            sys.exit(0)

    demand = get_demand(config)
    supply, timestamps = get_supply(config)
    diff = get_diff(supply, demand, config)
    order = get_order(diff)

    # Check if data is new enough
    now = datetime.datetime.now(datetime.timezone.utc)
    too_old = {}
    for k, v in timestamps.items():
        if (now - v).days > config['limits']['data_max_days']:
            too_old[k] = (now - v).days
    if len(too_old) > 0:
        error = "The following crates have data that is too old:\n"
        for k, v in too_old.items():
            error += "  {} ({} days)\n".format(k, v)
        print(error)
        # Send IRC notification via webhook on failure
        print('Sending webhook alert... ', end='')
        if not send_webhook_alert(error, config):
            print('ERROR')
        else:
            print('OK')
        sys.exit(0)

    # Check crate limits
    crate_count = sum(diff.values())
    min_crates = config['limits']['min_crates']
    max_crates = config['limits']['max_crates']
    if crate_count < min_crates:
        print("The order would consist of {} crates."
              .format(crate_count))
        print("This is below the lower limit of {} crates."
              .format(min_crates))
        sys.exit(0)
    if crate_count > max_crates:
        print("The order would consist of {} crates."
              .format(crate_count))
        print("This is above the upper limit of {} crates."
              .format(max_crates))
        order = cap_order(order, max_crates)
        print("Successfully successively lowered to match limit.")

    supplier = config['template']['supplier']
    supplier_filename = supplier.split(' ')[1].lower().strip()
    file_out = '/tmp/{}-bestellung-{}.pdf'.format(
        datetime.date.today().isoformat(),
        supplier_filename,
        )

    # Write order data to temporary yaml file
    with open(FILE_ORDER, 'w') as f:
        f.write('---\n')
        f.write(yaml.dump(order, default_flow_style=False))
        f.write('...\n')

    # Create order document
    print('Creating order as pdf... ', end='')
    sys.stdout.flush()
    output = pypandoc.convert_file(
        'empty.md', 'pdf',
        outputfile=file_out,
        extra_args=['-s',
                    '--template={}'.format(FILE_TEMPLATE),
                    FILE_ORDER,
                    FILE_CACHE,
                    FILE_CONFIG,
                    ]
        )
    assert output == ''
    print('OK')

    # Sent order via mail
    print('Sending test mail... ', end='')
    sys.stdout.flush()
    try:
        send_mail(config, cache, file_out)
    except Exception as e:
        print('ERROR\n')
        print(e)
        sys.exit(1)
    print('OK')

    # Create an annotation within the Grafana dashboard:
    # https://stats.flipdot.org/d/tpLhZnWiz/drinks-storage
    print('Creating dashboard annotation... ', end='')
    order_text = get_order_text(order, list(demand.keys()), config, cache)
    if not add_grafana_annotation(order_text, config, cache):
        print('ERROR')
    else:
        print('OK')

    # Abuse the webhook handler to create an alert which is then pasted to IRC
    print('Sending webhook alert... ', end='')
    if not send_webhook_alert('The following order has just been sent: {}'.format(order_text), config):
        print('ERROR')
    else:
        print('OK')

    # Increment order id on success
    print('Updating cache file... ', end='')
    sys.stdout.flush()
    with open(FILE_CACHE, 'r+') as f:
        # TODO Refactor
        cache = yaml.safe_load(f)
        cache['cache']['order_id'] += 1
        cache['cache']['last_date'] = datetime.date.today().isoformat()
        f.seek(0)
        f.write('---\n')
        f.write(yaml.dump(cache, default_flow_style=False))
        f.write('...\n')
    print('OK')

    # Remove temporary files
    os.remove(FILE_ORDER)
    os.remove(file_out)
