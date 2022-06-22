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

from PyQt5.QtCore import pyqtSignal, QThread
from os.path import join as pj
from os.path import basename, isfile
import pandas as pd
import sqlite3
import numpy as np
import functools

from src import extract_archive
from src.utils import *

# This dictionary stores each database and a reference to its tables that require building, renaming, reordering and
# joining. A single joiner should be identified across multiple databases while each table from a
# database should have an identifier renamed to _joiner_ for internal joining prior to the main db join.
# This dictionary assumes the main table will be first, so that all other tables join outer left to it
sec_dict = {'dbs': {'media.db':
                        {'path': '',
                         'tables':
                             {'files':
                                  {'cols': {'_id': {'new': '_joiner_'},
                                            'media_id': {'new': 'media_id'},
                                            '_size': {'new': 'Size'},
                                            'datetaken': {'new': 'Captured'},
                                            'date_added': {'new': 'Added'},
                                            'date_modified': {'new': 'Modified'},
                                            'media_type': {'new': 'Type',
                                                           'keys': {0: 'Folder',
                                                                    1: 'Image',
                                                                    2: 'Music',
                                                                    3: 'Video'}},
                                            'mime_type': {'new': 'Mime Type'},
                                            'title': {'new': 'Filename'},
                                            '_display_name': {'new': 'Display Name'},
                                            'orientation': {'new': 'Orientation'},
                                            'latitude': {'new': 'Latitude'},
                                            'longitude': {'new': 'Longitude'},
                                            'addr': {'new': 'Address'},
                                            'bookmark': {'new': 'Bookmark'},
                                            'bucket_id': {'new': 'Identifier'},
                                            'bucket_display_name': {'new': 'Identifier Name'},
                                            'isprivate': {'new': 'Private'},
                                            'duration': {'new': 'Duration'},
                                            'recording_mode': {'new': 'Recording Mode',
                                                               'keys': {5: 'Slow Motion',
                                                                        12: 'HDR'}},
                                            'video_codec_info': {'new': 'Video Codec'},
                                            'audio_codec_info': {'new': 'Audio Codec'},
                                            'isPlayed': {'new': 'Played',
                                                         'keys': {1: 'Yes',
                                                                  0: 'No'}},
                                            'album': {'new': 'Album Title'},
                                            'resolution': {'new': 'Resolution'},
                                            'captured_url': {'new': 'Captured URL'},
                                            'captured_app': {'new': 'Captured App'},
                                            'owner_package_name': {'new': 'Parent Package'},
                                            'is_hide': {'new': 'Hidden'},
                                            'is_trashed': {'new': 'Trashed',
                                                           'keys': {1: 'Yes',
                                                                    0: 'No'}},
                                            'deleted': {'new': 'Deleted'},
                                            'relative_path': {'new': 'System Path'},
                                            'is_favorite': {'new': 'Favourite',
                                                            'keys': {1: 'Yes',
                                                                     0: 'No'}},
                                            'is_cloud': {'new': 'Cloud Asset'},
                                            'cloud_server_path': {'new': 'Cloud Server Path'},
                                            'original_file_hash': {'new': 'Original Hash'}},
                                   'queries': {1: {'query': "SELECT * FROM files"}},
                                   'df': dict()},

                              'usertag':
                                  {'cols': {'sec_media_id': {'new': '_joiner_'},
                                            'tag': {'new': 'User Generated Tag'},
                                            'timestamp': {'new': 'Tag Created'}},
                                   'queries': {1: {'query': "SELECT * FROM usertag"}},
                                   'df': dict()}},
                         'df': ''},

                    'external.db':
                        {'path': '',
                         'tables':
                             {'files':
                                  {'cols': {'_id': {'new': 'media_id'},
                                            'is_download': {'new': 'Downloaded',
                                                            'keys': {1: 'Yes',
                                                                     0: 'No'}}},
                                   'queries': {1: {'query': "SELECT _id, is_download FROM files"}},
                                   'df': dict()}},
                         'df': ''},

                    'cmh.db':
                        {'path': '',
                         'tables':
                             {'files':
                                  {'cols': {'isUsedAsWallpaper': {'new': 'Used As Wallpaper',
                                                                  'keys': {1: 'Yes',
                                                                           0: 'No'}},
                                            '_id': {'new': '_joiner_'},
                                            'media_id': {'new': 'media_id'}},
                                   'queries': {1: {'query': "SELECT * FROM files"}},
                                   'df': dict()},
                              'ocr_tag':
                                  {'cols': {'fk_file_id': {'new': '_joiner_'},
                                            'image_ocr_tag': {'new': 'OCR Tag'},
                                            'tag_added_date': {'new': 'OCR Added'}},
                                   'queries': {1: {'query': "SELECT * FROM ocr_tag"}},
                                   'df': dict()}},
                        'df': ''}},

            'table_joins': {'main_key': 'media_id'}}


