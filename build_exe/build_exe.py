# mift | Control-F | 2021-2022
# script to concatenate executable binary pieces

import os
from os.path import join as pj
cwd = os.getcwd()

print('Building mift.exe...')
mift_chunks = [f for f in os.listdir(cwd) if f.startswith('mift.')]
with open(pj(cwd, 'mift.exe'), 'wb+') as mift_out:
    for mift_chunk in sorted(mift_chunks):
        with open(pj(cwd, mift_chunk), 'rb') as chunk:
            mift_out.write(chunk.read())
print('Finished!')
