# Anchor: The Docker Clone
A repository containing our learnings and implementations for the project "Anchor: The Docker Clone" under IEEE-NITK

Currently, the repository stores the (partial) code and requirements for the `run` command.

## Prerequisites
We're using Python 3.8 for the `run` command, let's try sticking to that.

## Setup
1. Create a VM either on your system using Virtual-Box, or a cloud VM (preferably) using your free Azure or AWS Student Account.
2. Clone the Git repository. How exactly you wish to clone it - whether directly into the VM or into your system and then `scp` it into the VM is upto you.
3. Build and Install the Linux module
    - ```bash
      cd setup
      python3 setup.py build
      python3 setup.py install
      cd ..
      ```
4. Run the `anchor_run.py` file according to instructions given in the file.

## Basic Guide
`ubuntu-export.tar` is the base image we would be using for now since it has the Ubuntu filesystem loaded from a running container. You can test your working by running basic commands within the container. 

Example:
```bash
python3 anchor_run.py run -i ubuntu-export /bin/echo "Hello World"
```
Should print Hello World and exit.
