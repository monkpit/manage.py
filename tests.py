# -*- coding: utf-8 -*-
import os
import sys
import unittest
import re

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO  # NOQA

from manager import Arg, Command, Error, Manager, PromptedArg, puts
from manager.cli import process_value, prompt, TRUE_CHOICES, FALSE_CHOICES


manager = Manager()


class StdOut(StringIO):
    def __init__(self, stdin, prompts=None):
        StringIO.__init__(self)
        self.stdin = stdin
        self.prompts = prompts or {}

    def write(self, message):
        for key, value in self.prompts:
            if re.search(key, message):
                self.stdin.truncate(0)
                self.stdin.write(value)
                self.stdin.seek(0)
                return

        StringIO.write(self, message)


class capture(object):
    """Captures the std output.
    """
    def __init__(self, prompts=None):
        self.prompts = prompts

    def __enter__(self):
        self._stdout = sys.stdout
        self._stdin = sys.stdin
        sys.stdin = StringIO()
        sys.stdout = StdOut(sys.stdin, prompts=self.prompts)
        return sys.stdout

    def __exit__(self, type, value, traceback):
        sys.stdout = self._stdout
        sys.stdin = self._stdin


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

    def test_capture_usage(self):
        sys.argv[0] = 'manage.py'
        with capture() as c:
            manager.main(args=[])

        self.assertMultiLineEqual(
            c.getvalue(),
            """\
usage: manage.py [<namespace>.]<command> [<args>]

positional arguments:
  command     the command to run

optional arguments:
  -h, --help  show this help message and exit

available commands:
  class_based              no description
  raises                   no description
  simple_command           no description
  
  [my_namespace]
    namespaced             namespaced command
"""
        )

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
            new_manager.commands['new_command'].parse(['--first-arg', 'test'])

        self.assertNotIn(c.getvalue(), 'ERROR')

    def test_inspect_boolean_true(self):
        new_manager = Manager()

        @new_manager.command
        def new_command(arg=True):
            return 'true' if arg else 'false'

        with capture() as c:
            new_command.parse(['--no-arg'])

        self.assertIn('false', c.getvalue())

    def test_inspect_boolean_false(self):
        new_manager = Manager()

        @new_manager.command
        def new_command(arg=False):
            return 'true' if arg else 'false'

        with capture() as c:
            new_command.parse(['--arg'])

        self.assertIn('true', c.getvalue())

    def test_path_root(self):
        self.assertEqual(
            manager.commands['simple_command'].path,
            'simple_command'
        )

    def test_path_namespace(self):
        self.assertEqual(
            manager.commands['my_namespace.namespaced'].path,
            'my_namespace.namespaced'
        )

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
        self.assertEqual(
            len(manager.commands['my_namespace.namespaced'].args),
            1
        )

    def test_command_decorator_doc(self):
        self.assertEqual(
            manager.commands['my_namespace.namespaced'].description,
            'namespaced command'
        )

    def test_base_command(self):
        class ExtendedCommand(Command):
            attribute = 'value'

        new_manager = Manager(base_command=ExtendedCommand)

        @new_manager.command
        def my_command():
            return True

        self.assertTrue(hasattr(my_command, 'attribute'))

    def test_arg_decorator(self):
        @manager.arg('first_arg', help='first help')
        @manager.arg('second_arg', help='second help')
        @manager.command
        def new_command(first_arg, second_arg):
            return first_arg

        command = manager.commands['new_command']
        self.assertEqual(command.args[0].help, 'first help')
        self.assertEqual(command.args[1].help, 'second help')

    def test_prompt_decorator(self):
        @manager.prompt('password', hidden=True)
        @manager.command
        def connect(username, password):
            return password

        self.assertTrue(isinstance(connect.args[1], PromptedArg))

    def test_arg_preserve_inspected(self):
        @manager.arg('first_arg', shortcut='f')
        @manager.command
        def new_command(first_arg=False):
            return first_arg

        command = manager.commands['new_command']
        arg, position = command.get_argument('first_arg')
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
            command.parse(['first', '--second-arg', 'second value'])

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

    def test_parse_error(self):
        with capture() as c:
            try:
                manager.commands['raises'].parse(list())
            except SystemExit:
                pass
        self.assertEqual(c.getvalue(), 'No way dude!\n')

    def test_parse_false(self):
        @manager.command
        def new_command(**kwargs):
            return False

        with capture():
            self.assertRaises(
                SystemExit,
                manager.commands['new_command'].parse, list()
            )

    def test_parse_env_simple(self):
        env = "key=value"
        self.assertEqual(dict(manager.parse_env(env)), dict(key='value'))

    def test_parse_env_quote(self):
        env = "key='value'"
        self.assertEqual(dict(manager.parse_env(env)), dict(key='value'))

    def test_parse_env_double_quote(self):
        env = 'key="value"'
        self.assertEqual(dict(manager.parse_env(env)), dict(key='value'))

    def test_parse_env_multiline(self):
        env = """key="value"
another_key=another value"""
        self.assertEqual(
            dict(manager.parse_env(env)), dict(
                key='value',
                another_key='another value'
            )
        )

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

    def test_dict(self):
        with capture() as c:
            puts({
                'key': 'value',
                'nonetype': None,
                'nested': {'deep': 'value'},
            })

        self.assertEqual(len(c.getvalue().splitlines()), 3)

    def test_true(self):
        with capture() as c:
            puts(True)

        self.assertEqual(c.getvalue(), 'OK\n')

    def test_false(self):
        with capture() as c:
            puts(False)

        self.assertEqual(c.getvalue(), 'FAILED\n')


