# -*- mode: python -*-
# spec file for mift - Control-F 2021-2022

import os
from os.path import join as pj
from os.path import basename, dirname, isfile, isdir

block_cipher = None
main_path = os.getcwd()

a = Analysis(['mift.py'],
             pathex=[main_path],
             binaries=[],
             datas=[(main_path+'/mift.py', '.')],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)

extra_datas = []
for dir in ['res']:
    for f in os.listdir(pj(main_path, dir)):
        if isfile(pj(main_path, dir, f)):
            extra_datas.append((f, pj(main_path, dir, f), 'DATA'))

print(extra_datas)

a.datas += extra_datas

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='mift',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=False,
          icon=main_path+'/res/controlF.ico')