class MakeSamsungReport(QThread):
    finishedSignal = pyqtSignal(object)
    progressSignal = pyqtSignal(list)

    def __init__(self, *args):
        QThread.__init__(self, args[0])
        self.tab_widget, self.maingui, self.archive, self.save_dir = args

    def build_dataframes(self):
        # creates the dataframes needed, drops, reorders and renames the columns
        # and then stores the dataframe in the sec dictionary. Multiple tables in each databases
        # will have their joining identifier renamed to _joiner_ during renaming.
        for db, db_data in sec_dict['dbs'].items():
            for table, mods in db_data['tables'].items():
                for query, params in mods['queries'].items():
                    # build the dataframe
                    if 'index' in params:
                        df = build_dataframe(db_data['path'], None, query=params['query'], index=[params['index']])
                    else:
                        df = build_dataframe(db_data['path'], None, query=params['query'])
                    df = df.reset_index()

                    if mods['cols']:
                        # reorder and drop columns
                        df = df[mods['cols'].keys()]

                        # rename columns whilst updating column values
                        rename_dict = dict()
                        for k, v in mods['cols'].items():
                            rename_dict.update({k: v['new']})

                            if 'keys' in v:
                                for old, new in v['keys'].items():
                                    df.loc[df[k] == old, k] = new
                        df.rename(columns=rename_dict, inplace=True)

                    # add dataframe to dictionary under its table name
                    mods['df'][table] = df
        return

    def join_tables(self):
        # join individual dataframes from each table of a database using the renamed join '_joiner_'
        for db, db_data in sec_dict['dbs'].items():
            if len(db_data['tables'].keys()) > 1:
                df_list = list()
                for table, mods in db_data['tables'].items():
                    df_list.append(mods['df'][table])

                df_joined = functools.reduce(lambda left, right:
                                             pd.merge(left, right,
                                                      left_on='_joiner_',
                                                      right_on='_joiner_',
                                                      how='left'),
                                             df_list)
                db_data['df'] = df_joined
            else:
                # Just a single table, no joins required
                for table, mods in db_data['tables'].items():
                    db_data['df'] = mods['df'][table]
        return

    def join_dataframes(self):
        # join all main dataframes from the databases using the main key
        tables = list()
        j_key = sec_dict['table_joins']['main_key']
        for db, db_data in sec_dict['dbs'].items():
            tables.append(db_data['df'])

        df_joined = functools.reduce(lambda left, right:
                                     pd.merge(left, right,
                                              left_on=j_key,
                                              right_on=j_key,
                                              how='left'),
                                     tables)
        # a spot of cleaning!
        df_joined.replace(np.nan, '', inplace=True)
        df_joined['OCR Tag'] = df_joined['OCR Tag'].apply(lambda x: clean_ascii(x))

        # fetch a list of the filenames so we can extract them from the archive
        files = df_joined['Display Name'].values.tolist()
        return df_joined, files

    def extract_files(self, files):
        extract_instance = extract_archive.ExtractArchive(self, files, self.save_dir, self.archive)
        out = extract_instance.extract()
        return out

    def sanitise_sec_dict(self):
        # check our databases exist
        for key, path in {'media.db': pj(self.save_dir, 'media.db'),
                          'external.db': pj(self.save_dir, 'external.db'),
                          'cmh.db': pj(self.save_dir, 'cmh.db')}.items():
            if isfile(path):
                sec_dict['dbs'][key]['path'] = path
                # execute a checkpoint so we have up-to-date data
                # TO DO: use CF's forensic sqlite parser to recover deleted.
                with sqlite3.connect(path) as conn:
                    conn.cursor().execute('PRAGMA wal_checkpoint;')
                    conn.commit()
            else:
                del sec_dict['dbs'][key]
        return

    def clean_row_values(self, df):
        # convert columns to timestamps based on their format
        for date_col, format_ in {'Captured': 'ms', 'Added': 's', 'Modified': 's',
                                  'Tag Created': 'ms', 'OCR Added': 'ms'}.items():
            df[date_col] = df[date_col].apply(
                lambda x: pd.to_datetime(x, unit=format_, errors='ignore').strftime('%d-%m-%Y %H:%M:%S')
                if len(str(x)) != 0 else "")

        df['Size (MB)'] = round(df['Size']/1024/1024, 2)

        # Remove, rename and reorder rows
        for col in df.columns.values.tolist():
            if '_joiner_' in col or col == 'media_id':
                df = df[df.columns.drop(col)]
        return df

    def combiner(self, df):
        grouped_dict = {'File Info': ['Filename', 'Display Name', 'System Path', 'Size',
                                      'Size (MB)', 'Resolution', 'Type', 'Mime Type', 'Original Hash'],
                        'Other': ['Parent Package', 'Identifier', 'Identifier Name', 'Orientation', 'Private',
                                  'Duration', 'Recording Mode', 'Video Codec', 'Audio Codec'],
                        'Timestamps': ['Captured', 'Added', 'Modified'],
                        'Location': ['Latitude', 'Longitude', 'Address'],
                        'Album': ['Album Title'],
                        'Trash': ['Trashed', 'Deleted'],
                        'Cloud MetaData': ['Cloud Asset', 'Cloud Server Path'],
                        'Activity': ['Favourite', 'Played', 'Hidden', 'Bookmark', 'Captured URL', 'Captured App',
                                     'User Generated Tag', 'Tag Created', 'Downloaded', 'Used As Wallpaper',
                                     'OCR Tag', 'OCR Added']
                        }
        for group_name, col_list in grouped_dict.items():
            combined = list()
            for idx, row in df.iterrows():
                combined.append(row_combiner(row, col_list))
            df[group_name] = combined
            # Drop the columns we have merged
            df.drop(col_list, axis=1, inplace=True)
        return df

    def generate_thumbnails(self):
        count = 0
        img_list = [pj(self.save_dir, img) for img in os.listdir(self.save_dir) if not img.endswith('.db')]
        img_list_length = len(img_list)
        for img in img_list:
            img_raw, ext = media_support(img)
            img_raw.save(img, format=ext.upper())
            count += 1
            self.progressSignal.emit([int(count/img_list_length*100), basename(img)])
        return

    def run(self):
        errors = False
        out = self.extract_files([clean_path(pj('com.android.providers.media.module', 'databases', 'external.db')),
                                  clean_path(pj('com.samsung.android.providers.media', 'databases', 'media.db')),
                                  clean_path(pj('com.samsung.cmh', 'databases', 'cmh.db'))])
        for db in ['external.db', 'media.db', 'cmh.db']:
            if isfile(pj(self.save_dir, db)):
                pass
            else:
                errors = True
        if errors:
            self.progressSignal.emit([0, '[!!] Errors detected. Some databases were missing. '
                                         'The Samsung archive may be incomplete or the version '
                                         'of the Samsung OS is not supported.'])
            self.finishedSignal.emit(pd.DataFrame())

        self.progressSignal.emit([25, 'Extracted required databases'])
        self.sanitise_sec_dict()
        self.build_dataframes()
        self.progressSignal.emit([50, 'Built dataframes'])
        self.join_tables()
        df, files = self.join_dataframes()
        self.progressSignal.emit([60, 'Extracting media files...'])
        out = self.extract_files(files)
        self.progressSignal.emit([100, 'Media extracted'])
        media = [pj(self.save_dir, f) for f in files]
        df['media'] = media
        self.progressSignal.emit([0, 'Converting media format for GUI Display...'])
        self.generate_thumbnails()
        self.progressSignal.emit([100, 'Media converted'])
        self.progressSignal.emit([100, 'Cleaning and formatting rows...'])
        df = self.clean_row_values(df)
        self.progressSignal.emit([100, 'Grouping categories...'])
        df = self.combiner(df)
        df = df.fillna(np.nan).replace([np.nan], [None])
        self.finishedSignal.emit(df)
