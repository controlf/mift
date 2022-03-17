"""
MIT License

mift - Copyright (c) 2021 Control-F
Author: Mike Bangham (Control-F)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software, 'mift', and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

"""

from PyQt5.QtGui import QPixmap, QTransform
from PyQt5.QtCore import Qt
import os
import logging
import sys
from os.path import join as pj
from os.path import abspath
import sqlite3
import time
import pandas as pd
import codecs
import shutil
from io import BytesIO
import plistlib

from src import ccl_bplist

start_dir = os.getcwd()
app_data_dir = os.getenv('APPDATA')
log_file_fp = pj(app_data_dir, 'CF_MIFT', 'logs.txt')


def clean_path(path):
    return path.replace('\\\\', '/').replace('\\', '/')


def build_dataframe(db, table, index=None):
    fc_conn = sqlite3.connect(db)
    df = pd.read_sql_query("SELECT * FROM "+ table, fc_conn, index_col=index)
    fc_conn.close()
    return df


def dictionary_recursor(dic):
    for k, v in dic.items():
        if type(v) is dict:
            yield from dictionary_recursor(v)
        else:
            yield k, v


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except:
        # 'res' added to path. Should be omitted when compiling executable.
        # base_path = os.path.abspath(".")
        base_path = abspath(pj(".", 'res'))
    return pj(base_path, relative_path)


def refresh_temp_dir():
    now = int(time.time())
    # Create our temp dir for storing working copies of files. If it exists we need to remove it and recreate it.
    temp_out = pj(app_data_dir, 'CF_MIFT', 'temp')
    if os.path.exists(temp_out):
        try:  # Clear the temporary directory
            shutil.rmtree(temp_out)
            os.makedirs(pj(temp_out, '{}'.format(now)), exist_ok=True)
        except Exception as e:
            logging.error(e)
            logging.info('Unable to clear the Temp Directory: {}. Please do this manually.'.format(temp_out))
    else:
        os.makedirs(pj(temp_out, '{}'.format(now)), exist_ok=True)

    return pj(temp_out, '{}'.format(now))


def get_sqlite_rowcount(db, table):
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    cur.execute('SELECT * FROM {}'.format(table))
    return len(cur.fetchall())


def transform_image(image, width=500, length=500, rotation_angle=0):
    pixmap = QPixmap(image)
    pixmap = pixmap.scaled(width, length, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    if rotation_angle != 0:
        transform = QTransform().rotate(rotation_angle)  # rotate image using angle
        pixmap = pixmap.transformed(transform, Qt.SmoothTransformation)  # smooth image
    return pixmap


def decode_bplist(data, hxd=False):
    if hxd:
        # The bplist was dumped as hex in string format. We can convert the hex
        # and read it as a stream, saving the need to write the bplist out to a file
        try:
            converted = BytesIO(codecs.decode(data[2:-1], 'hex'))
            plist = ccl_bplist.load(converted)
        except Exception as err:
            logging.error('ERROR: Could not convert bplist from hex to bytes stream.\n{}'.format(err))
            return False
    else:
        # using a buffered stream so we can work on them only in memory.
        print(data)
        print(type(data))
        try:
            plist_dict = plistlib.load(BytesIO(data))  # convert our bplist as bytes to a dictionary object
            plist = ccl_bplist.load(BytesIO(plist_dict))  # buffer the dictionary so we can deserialise the keys
        except Exception as err:
            logging.error('ERROR: Could not convert data to bytes stream.\n{}'.format(err))
            return False  

    return ccl_bplist.deserialise_NsKeyedArchiver(plist, parse_whole_structure=True)
