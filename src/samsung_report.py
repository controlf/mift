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
import logging
from os.path import join as pj
from os.path import dirname, basename, isfile, abspath
from time import strftime
from datetime import datetime
import webbrowser as wb
import pandas as pd
import sqlite3
import shutil
import base64

from src import extract_archive
from src.utils import clean_path, get_sqlite_rowcount, build_dataframe


class MakeSamsungReport(QThread):
    finishedSignal = pyqtSignal(object)
    progressSignal = pyqtSignal(list)

    def __init__(self, *args):
        QThread.__init__(self, args[0])
        self.tab_widget, self.maingui, self.archive, self.save_dir = args
        self.filecachedb = pj(self.save_dir, 'FileCache.db')

    def build_dataframes(self):
        self.row_count = 0
        cache_df = None
        try:
            self.row_count = get_sqlite_rowcount(self.filecachedb, 'FileCache')
            cache_df = build_dataframe(self.filecachedb, 'FileCache', index=['_index'])
            cache_df = cache_df[cache_df.storage == 0]
        except Exception as err:
            logging.error(err)
        return cache_df

    def live_deleted_status(self, filecache_df):
        live_deleted_column = list()
        external_db_df = build_dataframe(pj(self.save_dir, 'external.db'), 'files', index=None)
        external_db_fps = external_db_df['_data'].tolist()

        for row in filecache_df.itertuples():
            if any('{}'.format(basename(row.media)) in file for file in external_db_fps):
                live_deleted_column.append('Live/Accessible')
            else:
                live_deleted_column.append('Deleted')

        filecache_df['Original'] = live_deleted_column
        return filecache_df

    def thumbnail_path(self, filecache_df):
        thumbnail_col = list()
        total_rows = len(filecache_df.index)
        count = 0
        for row in filecache_df.itertuples():
            thumbnail_path_absolute = pj(self.save_dir, '{}.jpg'.format(row.Index))
            if isfile(thumbnail_path_absolute):
                thumbnail_col.append(thumbnail_path_absolute)
            else:
                thumbnail_col.append(thumbnail_path_absolute)
            count += 1
            self.progressSignal.emit([int(count/total_rows*100), thumbnail_path_absolute])

        filecache_df['media'] = thumbnail_col
        return filecache_df

    def clean_row_values(self, filecache_df):
        filecache_df['date_modified'] = pd.to_datetime(filecache_df['date_modified'], unit='ms')
        filecache_df['latest'] = pd.to_datetime(filecache_df['latest'], unit='ms')
        filecache_df['size'] = round(filecache_df['size']/1024/1024, 2)

        # Remove, rename and reorder rows
        filecache_df = filecache_df[filecache_df.columns.drop('storage')]
        filecache_df = filecache_df[['media', 'size', 'Original', 'date_modified', 'latest', '_data']]
        filecache_df.rename(columns={'size': 'Original Size', 'date_modified': 'Created', 
                                     'latest': 'Last Modified', '_data': 'File Path'}, inplace=True)
        return filecache_df

    def run(self):
        extract_instance = extract_archive.ExtractArchive(self,
                                        [clean_path(pj('com.sec.android.app.myfiles', 'databases', 'FileCache.db')), 
                                        'external.db',
                                        clean_path(pj('com.sec.android.app.myfiles', 'cache'))],
                                        self.save_dir,
                                        self.archive)

        out = extract_instance.extract()
        self.progressSignal.emit([100, out])
        filecache_df = self.build_dataframes()
        filecache_df = self.thumbnail_path(filecache_df)
        filecache_df = self.live_deleted_status(filecache_df)
        filecache_df = self.clean_row_values(filecache_df)
        self.finishedSignal.emit(filecache_df)
