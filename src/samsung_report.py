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
import logging
from os.path import join as pj
from os.path import dirname, basename, isfile
from time import strftime
from datetime import datetime
import webbrowser as wb
import sqlite3
import shutil
import base64

from src import extract_archive, html_utils
from src.utils import clean_path, get_sqlite_rowcount, build_dataframe


class MakeSamsungReport(QWidget):
    def __init__(self, *args):
        super(MakeSamsungReport, self).__init__(parent=args[0])
        self.maingui, self.archive, self.report_dir, self.save_dir = args
        self.filecachedb = pj(self.save_dir, 'FileCache.db')
        self._init_archive_extraction()

    def _progress_archive_extraction(self, txt):
        self.maingui.status_lbl.setText('{}'.format(txt))

    def _finished_archive_extraction(self, txt):
        self.maingui.status_lbl.setText('{}'.format(txt))
        self.row_count = 0
        cache_df = None
        try:
            self.row_count = get_sqlite_rowcount(self.filecachedb, 'FileCache')
            cache_df = build_dataframe(self.filecachedb, 'FileCache', index=['_index'])
        except Exception as err:
            self.maingui.reset_widgets()
            self.maingui.output_display.insertPlainText('Error - Could not parse the FileCache.db\n\nRefer to logs.')
            logging.error(err)

        if not cache_df.empty:
            self._init_thread(cache_df, self.filecachedb, self.archive, self.save_dir)
        else:
            self.maingui.output_display.insertPlainText('Error - The FileCache database is empty')

    def _init_archive_extraction(self):
        self._extract_archive_thread = extract_archive.ExtractArchiveThread(self,
                                                            [clean_path(pj('com.sec.android.app.myfiles', 'databases',
                                                                'FileCache.db')), 'external.db',
                                                            clean_path(pj('com.sec.android.app.myfiles', 'cache'))],
                                                            self.save_dir,
                                                            self.archive)
        self._extract_archive_thread.progressSignal.connect(self._progress_archive_extraction)
        self._extract_archive_thread.finishedSignal.connect(self._finished_archive_extraction)
        self._extract_archive_thread.start()

    def _progress_report(self, value):
        self.maingui.progress_bar.setValue(value)

    def _finished_report(self, report_path):
        self.maingui.progress_bar.setValue(self.row_count)
        self.maingui.output_display.clear()
        self.maingui.status_lbl.setText('Report generated successfully!')
        self.maingui.finished_btn.show()
        wb.open(report_path)

    def _init_thread(self, cache_df, filecachedb, archive, save_dir):
        self.maingui.progress_bar.show()
        for btn in [self.maingui.select_datadir_btn, self.maingui.select_sony_btn, self.maingui.select_samsung_btn,
                    self.maingui.select_huawei_btn, self.maingui.select_ios_photos_btn,
                    self.maingui.select_ios_snapshots_btn]:
            btn.hide()
        self.maingui.progress_bar.setMaximum(self.row_count)
        self.maingui.progress_bar.setValue(0)
        self._thread = MakeSamsungReportThread(self, cache_df, filecachedb, archive, save_dir, self.report_dir)
        self._thread.progressSignal.connect(self._progress_report)
        self._thread.finishedSignal.connect(self._finished_report)
        self._thread.start()


class MakeSamsungReportThread(QThread):
    finishedSignal = pyqtSignal(str)
    progressSignal = pyqtSignal(int)

    def __init__(self, parent, *args):
        QThread.__init__(self, parent)
        self.filecache_df, self.filecachedb, self.archive,self.save_dir, self.report_dir = args

        dt = '{}_{}'.format(strftime('%d%m%y'), strftime('%H%M%S'))
        self.reportname = 'Samsung Media Cache Report'
        self.out_fn = pj(self.report_dir, 'Samsung_Report_{}.html'.format(dt))

    def run(self):
        outfile = html_utils.generate_html_grid_container(self.out_fn, self.reportname, basename(self.filecachedb))
        conn = sqlite3.connect(pj(self.save_dir, 'external.db'))
        conn.row_factory = lambda cursor, row: row[0]
        c = conn.cursor()
        externaldb_files = c.execute("SELECT _data FROM files").fetchall()
        c.close()
        conn.close()

        for row in self.filecache_df.itertuples():
            self.progressSignal.emit(1)
            cache_img_absolute = pj(self.save_dir, '{}.jpg'.format(row.Index))

            if isfile(cache_img_absolute):
                thmb_data = open(cache_img_absolute, 'rb').read()
                thmb_b64 = base64.b64encode(thmb_data)
                thmb_b64 = thmb_b64.decode()

                try:
                    path = row.path
                except:
                    path = row._2
                try:
                    created_date = row.date_modified
                except:
                    created_date = row.date

                if any('{}'.format(basename(path)) in file for file in externaldb_files):
                    deleted_status = 'Live/Accessible'
                else:
                    deleted_status = 'Deleted'
                float_img = ("""<div class="grid-item">
                                    <img src="data:image/jpeg;base64,{}" alt="img" padding: 
                                    0px 10px 10px 0px width='200';height='280':">
                                </div>
                                <div class="grid-item">
                                    <span style="font-weight:bold; font-family: "Segoe UI"; font-size:16px">
                                    Original File Metadata</span><br /r><br /r>
                                    <strong>Path:</strong> {}<br /r>
                                    <strong>Name:</strong> {}<br /r>
                                    <strong>Created:</strong> {}<br /r>
                                    <strong>Size:</strong> {}MB<br /r>
                                    <strong>Original:</strong> {}<br /r>
                                    <strong>Cache:</strong> {}
                                </div>""".format(thmb_b64,
                                                 dirname(path),
                                                 basename(path),
                                                 datetime.utcfromtimestamp(created_date
                                                                           / 1000.0).strftime('%d-%m-%Y %H:%M:%S'),
                                                 round(row.size/1024/1024, 2),
                                                 deleted_status,
                                                 basename(cache_img_absolute)))
                outfile.write(str.encode(float_img))

        end = """</div></body></html>"""
        outfile.write(str.encode(end))
        outfile.close()

        shutil.rmtree(self.save_dir, ignore_errors=True)
        logging.info('Report successfully created: {}'.format(self.out_fn))
        self.finishedSignal.emit(self.out_fn)
