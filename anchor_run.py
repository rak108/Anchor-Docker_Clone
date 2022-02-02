"""
Python3 file for the "run" command in Anchor.

Usage:
    running:
        'python anchor_run.py run /bin/echo "Welcome to Anchor"'
    will:
        - fork a new process which will execute '/bin/echo' and will print "Welcome to Anchor".
        - while the parent waits for it to finish
"""

from __future__ import print_function

import click
import os
import traceback


@click.group()
def cli():
    pass


def contain(command):
    os.execvp(command[0], command)


@cli.command(context_settings=dict(ignore_unknown_options=True,))
@click.argument('Command', required=True, nargs=-1)
def run(command):
    pid = os.fork()
    if pid == 0:
        try:
            contain(command)
        except Exception:
            traceback.print_exc()
            os._exit(1)
    _, status = os.waitpid(pid, 0)
    print('{} exited with status {}'.format(pid, status))


if __name__ == '__main__':
    cli()
