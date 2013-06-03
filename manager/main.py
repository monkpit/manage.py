# -*- coding: utf-8 -*-
import os
import imp
import sys

from clint.textui import colored, puts


def main():
    try:
        sys.path.append(os.getcwd())
        imp.load_source('manager', os.path.join(os.getcwd(), 'manage.py'))
    except IOError:
        return puts(colored.red('No such file manage.py'))

    from manager import manager

    manager.main()


if __name__ == '__main__':
    main()
