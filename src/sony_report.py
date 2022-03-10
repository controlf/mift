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
import shutil
import pandas as pd
import base64

from src import extract_archive, html_utils
from src.utils import clean_path, get_sqlite_rowcount


class MakeSonyReport(QWidget):
    def __init__(self, *args):
        super(MakeSonyReport, self).__init__(parent=args[0])
        self.maingui, self.archive, self.report_dir, self.save_dir = args
        self.picnic_db = pj(self.save_dir, 'picnic')
        self._init_archive_extraction()

    def _progress_archive_extraction(self, txt):
        self.maingui.status_lbl.setText('{}'.format(txt))

    def _finished_archive_extraction(self, txt):
        self.maingui.status_lbl.setText('{}'.format(txt))
        self.row_count = 0
        try:
            self.row_count = get_sqlite_rowcount(self.picnic_db, 'ThumbnailRecord')
            self.maingui.status_lbl.setText('Found {} thumbnail records'.format(self.row_count))
        except Exception as err:
            self.maingui.reset_widgets()
            self.maingui.output_display.insertPlainText('Error - Could not parse picnic database.\n\nRefer to logs.')
            logging.error(err)

        if self.row_count > 0:
            self._init_thread(self.archive, self.picnic_db, self.save_dir)
        else:
           self.maingui.output_display.insertPlainText('Error - the picnic.db is empty') 

    def _init_archive_extraction(self):
        self._extract_archive_thread = extract_archive.ExtractArchiveThread(self,
                                                                [clean_path(pj('com.sonyericsson.album', 'databases',
                                                                               'picnic')), 'external.db',
                                                                 clean_path(pj('com.sonyericsson.album', 'cache'))],
                                                                self.save_dir,
                                                                self.archive)
        self._extract_archive_thread.progressSignal.connect(self._progress_archive_extraction)
        self._extract_archive_thread.finishedSignal.connect(self._finished_archive_extraction)
        self._extract_archive_thread.start()

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

    def _init_thread(self, archive, picnic_db, save_dir):
        self.maingui.progress_bar.show()
        for btn in [self.maingui.select_datadir_btn, self.maingui.select_sony_btn, self.maingui.select_samsung_btn,
                    self.maingui.select_huawei_btn, self.maingui.select_ios_photos_btn,
                    self.maingui.select_ios_snapshots_btn]:
            btn.hide()
        self.maingui.progress_bar.setMaximum(self.row_count)
        self.maingui.progress_bar.setValue(0)
        self._thread = MakeSonyReportThread(self, archive, picnic_db, save_dir, self.report_dir)
        self._thread.progressSignal.connect(self._progress_report)
        self._thread.statusSignal.connect(self._status_report)
        self._thread.finishedSignal.connect(self._finished_report)
        self._thread.start()


class MakeSonyReportThread(QThread):
    finishedSignal = pyqtSignal(str)
    progressSignal = pyqtSignal(int)
    statusSignal = pyqtSignal(str)

    def __init__(self, parent, *args):
        QThread.__init__(self, parent)
        self.archive, self.picnic_db, self.save_dir, self.report_dir = args

        dt = '{}_{}'.format(strftime('%d%m%y'), strftime('%H%M%S'))
        self.reportname = 'Sony Thumbnail Report'
        self.out_fn = pj(self.report_dir, 'Sony_Thumbnail_Report_{}.html'.format(dt))

    def run(self):
        outfile = html_utils.generate_html_grid_container(self.out_fn, self.reportname, basename(self.picnic_db))
        conn = sqlite3.connect(self.picnic_db)
        query = ["SELECT * FROM ThumbnailRecord "
                 "LEFT JOIN ImageRecord ON ThumbnailRecord.imageRecord = ImageRecord.key "
                 "LEFT JOIN ThumbnailMetadata ON ThumbnailRecord.id = ThumbnailMetadata.thumbId "
                 "WHERE customThumbKey = 'FileDate' "
                 "ORDER BY ThumbnailRecord.id DESC"]
        picnic_df = pd.read_sql(query[0], conn)
        conn.close()

        conn = sqlite3.connect(pj(self.save_dir, 'external.db'))
        conn.row_factory = lambda cursor, row: row[0]
        c = conn.cursor()
        externaldb_files = c.execute("SELECT _data FROM files").fetchall()
        c.close()
        conn.close()

        for row in picnic_df.itertuples():
            self.progressSignal.emit(1)
            thumbnail_img_absolute = pj(self.save_dir, '{}'.format(row.localPath.split('/')[-1]))

            thmb_data = open(thumbnail_img_absolute, 'rb').read()
            thmb_b64 = base64.b64encode(thmb_data)
            thmb_b64 = thmb_b64.decode()

            if any('{}'.format(basename(row.uri)) in file for file in externaldb_files):
                deleted_status = 'Live/Accessible'
            else:
                deleted_status = 'Deleted'
            if isfile(thumbnail_img_absolute):
                float_img = ("""<div class="grid-item">
                                    <img src="data:image/jpeg;base64,{}" alt="img" padding: 0px 10px 10px 0px 
                                    width='200';height='280':">
                                </div>
                                <div class="grid-item">
                                    <span style="font-weight:bold; font-family: "Segoe UI"; 
                                    font-size:16px">Original File Metadata</span><br /r><br /r>
                                    <strong>Path:</strong> {}<br /r>
                                    <strong>Name:</strong> {}<br /r>
                                    <strong>Created:</strong> {}<br /r>
                                    <strong>Original Status:</strong> {}<br /r>
                                    <strong>Thumbnail:</strong> {}
                                </div>""".format(thmb_b64,
                                                 dirname(row.uri),
                                                 basename(row.uri),
                                                 datetime.utcfromtimestamp(int(row.customThumbValue)
                                                                           / 1000.0).strftime('%d-%m-%Y %H:%M:%S'),
                                                 deleted_status,
                                                 basename(thumbnail_img_absolute)))
                outfile.write(str.encode(float_img))
            self.statusSignal.emit('Parsed: {}'.format(row.localPath.split('/')[-1]))

        end = """</div></body></html>"""
        outfile.write(str.encode(end))
        outfile.close()

        shutil.rmtree(self.save_dir, ignore_errors=True)
        logging.info('Report successfully created: {}'.format(self.out_fn))
        self.finishedSignal.emit(self.out_fn)