#install script for mift
supported = ['3.6', '3.7', '3.8', '3.9']
import pip
import platform
from subprocess import call
import os
from os.path import join as pj

print('\n\nINSTALLING MODULES REQUIRED FOR MIFT....\n')

cwd = os.getcwd()
py_version = '.'.join(platform.python_version_tuple()[:-1])

if py_version in supported:
    version_dir = pj(cwd, py_version)
    for folder in range(len(os.listdir(version_dir))):
        folder = str(folder + 1)
        for whl in os.listdir(pj(version_dir, folder)):
            print(pj(version_dir, str(folder), whl))
            call(['pip', 'install', os.path.join(cwd, py_version, str(folder), whl)])
    for whl in os.listdir(cwd):
        if whl.endswith('.whl'):
            print(pj(cwd, whl))
            call(['pip', 'install', pj(cwd, whl)])

else:
    print('The version of Python ({}) is not supported. '
          'Please install one of the following Python versions: {}'.format(py_version, supported))
