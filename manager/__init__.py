# -*- coding: utf-8 -*-
import argparse
import collections
import functools
import sys
import re
import os
import inspect

from clint import args
from clint.textui import colored, puts as clint_puts, min_width, indent


class Error(Exception):
    pass


def puts(r):
    stdout = sys.stdout.write
    type_ = type(r)
    if type_ == list:
        return [puts(i) for i in r]
    elif type_ == dict:
        for key in r:
            puts(min_width(colored.blue(key), 25) + r[key])
        return
    elif type_ == Error:
        return puts(colored.red(str(r)))
    elif type_ == bool:
        if r:
            return puts(colored.green('OK'))
        return puts(colored.red('FAILED'))
    elif r is not None:
        return clint_puts(str(r).strip('\n'), stream=stdout)


class Command(object):
    name = None
    namespace = None
    description = 'no description'
    run = None
    capture_all = False

    def __init__(self, **kwargs):
        for key in kwargs:
            if hasattr(self, key):
                setattr(self, key, kwargs[key])
            else:
                raise Exception('Invalid keyword argument `%s`' % key)

        self.args = []

        if self.name is None:
            self.name = re.sub('(.)([A-Z]{1})', r'\1_\2',
                self.__class__.__name__).lower()

        if not self.capture_all:
            self.inspect()

    def __call__(self, *args, **kwargs):
        return self.run(*args, **kwargs)

    def inspect(self):
        self.arg_names, varargs, keywords, defaults = inspect.getargspec(
            self.run)
        if hasattr(self.run, 'im_self') or hasattr(self.run, '__self__'):
            del self.arg_names[0]  # Removes `self` arg for class method
        if defaults is not None:
            kwargs = dict(zip(*[reversed(l) \
                for l in (self.arg_names, defaults)]))
        else:
            kwargs = []
        for arg_name in self.arg_names:
            type_ = type(kwargs[arg_name]) if arg_name in kwargs else None
            if type_ == type(None):
                type_ = None
            arg = Arg(
                arg_name,
                default=kwargs[arg_name] if arg_name in kwargs else None,
                type=type_,
                required=not arg_name in kwargs,
            )
            self.add_argument(arg)

    def add_argument(self, arg):
        dest = arg.dest if hasattr(arg, 'dest') else arg.name
        if self.has_argument(arg.name):
            raise Exception('Arg %s already exists' % arg.name)
        self.args.append(arg)

    def get_argument(self, name):
        if not self.has_argument(name):
            raise Exception('Arg %s does not exist' % name)
        position = self.arg_names.index(name)
        return self.args[position]

    def has_argument(self, name):
        return name in [arg.name for arg in self.args]

    def run(self, *args, **kwargs):
        raise NotImplementedError

    def parse(self, args):
        if self.capture_all:
            args, kwargs = [args], {}
        else:
            parsed_args = self.parser.parse_args(args)
            kwargs = dict(parsed_args._get_kwargs())
            args = []
            position = 0
            for arg_name in self.arg_names:
                arg = self.args[position]
                if arg.required:
                    args.append(getattr(parsed_args, arg_name))
                    del kwargs[arg_name]
                position = position + 1
        try:
            r = self(*args, **kwargs)
        except Error as e:
            r = e
        return puts(r)

    @property
    def parser(self):
        parser = argparse.ArgumentParser(description=self.description)
        for arg in self.args:
            flags = [arg.name]
            if not arg.required:
                flags = ['--%s' % arg.name]
                if arg.shortcut is not None:
                    flags.append('-%s' % arg.shortcut)
            parser.add_argument(*flags, **arg.kwargs)
        return parser

    @property
    def path(self):
        return self.name if self.namespace is None else '%s.%s' % \
            (self.namespace, self.name)


