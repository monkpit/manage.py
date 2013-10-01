# -*- coding: utf-8 -*-
import boto

from manager import Manager
from manager.ext.aws import connect


manager = Manager()


def get_namespace_key(path):
    """Gets namespace name and key for given path."""
    values = path.split('.')
    if len(values) == 1:
        return 'all', values[0]
    elif len(values) == 2:
        return values[0], values[1]
    raise Exception('Invalid key path')


def get_value(item, shorten=False):
    """Gets the value for given item.
    """
    lines = [item[key] for key in sorted(item)]
    if shorten:
        return lines[0]
    return '\n'.join(lines)


@manager.command
def set(path, value):
    """Sets a live config value for given path."""
    namespace, key = get_namespace_key(path)
    lines = value.splitlines()
    value = {}
    i = 0
    for line in lines:
        value["%03d" % i] = line
        i = i + 1
    conn = connect('sdb')
    try:
        domain = conn.get_domain(namespace)
    except boto.exception.SDBResponseError:
        domain = conn.create_domain(namespace)
    getattr(domain, '_metadata')
    item = domain.get_item(key)
    if item is not None:
        item.delete()
    return domain.put_attributes(key, value)


@manager.command
def delete(path):
    """Removes the config at given path."""
    namespace, key = get_namespace_key(path)
    conn = connect('sdb')
    domain = conn.get_domain(namespace)
    domain.get_item(key).delete()
    return True


@manager.command
def get(path):
    """Shows value(s) for given key."""
    namespace, key = get_namespace_key(path)
    conn = connect('sdb')
    domain = conn.get_domain(namespace)
    try:
        item = dict(domain.get_item(key, consistent_read=True))
    except TypeError:
        raise Exception('Invalid key %s' % path)
    return get_value(item)


@manager.command
def list(namespace='', expand=False):
    """Lists all config paths."""
    conn = connect('sdb')
    results = {}
    for domain in conn.get_all_domains():
        if namespace == '' or domain.name == 'all' \
                or namespace != '' and domain.name == namespace:
            if namespace != '' or domain.name == 'all':
                prefix = ''
            else:
                prefix = '%s.' % domain.name
            r = domain.select('select * from `%s`' % domain.name)
            for item in r:
                results['%s%s' % (prefix, item.name)] = get_value(dict(item),
                    not expand)
    return results


@manager.command
def reset():
    """Deletes all configs."""
    conn = connect('sdb')
    for domain in conn.get_all_domains():
        domain.delete()