BOOL_CHOICES = TRUE_CHOICES + FALSE_CHOICES


class PromptTest(unittest.TestCase):
    def test_process_value_boolean_empty(self):
        self.assertRaises(Exception, process_value, '', type=bool,
            allowed=BOOL_CHOICES)

    def test_process_value_boolean_true(self):
        self.assertEqual(True, process_value('y', type=bool,
            allowed=BOOL_CHOICES))

    def test_process_value_boolean_false(self):
        self.assertEqual(False, process_value('no', type=bool,
            allowed=BOOL_CHOICES))

    def test_process_value_valid_choice(self):
        value = process_value('first', allowed=('first', 'second'))
        self.assertEqual(value, 'first')

    def test_process_value_invalid_choice(self):
        self.assertRaises(Exception, process_value, 'third',
            allowed=('first', 'second'))

    def test_process_value_default(self):
        value = process_value('', default='default value')
        self.assertEqual(value, 'default value')

    def test_string(self):
        with capture(prompts=[('Simple prompt', 'simple value')]) as c:
            value = prompt('Simple prompt')

        self.assertEqual(value, 'simple value')

    def test_string_empty_allowed(self):
        name = 'Simple prompt'
        with capture(prompts=[(name, '\n')]) as c:
            value = prompt(name, empty=True)

        self.assertEqual(value, None)

    def test_string_empty_disallowed(self):
        name = 'Simple prompt'
        with capture(prompts=[(name, '')]) as c:
            self.assertRaises(Error, prompt, name)

    def test_string_default(self):
        name = 'Simple prompt'
        with capture(prompts=[(name, '\n')]) as c:
            value = prompt(name, default='default value')

        self.assertEqual(value, 'default value')

    def test_boolean_empty(self):
        name = 'Bool prompt'
        with capture(prompts=[(name, '\n')]) as c:
            self.assertRaises(Error, prompt, name, type=bool)

    def test_boolean_yes(self):
        name = 'Bool prompt'
        with capture(prompts=[(name, 'yes')]) as c:
            value = prompt(name, type=bool)

        self.assertEqual(value, True)

    def test_boolean_no(self):
        name = 'Bool prompt'
        with capture(prompts=[(name, 'n')]) as c:
            value = prompt(name, type=bool)

        self.assertEqual(value, False)

    def test_confirm_match(self):
        name, expected = 'Simple prompt', 'expected'
        with capture(prompts=[('%s \(again\)' % name, expected),
                (name, expected)]) as c:
            value = prompt(name, confirm=True)

        self.assertEqual(value, expected)

    def test_confirm_not_match(self):
        name, expected = 'Simple prompt', 'expected'
        with capture(prompts=[('%s \(again\)' % name, 'wrong value'),
                (name, expected)]) as c:
            self.assertRaises(Error, prompt, name, confirm=True)


if __name__ == '__main__':
    unittest.main()
