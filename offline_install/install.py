#install script for mift
import pip
import platform
from subprocess import call
import os
from os.path import join as pj
from os.path import relpath as rp
from zipfile import ZipFile, ZIP_DEFLATED, is_zipfile


def build_large_wheel(folder, zip_fn):
    # GitHub does not allow large files, so we can build one from the constituent parts
    zf = ZipFile(zip_fn, 'w', ZIP_DEFLATED)
    abs_src = os.path.abspath(folder)
    for dirpath, dirnames, fns in os.walk(folder):
        for fn in fns:
            # make sure we have unpacked all zip files
            if is_zipfile(pj(dirpath, fn)):
                with ZipFile(pj(dirpath, fn), 'r') as zr:
                    zr.extractall(dirpath)
    for dirpath, dirnames, fns in os.walk(folder):
        for fn in fns:
            absname = os.path.abspath(os.path.join(dirpath, fn))
            arcname = absname[len(abs_src) + 1:]
            zf.write(pj(dirpath, fn), arcname)
    zf.close()


print('\n\nInstalling wheels required for mift....\n')

# we need this to be the precise execution order
wheels = ["six-1.16.0-py2.py3-none-any.whl",
          "python_dateutil-2.8.2-py2.py3-none-any.whl",
          "pytz-2022.1-py2.py3-none-any.whl",
          "astc_decomp-1.0.3-cp38-cp38-win_amd64.whl",
          "numpy-1.22.3-cp38-cp38-win_amd64.whl",
          "pandas-1.4.1-cp38-cp38-win_amd64.whl",
          "Pillow-9.0.1-cp38-cp38-win_amd64.whl",
          "pyliblzfse-0.4.1-cp38-cp38-win_amd64.whl",
          "PyQt5_sip-12.9.1-cp38-cp38-win_amd64.whl",
          "PyQt5_Qt5-5.15.2-py3-none-win_amd64.whl",
          "PyQt5-5.15.6-cp36-abi3-win_amd64.whl"]

cwd = os.getcwd()
py_version = '.'.join(platform.python_version_tuple()[:-1])

if '3.8' in py_version:
    print('Building PyQt5_Qt5-5.15.2-py3-none-win_amd64.whl...')
    folder = pj(cwd, 'wheels', 'PyQt5_Qt5')
    build_large_wheel(folder, pj(cwd, 'wheels', 'PyQt5_Qt5-5.15.2-py3-none-win_amd64.whl'))
    for whl in wheels:
        print(pj(cwd, 'wheels', whl))
        call(['pip', 'install', pj(cwd, 'wheels', whl)])
else:
    print('Offline install only works for Python version 3.8.x')

print('\n\nFinished install!')
