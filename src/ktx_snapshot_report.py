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

from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import pyqtSignal, QThread
import os
import logging
from os.path import join as pj
from os.path import dirname, basename, isfile
from time import strftime
from datetime import datetime
import webbrowser as wb
import sqlite3
import base64
from io import BytesIO
import zipfile

from src import extract_archive, html_utils, ktx_2_png
from src.utils import resource_path, decode_bplist

# timedelta is cocoa UTC epoch - unix UTC epoch
delta = datetime(2001, 1, 1) - datetime(1970, 1, 1)


class MakeSnapShotReport(QWidget):
    def __init__(self, *args):
        super(MakeSnapShotReport, self).__init__(parent=args[0])
        self.maingui, self.archive, self.report_dir, self.save_dir = args
        self.save_dir = pj(self.report_dir, 'snapshots')
        self.application_state_db = pj(self.save_dir, 'applicationState.db')
        self._init_archive_extraction()

    def _progress_archive_extraction(self, txt):
        self.maingui.status_lbl.setText('{}'.format(txt))

    def _finished_archive_extraction(self, txt):
        self.maingui.status_lbl.setText('{}'.format(txt))
        snapshot_rows = list()
        try:
            snapshot_rows = self.build_snapshot_dict(self.application_state_db)
            self.row_count = len(snapshot_rows)
        except Exception as err:
            self.maingui.reset_widgets()
            self.maingui.output_display.insertPlainText('Error - Could not parse the applicationState.db.\n\n'
                                                        'Refer to logs.')
            logging.error(err)

        if snapshot_rows:
            self._init_thread(self.archive, self.application_state_db, snapshot_rows, self.save_dir)
        else:
            self.maingui.output_display.insertPlainText('Error - missing snapshot records from applicationState.db')

    def _init_archive_extraction(self):
        self._extract_archive_thread = extract_archive.ExtractArchiveThread(self,
                                                            ['applicationState.db'],
                                                            self.save_dir,
                                                            self.archive)
        self._extract_archive_thread.progressSignal.connect(self._progress_archive_extraction)
        self._extract_archive_thread.finishedSignal.connect(self._finished_archive_extraction)
        self._extract_archive_thread.start()

    @staticmethod
    def build_snapshot_dict(application_state_db):
        with open(resource_path('applicationState_query.txt'), 'r') as asq_f:
            applicationstate_query = asq_f.read().strip('\n')
        conn = sqlite3.connect(application_state_db)
        cursor = conn.cursor()
        cursor.execute(applicationstate_query)
        snapshot_rows = cursor.fetchall()
        return snapshot_rows

    def _progress_report(self, value):
        self.maingui.progress_bar.setValue(value)

    def _status_report(self, msg):
        self.maingui.status_lbl.setText(msg)

    def _finished_report(self, report_path):
        self.maingui.progress_bar.setValue(self.row_count)
        self.maingui.output_display.clear()
        self.maingui.status_lbl.setText('Report generated successfully!')
        self.maingui.finished_btn.show()
        wb.open(report_path)

    def _init_thread(self, archive, application_state_db, snapshot_rows, save_dir):
        self.maingui.progress_bar.show()
        for btn in [self.maingui.select_datadir_btn, self.maingui.select_sony_btn, self.maingui.select_samsung_btn,
                    self.maingui.select_huawei_btn, self.maingui.select_ios_photos_btn,
                    self.maingui.select_ios_snapshots_btn]:
            btn.hide()
        self.maingui.progress_bar.setMaximum(self.row_count)
        self.maingui.progress_bar.setValue(0)
        self._thread = MakeSnapShotReportThread(self, archive, application_state_db, snapshot_rows, save_dir)
        self._thread.progressSignal.connect(self._progress_report)
        self._thread.statusSignal.connect(self._status_report)
        self._thread.finishedSignal.connect(self._finished_report)
        self._thread.start()


