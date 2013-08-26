# -*- coding: utf-8 -*-
import os
import sys
import unittest

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO
from manager import Arg, Command, Error, Manager, puts


manager = Manager()


class capture(object):
    """Captures the std output.
    """
    def __enter__(self):
        self.backup = sys.stdout
        sys.stdout = StringIO()
        return sys.stdout

    def __exit__(self, type, value, traceback):
        sys.stdout = self.backup


class ClassBased(manager.Command):
    def run(self, name, capitalyze=False):
        if capitalyze:
            return name.upper()
        return name


@manager.command
def simple_command(name, capitalyze=False):
    if capitalyze:
        return name.upper()
    return name


@manager.command(namespace='my_namespace')
def namespaced(name):
    """namespaced command"""
    return name


@manager.command
def raises():
    raise Error('No way dude!')


class ArgTest(unittest.TestCase):
    def test_kwargs_required(self):
        kwargs = Arg('name', required=True).kwargs
        self.assertNotIn('required', kwargs)

    def test_kwargs_bool_false(self):
        kwargs = Arg('name', default=False, type=bool).kwargs
        self.assertNotIn('type', kwargs)
        self.assertEqual(kwargs['action'], 'store_true')


class CommandTest(unittest.TestCase):
    def test_registration(self):
        class MyCommand(manager.Command):
            pass

        self.assertIn('my_command', manager.commands)
        del manager.commands['my_command']

    def test_get_argument_existing(self):
        command = manager.commands['class_based']
        arg = command.get_argument('capitalyze')
        self.assertTrue(arg is not None)

    def test_get_argument_not_existing(self):
        command = manager.commands['class_based']
        self.assertRaises(Exception, command.get_argument, 'invalid')

    def test_inspect_class_based(self):
        args = manager.commands['class_based'].args
        self.assertEqual(len(args), 2)
        self.assertEqual(args[0].name, 'name')
        self.assertTrue(args[0].required)
        self.assertTrue(args[0].default is None)
        self.assertEqual(args[1].name, 'capitalyze')
        self.assertFalse(args[1].required)
        self.assertEqual(args[1].default, False)

    def test_inspect_function_based(self):
        args = manager.commands['simple_command'].args
        self.assertEqual(len(args), 2)
        self.assertEqual(args[0].name, 'name')
        self.assertTrue(args[0].required)
        self.assertTrue(args[0].default is None)
        self.assertEqual(args[1].name, 'capitalyze')
        self.assertFalse(args[1].required)
        self.assertEqual(args[1].default, False)

    def test_inspect_not_typed_optional_argument(self):
        new_manager = Manager()

        @new_manager.command
        def new_command(first_arg=None):
            return first_arg

        with capture() as c:
            new_manager.commands['new_command'].parse(['--first_arg', 'test'])

        self.assertNotIn(c.getvalue(), 'ERROR')

    def test_path_root(self):
        self.assertEqual(manager.commands['simple_command'].path,
            'simple_command')

    def test_path_namespace(self):
        self.assertEqual(manager.commands['my_namespace.namespaced'].path,
            'my_namespace.namespaced')

    def test_add_argument_existsing(self):
        command = Command(run=lambda new_argument: new_argument)
        self.assertEqual(len(command.args), 1)
        arg = Arg('new_argument', help='argument help')
        self.assertRaises(Exception, command.add_argument, arg)

    def test_capture_all(self):
        command = Command(run=lambda argv: argv, capture_all=True)
        self.assertEqual(len(command.args), 0)


