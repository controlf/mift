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

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
import os
import logging
from os.path import join as pj
from os.path import *
from time import strftime
from datetime import datetime
import webbrowser as wb
import sqlite3
import shutil
import pandas as pd
import base64

from src import extract_archive
from src.utils import clean_path, get_sqlite_rowcount, build_dataframe


class MakeSonyReport(QThread):
    finishedSignal = pyqtSignal(object)
    progressSignal = pyqtSignal(list)

    def __init__(self, *args):
        QThread.__init__(self, args[0])
        self.tab_widget, self.maingui, self.archive, self.save_dir = args
        self.picnic_db = pj(self.save_dir, 'picnic')

    def build_dataframes(self):
        self.row_count = 0
        cache_df = None
        try:
            self.row_count = get_sqlite_rowcount(self.picnic_db, 'ThumbnailRecord')
            query = ("SELECT * FROM ThumbnailRecord "
                    "LEFT JOIN ImageRecord ON ThumbnailRecord.imageRecord = ImageRecord.key "
                    "LEFT JOIN ThumbnailMetadata ON ThumbnailRecord.id = ThumbnailMetadata.thumbId "
                    "WHERE customThumbKey = 'FileDate' "
                    "ORDER BY ThumbnailRecord.id DESC")
            cache_df = build_dataframe(self.picnic_db, 'ThumbnailRecord', index=['id'], query=query)
        except Exception as err:
            logging.error(err)
        return cache_df

    def live_deleted_status(self, cache_df):
        live_deleted_column = list()
        external_db_df = build_dataframe(pj(self.save_dir, 'external.db'), 'files', index=None)
        external_db_fps = external_db_df['_data'].tolist()

        for row in cache_df.itertuples():
            if any('{}'.format(basename(row.uri)) in file for file in external_db_fps):
                live_deleted_column.append('Live/Accessible')
            else:
                live_deleted_column.append('Deleted')

        cache_df['Original'] = live_deleted_column
        return cache_df

    def thumbnail_path(self, cache_df):
        thumbnail_col = list()
        total_rows = len(cache_df.index)
        count = 0
        for row in cache_df.itertuples():
            thumbnail_img_absolute = None
            thumbnail_img_absolute = pj(self.save_dir, '{}'.format(basename(row.localPath)))
            if isfile(thumbnail_img_absolute):
                thumbnail_col.append(thumbnail_img_absolute)
            else:
                thumbnail_col.append(thumbnail_img_absolute)
            count += 1
            self.progressSignal.emit([int(count/total_rows*100), thumbnail_img_absolute])

        cache_df['media'] = thumbnail_col
        return cache_df

    def clean_row_values(self, cache_df):
        cache_df['lastAccess'] = pd.to_datetime(cache_df['lastAccess'], unit='ms')
        cache_df['customThumbValue'] = pd.to_datetime(cache_df['customThumbValue'], unit='ms')

        # Remove, rename and reorder rows
        cache_df.rename(columns={'area': 'Thumbnail Type', 'uri': 'Original File Path', 
                                 'lastAccess': 'Last Access', 'localPath': 'Thumbnail File Path',
                                 'imgWidth': 'Width', 'imgHeight': 'Height', 'mimeType': 'Media Type',
                                 'Original': 'Original Status', 'customThumbValue': 'Original Created'}, 
                                 inplace=True)
        cache_df = cache_df[['media', 'Thumbnail Type', 'Original File Path', 'Original Created', 
                             'Last Access', 'Thumbnail File Path', 'Width', 'Height', 'Media Type', 
                             'Original Status']]
        return cache_df

    def run(self):
        extract_instance = extract_archive.ExtractArchive(
                self,
                [clean_path(pj('com.sonyericsson.album', 'databases','picnic')), 
                'external.db',
                clean_path(pj('com.sonyericsson.album', 'cache'))],
                self.save_dir,
                self.archive
                )
                                        
        out = extract_instance.extract()
        self.progressSignal.emit([100, out])
        cache_df = self.build_dataframes()
        cache_df = self.thumbnail_path(cache_df)
        cache_df = self.live_deleted_status(cache_df)
        cache_df = self.clean_row_values(cache_df)
        self.finishedSignal.emit(cache_df)
