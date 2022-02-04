"""
Python3 file for the "run" command in Anchor.

Usage:
    running:
        'python anchor_run.py run /bin/echo "Welcome to Anchor"'
    will:
        fork a new process which will execute '/bin/echo' and will print "Welcome to Anchor".
        while the parent waits for it to finish

    ---

    running:
        python anchor_run.py run -i ubuntu-export /bin/sh
    will:
        fork a new child process that will:
           - unpack an ubuntu image into a new directory
           - chroot() into that directory
           - exec '/bin/sh'
        while the parent waits for it to finish.
"""

from __future__ import print_function

import os
import tarfile
import uuid

import click
import traceback

import linux

def _get_image_path(image_name, image_dir, image_suffix='tar'):
    return os.path.join(image_dir, os.extsep.join([image_name, image_suffix]))

def _get_container_path(container_id, container_dir, *subdir_names):
    return os.path.join(container_dir, container_id, *subdir_names)

def create_container_root(image_name, image_dir, container_id, container_dir):
    """Create a container root by extracting an image into a new directory

    Usage:
    new_root = create_container_root(
        image_name, image_dir, container_id, container_dir)

    @param image_name: the image name to extract
    @param image_dir: the directory to lookup image tarballs in
    @param container_id: the unique container id
    @param container_dir: the base directory of newly generated container
                          directories
    @retrun: new container root directory
    @rtype: str
    """
    image_path = _get_image_path(image_name, image_dir)
    container_root = _get_container_path(container_id, container_dir, 'rootfs')

    assert os.path.exists(image_path), "unable to locate image %s" % image_name

    if not os.path.exists(container_root):
        os.makedirs(container_root)

    with tarfile.open(image_path) as t:
        members = [m for m in t.getmembers()
                   if m.type not in (tarfile.CHRTYPE, tarfile.BLKTYPE)]
        t.extractall(container_root, members=members)

    return container_root

@click.group()
def cli():
    pass

def contain(command, image_name, image_dir, container_id, container_dir):
    new_root = create_container_root(
        image_name, image_dir, container_id, container_dir)
    print('Created a new root fs for our container: {}'.format(new_root))

    linux.mount('proc', os.path.join(new_root, 'proc'), 'proc', 0, '')
    linux.mount('sysfs', os.path.join(new_root, 'sys'), 'sysfs', 0, '')
    linux.mount('tmpfs', os.path.join(new_root, 'dev'), 'tmpfs',
                linux.MS_NOSUID | linux.MS_STRICTATIME, 'mode=755')

    devpts_path = os.path.join(new_root, 'dev', 'pts')
    if not os.path.exists(devpts_path):
        os.makedirs(devpts_path)
        linux.mount('devpts', devpts_path, 'devpts', 0, '')
    for i, dev in enumerate(['stdin', 'stdout', 'stderr']):
        os.symlink('/proc/self/fd/%d' % i, os.path.join(new_root, 'dev', dev))

    os.chroot(new_root)

    os.chdir('/')

    os.execvp(command[0], command)

@cli.command(context_settings=dict(ignore_unknown_options=True,))
@click.option('--image-name', '-i', help='Image name', default='ubuntu-export')
@click.option('--image-dir', help='Images directory',
              default='.')
@click.option('--container-dir', help='Containers directory',
              default='./build/containers')
@click.argument('Command', required=True, nargs=-1)

def run(image_name, image_dir, container_dir, command):
    container_id = str(uuid.uuid4())
    pid = os.fork()
    if pid == 0:
        try:
            contain(command, image_name, image_dir, container_id,
                    container_dir)
        except Exception:
            traceback.print_exc()
            os._exit(1)

    _, status = os.waitpid(pid, 0)
    print('{} exited with status {}'.format(pid, status))


if __name__ == '__main__':
    if not os.path.exists('./build/containers'):
        os.makedirs('./build/containers')

    cli()