class Manager(object):
    def __init__(self, base_command=Command, envs=False):
        self.base_command = base_command
        self.commands = {}
        self.env_vars = collections.defaultdict(dict)
        if envs:
            self.command(self.envs)

    @property
    def Command(self):
        manager = self

        class BoundMeta(type):
            def __new__(meta, name, bases, dict_):
                new = type.__new__(meta, name, bases, dict_)
                if name != 'BoundCommand':
                    manager.add_command(new())
                return new

        return BoundMeta('BoundCommand', (self.base_command, ), {})

    def add_command(self, command):
        self.commands[command.path] = command

    def arg(self, name, shortcut=None, **kwargs):
        def wrapper(command):
            def wrapped(**kwargs):
                if command.has_argument(name):
                    arg = command.get_argument(name)
                    if shortcut is not None:
                        arg.shortcut = shortcut
                    arg._kwargs.update(**kwargs)
                    return command
                command.add_argument(Arg(name, shortcut, **kwargs))
                return command
            return wrapped(**kwargs)

        return wrapper

    def merge(self, manager, namespace=None):
        for command_name in manager.commands:
            command = manager.commands[command_name]
            if namespace is not None:
                command.namespace = namespace
            self.add_command(command)

    def command(self, *args, **kwargs):
        def register(fn):
            def wrapped(**kwargs):
                if not 'name' in kwargs:
                    kwargs['name'] = fn.__name__
                if not 'description' in kwargs and fn.__doc__:
                    kwargs['description'] = fn.__doc__
                command = self.Command(run=fn, **kwargs)
                self.add_command(command)
                return command
            return wrapped(**kwargs)

        if len(args) == 1 and callable(args[0]):
            fn = args[0]
            return register(fn)
        else:
            return register

    def update_env(self):
        path = os.path.join(os.getcwd(), '.env')
        if os.path.isfile(path):
            env = self.parse_env(open(path).read())
            for key in env:
                os.environ[key] = env[key]

    def parse_env(self, content):
        def strip_quotes(string):
            for quote in "'", '"':
                if string.startswith(quote) and string.endswith(quote):
                    return string.strip(quote)
            return string

        regexp = re.compile('^([A-Za-z_0-9]+)=(.*)$', re.MULTILINE)
        founds = re.findall(regexp, content)
        return {key: strip_quotes(value) for key, value in founds}

    @property
    def parser(self):
        parser = argparse.ArgumentParser(
            usage='%(prog)s [<namespace>.]<command> [<args>]')
        parser.add_argument('command', help='the command to run')
        return parser

    def usage(self):
        def format_line(command, w):
            return "%s%s" % (min_width(command.name, w),
                command.description)

        self.parser.print_help()
        if len(self.commands) > 0:
            puts('\navailable commands:')
            with indent(2):
                namespace = None
                for command_path in sorted(self.commands,
                        key=lambda c: '%s%s' % (c.count('.'), c)):
                    command = self.commands[command_path]
                    if command.namespace is not None:
                        if command.namespace != namespace:
                            puts(colored.red('\n[%s]' % command.namespace))
                        with indent(2):
                            puts(format_line(command, 23))
                    else:
                        puts(format_line(command, 25))
                    namespace = command.namespace

    def main(self):
        if len(args) == 0 or args[0] in ('-h', '--help'):
            return self.usage()
        command = args.get(0)
        try:
            command = self.commands[command]
        except KeyError as e:
            puts(colored.red('Invalid command `%s`\n' % command))
            return self.usage()
        self.update_env()
        command.parse(args.all[1:])

    def env(self, key, value=None):
        """Decorator to register an ENV variable needed for a method.

        For optional env variables, set a default value using <value>.

        All env vars will be made available as key word arguments.

        @manager.env('SOME_ARG')
        def your_method(some_arg):
            ...
        """
        key = key.lower()

        def decorator(f):
            self.env_vars[f.__name__][key] = value

            @functools.wraps(f)
            def wrapper(*args, **kwargs):
                if kwargs.get(key, None) is None:
                    if key.upper() in os.environ:
                        kwargs[key] = os.environ[key.upper()]
                    elif value:
                        kwargs[key] = value
                    else:
                        raise KeyError('Please set ENV var %s.' % key.upper())
                return f(*args, **kwargs)
            return wrapper
        return decorator

    def envs(self):
        """List required and optional environment variables."""
        if not self.env_vars:
            puts('No ENV variables have been registered.')
            puts('To register an ENV variable, use the @env(key, value) ')
            puts('method decorator of your manager object.')
            return

        puts('Registered ENV vars per method.\n')
        for func_name in self.env_vars:
            puts('%s:' % func_name)
            for var, default in self.env_vars[func_name].items():
                default = '(%s)' % default if default is not None else ''
                puts('\t%s%s' % (min_width(var.upper(), 30), default))
            puts('')


class Arg(object):
    defaults = {
        'help': 'no description',
        'required': False,
        'type': None,
    }

    def __init__(self, name, shortcut=None, **kwargs):
        self.name = name
        self.shortcut = shortcut
        self._kwargs = self.defaults.copy()
        self._kwargs.update(kwargs)

    def __getattr__(self, key):
        if not key in self._kwargs:
            raise AttributeError
        return self._kwargs[key]

    @property
    def kwargs(self):
        dict_ = self._kwargs.copy()
        if self.required:
            del dict_['required']
        elif self.type == bool and self.default == False:
            dict_['action'] = 'store_true'
            del dict_['type']
        return dict_
