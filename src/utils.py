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
from os.path import abspath, exists, dirname, basename, isfile
import sqlite3
import time
import pandas as pd
import numpy as np
import codecs
import re
import base64
import PIL.Image
import pillow_heif
import shutil
import filetype
import json
import cv2
from io import BytesIO
import plistlib

from src import ccl_bplist

start_dir = os.getcwd()
app_data_dir = os.getenv('APPDATA')
log_file_fp = pj(app_data_dir, 'CF_MIFT', 'logs.txt')


def copy_files(files, from_dir, to_dir):
    for file in files:
        if isfile(pj(from_dir, file)):
            shutil.copy(pj(from_dir, file), to_dir)


file_headers = {b'\xFF\xD8\xFF': ['jpeg', 'image'],
                b'\x89PNG\x0D\x0A\x1A\x0A': ['png', 'image'],
                b'GIF': ['gif', 'image'],
                b'BM': ['bmp', 'image'],
                b'\x00\x00\x01\x00': ['ico', 'image'],
                b'\x49\x49\x2A\x00': ['tif', 'image'],
                b'\x4D\x4D\x00\x2A': ['tif', 'image'],
                b'RIFF': ['avi', 'video'],
                b'OggS\x00\x02': ['ogg', 'video'],
                b'ftypf4v\x20': ['f4v', 'video'],
                b'ftypF4V\x20': ['f4v', 'video'],
                b'ftypmmp4': ['3gp', 'video'],
                b'ftyp3g2a': ['3g2', 'video'],
                b'matroska': ['mkv', 'video'],
                b'\x01\x42\xF7\x81\x01\x42\xF2\x81)': ['mkv', 'video'],
                b'moov': ['mov', 'video'],
                b'skip': ['mov', 'video'],
                b'mdat': ['mov', 'video'],
                b'\x00\x00\x00\x14pnot': ['mov', 'video'],
                b'\x00\x00\x00\x08wide)': ['mov', 'video'],
                b'ftypmp41': ['mp4', 'video'],
                b'ftypavc1': ['mp4', 'video'],
                b'ftypMSNV': ['mp4', 'video'],
                b'ftypFACE': ['mp4', 'video'],
                b'ftypmobi': ['mp4', 'video'],
                b'ftypmp42': ['mp4', 'video'],
                b'ftypMP42': ['mp4', 'video'],
                b'ftypdash': ['mp4', 'video'],
                b'\x30\x26\xB2\x75\x8E\x66\xCF\x11\xA6\xD9\x00\xAA\x00\x62\xCE\x6C': ['wmv', 'video'],
                b'4XMVLIST': ['4xm', 'video'],
                b'FLV\x01': ['flv', 'video'],
                b'\x1A\x45\xDF\xA3\x01\x00\x00\x00': ['webm', 'video'],
                b'ftypheic': ['heic', 'image']}


class NpEncoder(json.JSONEncoder):
    # converts numpy objects so they can be serialised
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NpEncoder, self).default(obj)


def heic_2_jpg(img_fp):
    # Convert heic to jpg. Check it is supported and has been converted
    p = Popen(['powershell', resource_path('ConvertTo-Jpeg.ps1'), img_fp],
              shell=False, stderr=PIPE, stdout=PIPE)
    out = p.stdout.read().decode('utf8')
    if 'Unsupported' in out:
        return 'Error'
    elif '[Already' in out:
        return 'Keep'
    else:
        # return the absolute path to the output jpg
        return abspath(pj(dirname(img_fp), basename(img_fp).split('.')[0] + '.jpg'))


def get_image_type(img_fp):
    file_typ, file_ext = None, None
    kind = filetype.guess(img_fp)
    if kind is None:
        with open(img_fp, 'rb') as bf:
            line = bf.read(50)
            for head, ext in file_headers.items():
                if head in line:
                    file_typ, file_ext = ext
    else:
        file_typ, file_ext = kind.mime, kind.extension
    return file_typ, file_ext


def get_video_frame(fp):
    # gets the first frame of a video
    try:
        cap = cv2.VideoCapture(fp)
        _, cv2_img = cap.read()
        cv2_img = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2RGB)
        img = PIL.Image.fromarray(cv2_img)
        file_ext = 'JPEG'
        return img, file_ext
    except Exception as e:
        print(e)
        return False, False


def media_support(fp):
    # analyses the media file for file signature etc so that it can be displayed in the GUI
    # if a file is not supported, a placeholder (blank image) is returned.
    file_type, file_ext = get_image_type(fp)

    if file_type and file_ext:
        if file_ext == 'heic':
            out = heic_2_jpg(fp)
            if out == 'Keep':
                img = PIL.Image.open(out, 'r')
            elif out == 'Error':
                img = PIL.Image.open(resource_path('blank_jpeg.png'), 'r')
                file_ext = 'PNG'
            else:
                img = PIL.Image.open(out, 'r')
                file_ext = 'JPEG'

        elif file_type.startswith('image'):
            img = PIL.Image.open(fp, 'r')

        elif file_type.startswith('video'):
            img, file_ext = get_video_frame(fp)
            if img and file_ext:
                pass
            else:
                img = PIL.Image.open(resource_path('blank_jpeg.png'), 'r')
                file_ext = 'PNG'
        else:
            img = PIL.Image.open(resource_path('blank_jpeg.png'), 'r')
            file_ext = 'PNG'
    else:
        img = PIL.Image.open(resource_path('blank_jpeg.png'), 'r')
        file_ext = 'PNG'

    if file_ext == 'jpg':
        # jpg is not recognised by pillow, jpeg is
        file_ext = 'jpeg'

    return img, file_ext


def generate_thumbnail(fp, thmbsize=128):
    # converts images to a thumbnail format for reports
    img, file_ext = media_support(fp)

    hpercent = (int(thmbsize) / float(img.size[1]))
    wsize = int((float(img.size[0]) * float(hpercent)))
    img = img.resize((wsize, int(thmbsize)), PIL.Image.ANTIALIAS)

    buf = BytesIO()
    img.save(buf, format=file_ext.upper())
    b64_thumb = base64.b64encode(buf.getvalue()).decode('utf8')

    return b64_thumb


def row_combiner(row, cols):
    combined = ''
    for col in cols:
        combined += '{}: {}\n'.format(col, row[col])
    return combined


def clean_ascii(val, replace_=' '):
    # remove non-ascii chars - replace with a provided string
    return re.sub(r'[^x00-x7F]', replace_, val)


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
        self.temp_dirs = list()
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