class ManagerTest(unittest.TestCase):
    def test_command_decorator(self):
        self.assertIn('simple_command', manager.commands)
        self.assertEqual(len(manager.commands['simple_command'].args), 2)

    def test_command_decorator_kwargs(self):
        self.assertIn('my_namespace.namespaced', manager.commands)
        self.assertEqual(len(manager.commands['my_namespace.namespaced'].args),
            1)

    def test_command_decorator_doc(self):
        self.assertEqual(
            manager.commands['my_namespace.namespaced'].description,
            'namespaced command'
        )

    def test_arg_decorator(self):
        @manager.arg('first_arg', help='first help')
        @manager.arg('second_arg', help='second help')
        @manager.command
        def new_command(first_arg, second_arg):
            return first_arg

        command = manager.commands['new_command']
        self.assertEqual(command.args[0].help, 'first help')
        self.assertEqual(command.args[1].help, 'second help')

    def test_arg_preserve_inspected(self):
        @manager.arg('first_arg', shortcut='f')
        @manager.command
        def new_command(first_arg=False):
            return first_arg

        command = manager.commands['new_command']
        arg = command.get_argument('first_arg')
        self.assertEqual(arg.shortcut, 'f')
        self.assertEqual(arg.kwargs['action'], 'store_true')
        self.assertEqual(arg.kwargs['default'], False)

    def test_arg_with_shortcut(self):
        @manager.arg('first_arg', shortcut='f')
        @manager.command
        def new_command(first_arg=None):
            return first_arg

        command = manager.commands['new_command']
        expected = 'test'

        with capture() as c:
            command.parse(['-f', expected])

        self.assertEqual(c.getvalue(), '%s\n' % expected)

    def test_arg_extra_arg(self):
        @manager.arg('second_arg')
        @manager.command
        def new_command(first_arg, **kwargs):
            return 'second_arg' in kwargs

        command = manager.commands['new_command']
        with capture() as c:
            command.parse(['first', '--second_arg', 'second value'])

        self.assertEqual(c.getvalue(), 'OK\n')

    def test_merge(self):
        new_manager = Manager()
        new_manager.add_command(Command(name='new_command'))
        manager.merge(new_manager)
        self.assertIn('new_command', manager.commands)

    def test_merge_namespace(self):
        new_manager = Manager()
        new_manager.add_command(Command(name='new_command'))
        manager.merge(new_manager, namespace='new_namespace')
        self.assertIn('new_namespace.new_command', manager.commands)

    def test_parse_env_simple(self):
        env = "key=value"
        self.assertEqual(manager.parse_env(env), dict(key='value'))

    def test_parse_env_quote(self):
        env = "key='value'"
        self.assertEqual(manager.parse_env(env), dict(key='value'))

    def test_parse_env_double_quote(self):
        env = 'key="value"'
        self.assertEqual(manager.parse_env(env), dict(key='value'))

    def test_parse_env_multiline(self):
        env = """key="value"
another_key=another value"""
        self.assertEqual(manager.parse_env(env), dict(key='value',
            another_key='another value'))

    def test_env(self):
        new_manager = Manager()

        @new_manager.env('REQUIRED')
        @new_manager.env('OPTIONAL', value='bar')
        def throwaway(required=None, optional=None):
            return required, optional
        self.assertEqual(len(new_manager.env_vars['throwaway']), 2)
        if 'REQUIRED' in os.environ:
            del os.environ['REQUIRED']
        self.assertRaises(KeyError, throwaway)
        os.environ['REQUIRED'] = 'foo'
        req, opt = throwaway()
        self.assertEqual(req, 'foo')
        self.assertEqual(opt, 'bar')


class PutsTest(unittest.TestCase):
    def test_error(self):
        with capture() as c:
            manager.commands['raises'].parse(list())

        self.assertEqual(c.getvalue(), 'No way dude!\n')

    def test_none(self):
        with capture() as c:
            puts(None)

        self.assertEqual(c.getvalue(), '')

    def test_empty(self):
        with capture() as c:
            puts('')

        self.assertEqual(c.getvalue(), '\n')

    def test_list_strip_carriage_returns(self):
        with capture() as c:
            puts(['first line\n', 'second line\n'])

        self.assertEqual(len(c.getvalue().splitlines()), 2)

    def test_true(self):
        with capture() as c:
            puts(True)

        self.assertEqual(c.getvalue(), 'OK\n')

    def test_false(self):
        with capture() as c:
            puts(False)

        self.assertEqual(c.getvalue(), 'FAILED\n')


if __name__ == '__main__':
    unittest.main()
