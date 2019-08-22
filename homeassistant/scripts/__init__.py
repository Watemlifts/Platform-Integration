"""Home Assistant command line scripts."""
import argparse
import asyncio
import importlib
import logging
import os
import sys
from typing import List

from homeassistant.bootstrap import async_mount_local_lib_path
from homeassistant.config import get_default_config_dir
from homeassistant.requirements import pip_kwargs
from homeassistant.util.package import (
    install_package, is_virtual_env, is_installed)


def run(args: List) -> int:
    """Run a script."""
    scripts = []
    path = os.path.dirname(__file__)
    for fil in os.listdir(path):
        if fil == '__pycache__':
            continue
        elif os.path.isdir(os.path.join(path, fil)):
            scripts.append(fil)
        elif fil != '__init__.py' and fil.endswith('.py'):
            scripts.append(fil[:-3])

    if not args:
        print('Please specify a script to run.')
        print('Available scripts:', ', '.join(scripts))
        return 1

    if args[0] not in scripts:
        print('Invalid script specified.')
        print('Available scripts:', ', '.join(scripts))
        return 1

    script = importlib.import_module('homeassistant.scripts.' + args[0])

    config_dir = extract_config_dir()

    loop = asyncio.get_event_loop()

    if not is_virtual_env():
        loop.run_until_complete(async_mount_local_lib_path(config_dir))

    _pip_kwargs = pip_kwargs(config_dir)

    logging.basicConfig(stream=sys.stdout, level=logging.INFO)

    for req in getattr(script, 'REQUIREMENTS', []):
        if is_installed(req):
            continue

        if not install_package(req, **_pip_kwargs):
            print('Aborting script, could not install dependency', req)
            return 1

    return script.run(args[1:])


def extract_config_dir(args=None) -> str:
    """Extract the config dir from the arguments or get the default."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('-c', '--config', default=None)
    args = parser.parse_known_args(args)[0]
    return (os.path.join(os.getcwd(), args.config) if args.config
            else get_default_config_dir())
