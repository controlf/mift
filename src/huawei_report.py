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

from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import pyqtSignal, QThread
import os
import logging
from os.path import join as pj
from os.path import dirname, basename, abspath
from time import strftime
from datetime import datetime
import webbrowser as wb
import re
import shutil
import pandas as pd

from src import extract_archive
from src.utils import refresh_temp_dir, clean_path, build_dataframe


def find_jpeg(cachefile):
    cachefile = open(cachefile, 'rb')
    cache_contents = cachefile.read()
    cachefile.close()
    cache_dict = dict()
    # regex the cache file for all instances of \xFF\xD8\xFF(.*?)\xFF\xD9
    for result in re.findall(b'\xFF\xD8\xFF(.*?)\xFF\xD9', cache_contents, re.S):
        result = b'\xFF\xD8\xFF'+result+b'\xFF\xD9'
        # make sure we do actually have a JPEG by checking the 11 bytes of the image header.
        if b'\x4A\x46\x49\x46\x00' in result:  # JFIF magic
            # We have the returned bytes for our jpeg but we don't have its index in order to grab the timestamp.
            idx = cache_contents.find(result, 0)
            # original timestamp is found in the 24 bytes proceeding the JPEG header. Use the index to get this.
            original_timestamp = cache_contents[idx-24:idx-4].replace(b'\x00', b'').decode()
            gallery_local_media_id = cache_contents[idx-33:idx-26].replace(b'\x00', b'').decode()
            cache_dict[gallery_local_media_id] = [result, original_timestamp]
    return cache_dict



class MakeHuaweiReport(QThread):
    finishedSignal = pyqtSignal(object)
    progressSignal = pyqtSignal(list)

    def __init__(self, *args):
        QThread.__init__(self, args[0])
        self.tab_widget, self.maingui, self.archive, self.save_dir = args
        self.gallery_db = pj(self.save_dir, 'gallery.db')
        self.cachefile = pj(self.save_dir, 'imgcache.0')

    def build_dataframes(self):
        gallery_df = None
        try:
            gallery_df = build_dataframe(self.gallery_db, 'gallery_media')
        except Exception as err:
            logging.error(err)
        return gallery_df

    def parse_cache(self, gallery_df, cache_dict):
        cache_count = len(cache_dict.keys())
        self.progressSignal.emit([100, 'Parsed {} cache files from imgcache.0'.format(cache_count)])
        rows = list()
        count = 0
        gallery_id_list = gallery_df['local_media_id'].astype(str).values.tolist()

        for gallery_id, dict_values in cache_dict.items():
            row = list()
            with open(pj(self.save_dir, '{}.jpg'.format(gallery_id)), 'wb') as f:
                f.write(dict_values[0])
            row.append(abspath(pj(self.save_dir, '{}.jpg'.format(gallery_id))))
            row.append(gallery_id)
            ts = datetime.utcfromtimestamp(int(dict_values[1])).strftime('%d-%m-%Y %H:%M:%S')

            if gallery_id in gallery_id_list:
                gallery_row = gallery_df.loc[gallery_df['local_media_id'] == int(gallery_id)]
                row.append(gallery_row['_display_name'].values[0])
                row.append(gallery_row['_data'].values[0])
                row.append(ts)
                row.append("Live/Accessible")
            else:
                row.extend(['','',ts,'Deleted'])

            rows.append(row)
            count += 1
            self.progressSignal.emit([int(count/cache_count*100), gallery_id])


        cache_df = pd.DataFrame(rows, columns=['media', 'id', 'File Name', 'File Path', 'Timestamp', 'Original Status'])
        return cache_df

    def run(self):
        extract_instance = extract_archive.ExtractArchive(self,
                                                          [clean_path(pj('com.android.gallery3d', 
                                                                        'databases', 'gallery.db')),
                                                           clean_path(pj('Android', 'data', 'com.android.gallery3d', 
                                                                         'cache'))],
                                                          self.save_dir, self.archive)
                                        
        out = extract_instance.extract()
        self.progressSignal.emit([100, out])
        gallery_df = self.build_dataframes()
        cache_dict = find_jpeg(self.cachefile)
        cache_df = self.parse_cache(gallery_df, cache_dict)
        self.finishedSignal.emit(cache_df)
