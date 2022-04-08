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

import stat


def _get_image_path(image_name, image_dir, image_suffix='tar'):
    """
    Function to obtain path to image

    :param image_name: Physical file name of Image
    :param image_dir: Directory path of image 
    :param image_suffix: file type of Image


    :return: full image path

    """
    return os.path.join(image_dir, os.extsep.join([image_name, image_suffix]))


def _get_container_path(container_id, container_dir, *subdir_names):
    """
    Function to obtain path to container

    :param container_id: the unique container id
    :param container_dir: the base directory of newly generated container
                          directories
    :param subdir_names: subdirectory within the container

    :return: full container path

    """
    return os.path.join(container_dir, container_id, *subdir_names)


def create_container_root(image_name, image_dir, container_id, container_dir):
    """
    Create a container root by extracting an image into a new directory

    :param image_name: the image name to extract
    :param image_dir: the directory to lookup image tarballs in
    :param container_id: the unique container id
    :param container_dir: the base directory of newly generated container
                          directories

    :return: full container path created

    """
    image_path = _get_image_path(image_name, image_dir)
    container_root = _get_container_path(container_id, container_dir, 'rootfs')

    assert os.path.exists(image_path), "unable to locate image %s" % image_name

    # keep only one rootfs per image and re-use it
    container_root = _get_container_path(container_id, container_dir, 'rootfs')

    if not os.path.exists(container_root):
        os.makedirs(container_root)

    # pivot_root(new_root, put_old) requires new_root to be a different filesystem then the old root.
    # To prevent run time errors we mount an overlay filesystem as new_root
    linux.mount('tmpfs', container_root, 'tmpfs', 0, None)

    with tarfile.open(image_path) as t:
        # CHRTYPE and BLKTYPE are device driver files that we don't require
        members = [m for m in t.getmembers()
                   if m.type not in (tarfile.CHRTYPE, tarfile.BLKTYPE)]
        t.extractall(container_root, members=members)

    return container_root


@click.group()
def cli():
    pass


def makedev(dev_path):
    for i, dev in enumerate(['stdin', 'stdout', 'stderr']):
        os.symlink('/proc/self/fd/%d' % i, os.path.join(dev_path, dev))
    os.symlink('/proc/self/fd', os.path.join(dev_path, 'fd'))
    # Add extra devices (null, zero, random, urandom, console ...)
    DEVICES = {'null': (stat.S_IFCHR, 1, 3), 'zero': (stat.S_IFCHR, 1, 5),
               'random': (stat.S_IFCHR, 1, 8), 'urandom': (stat.S_IFCHR, 1, 9),
               'console': (stat.S_IFCHR, 136, 1), 'tty': (stat.S_IFCHR, 5, 0),
               'full': (stat.S_IFCHR, 1, 7)}
    for device, (dev_type, major, minor) in DEVICES.items():
        # mode = 0o666, allows read and write file operations within the created directory
        os.mknod(os.path.join(dev_path, device),
                 0o666 | dev_type, os.makedev(major, minor))


def _create_mounts(new_root):
    # In order to actually access the configurations of the container being created, we require these 3 pseudo-filesystems
    # proc: information about the real runtime system configurations
    linux.mount('proc', os.path.join(new_root, 'proc'), 'proc', 0, '')
    # sys: information about various kernel subsystems, hardware devices, and associated device drivers
    linux.mount('sysfs', os.path.join(new_root, 'sys'), 'sysfs', 0, '')
    # tmp: a temporary file storage; acts similar to RAM
    # NOSUID: prevents the 'suid' bit on executables from taking effect, and thus essentially allows anyone other than
    # the executables owner to also run the executable;
    # STRICTATIME: updates the access time of the files every time they are accessed
    linux.mount('tmpfs', os.path.join(new_root, 'dev'), 'tmpfs',
                linux.MS_NOSUID | linux.MS_STRICTATIME, 'mode=755')

    # devpts: to enable terminal within the container to allow interactions with the container
    devpts_path = os.path.join(new_root, 'dev', 'pts')
    if not os.path.exists(devpts_path):
        os.makedirs(devpts_path)
        linux.mount('devpts', devpts_path, 'devpts', 0, '')

    makedev(os.path.join(new_root, 'dev'))


def contain(command, image_name, image_dir, container_id, container_dir):
    """
    Contain function that is used to actually create the contained space.

    :param command: Command passed while running the file
    :param image_name: Physical file name of Image
    :param image_dir: Directory path of image 
    :param container_id: Unique ID of container
    :param container_dir: Directory path of container to be made

    """
    try:
        # create a new mount namespace
        linux.unshare(linux.CLONE_NEWNS)
        # CLONE_NEWNS provides the child with a new mount namespace (requires ADMIN capability)
    except RuntimeError as e:
        if getattr(e, 'args', '') == (1, 'Operation not permitted'):
            print('Error: Use of CLONE_NEWNS with unshare(2) requires the '
                  'CAP_SYS_ADMIN capability (i.e. you probably want to retry '
                  'this with sudo)')
        raise e
    # MS_PRIVATE makes the mount private
    # MS_REC creates a recursive bind mount

    # NOTE: MS_REC is added along with MS_PRIVATE to change the propagation type of all of the mounts in a subtree
    linux.mount(None, '/', None, linux.MS_PRIVATE | linux.MS_REC, None)

    new_root = create_container_root(
        image_name, image_dir, container_id, container_dir)
    print('Created a new root fs for our container: {}'.format(new_root))

    _create_mounts(new_root)

    old_root = os.path.join(new_root, 'old_root')
    os.makedirs(old_root)

    linux.pivot_root(new_root, old_root)

    # Changes directory to be within the new root
    os.chdir('/')
    # umount old root
    linux.umount2('/old_root', linux.MNT_DETACH)
    # rmdir the old_root dir
    os.rmdir('/old_root')

    os.execvp(command[0], command)


@cli.command(context_settings=dict(ignore_unknown_options=True,))
@click.option('--image-name', '-i', help='Image name', default='ubuntu-export')
@click.option('--image-dir', help='Images directory',
              default='.')
@click.option('--container-dir', help='Containers directory',
              default='./build/containers')
@click.argument('Command', required=True, nargs=-1)
def run(image_name, image_dir, container_dir, command):
    """
    Run function that is called via the 'run' arugment in the command-line command

    :param image_name: Physical file name of Image
    :param image_dir: Directory path of image 
    :param container_dir: Directory path of container to be made
    :param command: Command passed while running the file

    """
    container_id = str(uuid.uuid4())
    pid = os.fork()
    # if it is the parent process, call the contain function
    if pid == 0:
        # This is the child, we'll try to do some containment here
        try:
            contain(command, image_name, image_dir, container_id,
                    container_dir)
        except Exception:
            traceback.print_exc()
            # something went wrong in contain()
            os._exit(1)

    # This is the parent, pid contains the PID of the forked process
    # wait for the forked child, fetch the exit status
    _, status = os.waitpid(pid, 0)
    print('{} exited with status {}'.format(pid, status))


if __name__ == '__main__':
    if not os.path.exists('./build/containers'):
        os.makedirs('./build/containers')

    cli()