class MakeSnapShotReportThread(QThread):
    finishedSignal = pyqtSignal(str)
    progressSignal = pyqtSignal(int)
    statusSignal = pyqtSignal(str)

    def __init__(self, parent, *args):
        QThread.__init__(self, parent)
        self.archive, self.application_state_db, self.snapshot_rows, self.save_dir = args

        self.date = '{}_{}'.format(strftime('%d%m%y'), strftime('%H%M%S'))
        self.reportname = 'iOS Carousel Snapshot Report'
        self.out_fn = pj(dirname(self.save_dir), 'iOS_Snapshot_Report_{}.html'.format(self.date))

    def run(self):
        html_report = html_utils.generate_html_grid_container(self.out_fn, self.reportname, 
                                                              basename(self.application_state_db))
        self.statusSignal.emit('Parsing binary plists...')
        all_snapshots_dict = self.get_metadata(self.snapshot_rows)
        self.statusSignal.emit('{} KTX files found. Some files may not be recoverable. '
                               'Initiating...'.format(len(all_snapshots_dict.keys())))

        ktx = ktx_2_png.KTXReader()

        ktx_dict = {}  # There are many duplicated snapshots and entries in applicationState so we need a condensed dict
        with zipfile.ZipFile(self.archive, 'r') as zip_obj:
            filepaths = zip_obj.namelist()
            file_count = len(filepaths)

            count = 0
            for fn in filepaths:
                # iterate over each unique ktx file
                if fn.endswith('.ktx'):
                    ktx_png = pj(self.save_dir, '{}.png'.format(basename(fn)))
                    self.statusSignal.emit('Decompressing: {}...'.format(basename(fn)))
                    snapshot_fn = basename(ktx_png)[:36]
                    if ktx_png in ktx_dict.keys():
                        pass
                    else:
                        ktx_dict[ktx_png] = {'snapshot_fn': snapshot_fn, 
                                             'relative_path': '', 
                                             'metadata': []}

                    f = BytesIO(zip_obj.read(fn))
                    try:
                        ktx.convert_to_png(f, ktx_png)
                    except Exception as err:
                        logging.error('{} - {}'.format(basename(fn), err))
                        continue

                    if isfile(ktx_png):
                        ktx_dict[ktx_png]['relative_path'] = 'snapshots/{}'.format(basename(ktx_png))

                        if snapshot_fn in all_snapshots_dict:
                            metadata = all_snapshots_dict.get(snapshot_fn)
                            for k, v in metadata.items():
                                # if is a datetime object, convert it, otherwise store k, v
                                if k in ['creationDate', 'lastUsedDate', 'expirationDate']:
                                    ktx_dict[ktx_png]['metadata'].append('<strong>{}:</strong>{}<br /r>'.format(k,
                                                                              datetime.fromtimestamp(int(float(v)))
                                                                              + delta))
                                else:
                                    ktx_dict[ktx_png]['metadata'].append('<strong>{}:</strong> {}<br /r>'.format(k, v))

                count += 1
                self.progressSignal.emit(round(count/file_count * 100))
                    
        self.statusSignal.emit('Finished decompressing. Generating report...')
        for ktx_png in ktx_dict.keys():
            if isfile(ktx_png):
                snapshot_data = ("""<div class="grid-item">
                                        <img src="{}" alt="img" padding: 0px 10px 10px 0px width='200';
                                        height='280':">
                                    </div>
                                    <div class="grid-item">
                                        <span style="font-weight:bold; font-family: "Segoe UI"; 
                                        font-size:16px">Snapshot Properties</span><br /r><br /r>
                                        <strong>Snapshot Filename:</strong> {}<br /r><br /r>
                                        <strong>Metadata</strong><br /r>{}		
                                    </div>""".format(ktx_dict[ktx_png]['relative_path'],
                                                     basename(ktx_png),
                                                     ''.join(ktx_dict[ktx_png]['metadata'])))

                html_report.write(str.encode(snapshot_data))

        end = """</div></body></html>"""
        html_report.write(str.encode(end))
        html_report.close()
        logging.info('Report successfully created: {}'.format(self.out_fn))
        self.finishedSignal.emit(self.out_fn)

    @staticmethod
    def get_metadata(snapshot_rows):
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

                required = ['referenceSize', 'imageScale', 'groupID', 'variantID', 'identifier', 'imageOpaque',
                            'relativePath', 'identifier']

                if snapshots:
                    for count, snapshot in enumerate(snapshots):
                        # sometimes there are more than 1 snapshot per identifier. These may show different
                        # things visually so it is important to split them up as separate snapshots in the html.
                        identifier = ''
                        metadata = {}
                        for k, v in snapshot.items():
                            if k in required:
                                metadata[k] = '{}'.format(obj_nk['root']['snapshots']['NS.objects'][count]
                                                          ['snapshots']['NS.objects'][count][k])

                            if k in ['creationDate', 'expirationDate', 'lastUsedDate']:
                                try:
                                    metadata[k] = '{}'.format(obj_nk['root']['snapshots']['NS.objects'][count]
                                                              ['snapshots']['NS.objects'][count][k]['NS.time'])
                                except:
                                    pass

                            if k == 'identifier':
                                identifier = v

                            all_snapshots_dict['{}'.format(identifier)] = metadata

        return all_snapshots_dict