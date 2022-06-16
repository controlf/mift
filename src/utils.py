"""
MIT License

mift - Copyright (c) 2021-2022 Control-F
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
from PyQt5.QtCore import Qt, QThread
import os
import logging
from subprocess import Popen, PIPE
import sys
from os.path import join as pj
from os.path import abspath, exists
import sqlite3
import time
import pandas as pd
import codecs
from io import BytesIO
import plistlib

from src import ccl_bplist

start_dir = os.getcwd()
app_data_dir = os.getenv('APPDATA')
log_file_fp = pj(app_data_dir, 'CF_MIFT', 'logs.txt')


def clean_path(path):
    return path.replace('\\\\', '/').replace('\\', '/')


def build_dataframe(db, table, index=None, query=None):
    fc_conn = sqlite3.connect(db)
    if query:
        df = pd.read_sql_query(query, fc_conn, index_col=index)
    else:
        df = pd.read_sql_query("SELECT * FROM " + table, fc_conn, index_col=index)
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
            _plist = ccl_bplist.load(converted)
            if '$archiver' in _plist:  # is an NSKeyedArchiver object
                return ccl_bplist.deserialise_NsKeyedArchiver(_plist, parse_whole_structure=True)
            else:  # is a bplist
                # Younger versions of iOS store location data serialised under a key in a bplist.
                # To Do: parse this serialised data and return the dictionary
                pass
        except Exception as err:
            logging.error('ERROR: Could not convert bplist from hex to bytes stream.\n{}'.format(err))
            return False
    else:
        # using a buffered stream so we can work on them only in memory.
        try:
            plist_dict = plistlib.load(BytesIO(data))  # convert our bplist as bytes to a dictionary object
            _plist = ccl_bplist.load(BytesIO(plist_dict))  # buffer the dictionary so we can deserialise the keys
            return ccl_bplist.deserialise_NsKeyedArchiver(_plist, parse_whole_structure=True)
        except Exception as err:
            logging.error('ERROR: Could not convert data to bytes stream.\n{}'.format(err))
            return False


def refresh_temp_dir():
    temp_out = pj(app_data_dir, 'CF_MIFT', 'temp', str(int(time.time())))
    os.makedirs(temp_out, exist_ok=True)
    return temp_out


class CleanTemp(QThread):
    # Cleans the temporary directory in the background at startup
    def __init__(self, temp_output_dir):
        QThread.__init__(self, parent=None)
        self.temp_output_dir = temp_output_dir
        if exists(self.temp_output_dir):
            self.temp_dirs = [pj(self.temp_output_dir, d) for d in os.listdir(self.temp_output_dir)]

    def power_delete(self, dir_):
        try:
            cmd = ["powershell", "-Command", "Remove-Item", "-LiteralPath", dir_, "-Force", "-Recurse", "-Verbose"]
            Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True)
            return True
        except:
            return False

    def run(self):
        if self.temp_dirs:
            for td in self.temp_dirs:
                for root, dirs, files in os.walk(td, topdown=False):
                    for name in files:
                        try:
                            os.remove(pj(root, name))
                        except:
                            self.power_delete(pj(root, name))
                    for name in dirs:
                        try:
                            os.rmdir(pj(root, name))
                        except:
                            self.power_delete(pj(root, name))

        os.makedirs(self.temp_output_dir, exist_ok=True)

