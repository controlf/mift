# -*- mode: python ; coding: utf-8 -*-

block_cipher = None
cwd = '.'

a = Analysis(['mift.py'],
             pathex=[cwd+'/mift.py'],
             binaries=[],
             datas=[(cwd+'/mift.py', '.')],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)

a.datas += [('folder_y.png',cwd+'\\res\\folder_y.png', 'DATA'),
            ('dark_style.qss',cwd+'\\res\\dark_style.qss', 'DATA'),
			('photos_sqlite_query.txt',cwd+'\\res\\photos_sqlite_query.txt', 'DATA'),
			('applicationState_query.txt',cwd+'\\res\\applicationState_query.txt', 'DATA'),
            ('controlF.ico',cwd+'\\res\\controlF.ico', 'DATA'),
			('credits.txt',cwd+'\\res\\credits.txt', 'DATA'),
			('EULA.txt',cwd+'\\res\\EULA.txt', 'DATA'),
			('EULA_short.txt',cwd+'\\res\\EULA_short.txt', 'DATA'),
			('release_notes.txt',cwd+'\\res\\release_notes.txt', 'DATA'),
			('help.txt',cwd+'\\res\\help.txt', 'DATA'),
			('ControlF_R_RGB.png',cwd+'\\res\\ControlF_R_RGB.png', 'DATA'),
			('blank_jpeg.jpg',cwd+'\\res\\blank_jpeg.jpg', 'DATA'),
			('times_square.jpg',cwd+'\\res\\times_square.jpg', 'DATA'),
			('/config/Huawei.txt',cwd+'\\res\\config\\Huawei.txt', 'DATA'),
			('/config/iOS Photos.txt',cwd+'\\res\\config\\iOS Photos.txt', 'DATA'),
			('/config/iOS Snapshots.txt',cwd+'\\res\\config\\iOS Snapshots.txt', 'DATA'),
			('/config/Samsung.txt',cwd+'\\res\\config\\Samsung.txt', 'DATA'),		
			('/config/Sony.txt',cwd+'\\res\\config\\Sony.txt', 'DATA')
            ]

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
          icon=cwd+'/res/controlF.ico')
