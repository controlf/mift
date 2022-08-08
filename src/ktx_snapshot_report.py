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
import os
import logging
from os.path import join as pj
from os.path import basename, abspath, isfile
from datetime import datetime
from io import BytesIO
import pandas as pd
import shutil

from src import extract_archive, ktx_2_png
from src.utils import resource_path, decode_bplist, build_dataframe

# timedelta is cocoa UTC epoch - unix UTC epoch
delta = datetime(2001, 1, 1) - datetime(1970, 1, 1)


class MakeSnapShotReport(QThread):
    finishedSignal = pyqtSignal(object)
    progressSignal = pyqtSignal(list)

    def __init__(self, *args):
        QThread.__init__(self, args[0])
        self.tab_widget, self.maingui, self.archive, self.save_dir = args
        self.application_state_db = pj(self.save_dir, 'applicationState.db')

    def build_dataframes(self):
        appstate_df = None
        with open(resource_path('applicationState_query.txt'), 'r') as asq_f:
            applicationstate_query = asq_f.read().strip('\n')
        try:
            appstate_df = build_dataframe(self.application_state_db, None, query=applicationstate_query)
        except Exception as err:
            logging.error(err)
        return appstate_df

    def get_metadata(self, snapshot_rows):
        # parse the applicationState.db and produce a dictionary to match our converted snapshots
        all_snapshots_dict = {}
        for row in snapshot_rows:
            obj_nk = decode_bplist(row[0])
            if obj_nk:
                snapshots = []
                try:
                    for count, obj in enumerate(obj_nk['root']['snapshots']['NS.objects']):
                        snapshots.append(obj_nk['root']['snapshots']['NS.objects'][count]
                                         ['snapshots']['NS.objects'][count])
                except:
                    pass

                required = ['groupID', 'identifier', 'relativePath']

                if snapshots:
                    for count, snapshot in enumerate(snapshots):
                        # sometimes there is more than 1 snapshot per identifier. These may show different
                        # things visually so it is important to separate.
                        identifier = ''
                        metadata = {}
                        for k, v in snapshot.items():
                            if k in required:
                                metadata[k] = '{}'.format(obj_nk['root']['snapshots']['NS.objects'][count]
                                                          ['snapshots']['NS.objects'][count][k])

                            if k in ['creationDate', 'expirationDate', 'lastUsedDate']:
                                try:
                                    ts = '{}'.format(obj_nk['root']['snapshots']['NS.objects'][count]
                                                     ['snapshots']['NS.objects'][count][k]['NS.time'])
                                    metadata[k] = datetime.fromtimestamp(int(float(ts))) + delta
                                except:
                                    pass

                            if k == 'identifier':
                                identifier = v

                            all_snapshots_dict['{}'.format(identifier)] = metadata

        return all_snapshots_dict

    def build_snapshot_df(self, all_snapshots_dict):
        ktx_list = [pj(self.save_dir, f) for f in os.listdir(self.save_dir) if f.endswith('.ktx')]
        ktx_count = len(ktx_list)
        ktx = ktx_2_png.KTXReader()

        count = 0
        unsupported = 0
        for ktx_f in ktx_list:
            count += 1
            ktx_png_fn = pj(self.save_dir, '{}.png'.format(basename(ktx_f)))
            try:
                ktx_f_bytes = BytesIO(open(ktx_f, 'rb').read())
                ktx.convert_to_png(ktx_f_bytes, ktx_png_fn)
                os.remove(ktx_f)
                self.progressSignal.emit([round(count / ktx_count * 100),
                                          'Decompressing: {} - Success'.format(basename(ktx_f))])
            except Exception as err:
                unsupported += 1
                logging.error('{} - {}'.format(basename(ktx_f), err))
                os.remove(ktx_f)
                shutil.copy(resource_path('blank_jpeg.png'), ktx_png_fn)  # copy a blank
                self.progressSignal.emit([round(count / ktx_count * 100),
                                          'Decompressing: {} - Error (check logs)'.format(basename(ktx_f))])

            app_guid = basename(ktx_f)[:36]
            try:
                all_snapshots_dict[app_guid]['media'] = abspath(ktx_png_fn)
            except KeyError:
                # some ktx will not be attributed to an application/package
                all_snapshots_dict['Unattributed_{}'.format(count)] = dict()
                all_snapshots_dict['Unattributed_{}'.format(count)]['media'] = abspath(ktx_png_fn)

        self.progressSignal.emit([100, '{} unsupported files detected'.format(unsupported)])

        # clean up system/default ktx items as these are not evidential and cause issues when displaying.
        rem_list = list()
        for k, v in all_snapshots_dict.items():
            if 'media' not in v:
                rem_list.append(k)
        for s in rem_list:
            del all_snapshots_dict[s]

        self.progressSignal.emit([100, '{} snapshots recovered!'.format(len(all_snapshots_dict.keys()))])

        df = pd.DataFrame(all_snapshots_dict).T.rename_axis('GUID').reset_index()
        # Remove, rename and reorder rows
        df = df[df.columns.drop('identifier')]
        df.rename(columns={'relativePath': 'File Name', 'groupID': 'Group ID',
                           'GUID': 'GUID Identifier', 'creationDate': 'Created Date',
                           'lastUsedDate': 'Last Used Date'}, inplace=True)
        df = df[['media', 'GUID Identifier', 'Group ID', 'Created Date', 'Last Used Date', 'File Name']]
        df = df.fillna('')
        return df

    def run(self):
        extract_instance = extract_archive.ExtractArchive(self, ['applicationState.db', '@2x.'],
                                                          self.save_dir, self.archive)
                                        
        out = extract_instance.extract()
        self.progressSignal.emit([100, out])
        appstate_df = self.build_dataframes()
        all_snapshots_dict = self.get_metadata(appstate_df.values.tolist())
        df = self.build_snapshot_df(all_snapshots_dict)
        self.finishedSignal.emit(df)
