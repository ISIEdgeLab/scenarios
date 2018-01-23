#!/usr/bin/env python3
import sys
from subprocess import PIPE, Popen
from shutil import copyfile


def installed() -> bool:
    proc = Popen('3to2 -h', stdout=PIPE, stderr=PIPE, shell=True)
    _, stderr = proc.communicate()
    if stderr:
        return False
    return True


def install_3to2():
    proc = Popen('pip3 install 3to2 --user', stdout=PIPE, stderr=PIPE, shell=True)
    stdout, stderr = proc.communicate()
    if stdout:
        print(stderr)
        return False
    return True


def update_code():
    ''' create a python2 version of wrapper.py named wrapper.py'''
    proc = Popen('3to2 -w wrapper.py', stdout=PIPE, stderr=PIPE, shell=True)
    stdout, stderr = proc.communicate()
    if stdout:
        print(stderr)
        return False
    return True


if not installed():
    if not install_3to2():
        print('unable to install 3to2 tool')
        sys.exit(1)

# create backups
copyfile('wrapper.py', '.py3_wrapper.bak')
copyfile('py2_wrapper.py', '.py2_wrapper.bak')

update_code()

copyfile('wrapper.py', 'py2_wrapper.py')
copyfile('.py3_wrapper.bak', 'wrapper.py')

print('successfully updated python2 code from python3 source')
