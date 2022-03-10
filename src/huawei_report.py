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
from os.path import dirname, basename
from time import strftime
from datetime import datetime
import webbrowser as wb
import re
import shutil
import base64


from src import extract_archive, html_utils
from src.utils import refresh_temp_dir, clean_path, build_dataframe


def find_jpeg(cachefile):
    # generator for parsing our cache files
    cachefile = open(cachefile, 'rb')
    cache_contents = cachefile.read()
    cachefile.close()
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
            yield result, original_timestamp, gallery_local_media_id


class MakeHuaweiReport(QWidget):
    def __init__(self, *args):
        super(MakeHuaweiReport, self).__init__(parent=args[0])
        self.maingui, self.archive, self.report_dir, self.save_dir = args
        self.gallery_db = pj(self.save_dir, 'gallery.db')
        self._init_archive_extraction()

    def _progress_archive_extraction(self, txt):
        self.maingui.status_lbl.setText('{}'.format(txt))

    def _finished_archive_extraction(self, txt):
        self.maingui.status_lbl.setText('{}'.format(txt))
        gallery_df = None
        try:
            gallery_df = build_dataframe(self.gallery_db, 'gallery_media')
        except Exception as err:
            self.maingui.reset_widgets()
            self.maingui.output_display.insertPlainText('Error - Could not parse the gallery.db.\n\nRefer to logs')
            logging.error(err)

        if not gallery_df.empty:
            self._init_thread(self.archive, gallery_df, self.gallery_db, self.save_dir)
        else:
           self.maingui.output_display.insertPlainText('Error - gallery.db database is empty') 

    def _init_archive_extraction(self):
        self._extract_archive_thread = extract_archive.ExtractArchiveThread(self,
                                                [clean_path(pj('com.android.gallery3d', 'databases', 'gallery.db')),
                                                 clean_path(pj('Android', 'data', 'com.android.gallery3d', 'cache'))],
                                                 self.save_dir, self.archive)
        self._extract_archive_thread.progressSignal.connect(self._progress_archive_extraction)
        self._extract_archive_thread.finishedSignal.connect(self._finished_archive_extraction)
        self._extract_archive_thread.start()

    def _progress_report(self, value):
        self.maingui.progress_bar.setValue(value)

    def _finished_report(self, report_path):
        self.maingui.progress_bar.setValue(100)
        self.maingui.output_display.clear()
        self.maingui.status_lbl.setText('Report generated successfully!')
        self.maingui.finished_btn.show()
        wb.open(report_path)

    def _init_thread(self, archive, gallery_df, gallery_db, save_dir):
        self.maingui.progress_bar.show()
        for btn in [self.maingui.select_datadir_btn, self.maingui.select_sony_btn, self.maingui.select_samsung_btn,
                    self.maingui.select_huawei_btn, self.maingui.select_ios_photos_btn,
                    self.maingui.select_ios_snapshots_btn]:
            btn.hide()
        self.maingui.progress_bar.setMaximum(100)
        self.maingui.progress_bar.setValue(0)
        self._thread = MakeHuaweiReportThread(self, archive, gallery_df, gallery_db, save_dir, self.report_dir)
        self._thread.progressSignal.connect(self._progress_report)
        self._thread.finishedSignal.connect(self._finished_report)
        self._thread.start()


class MakeHuaweiReportThread(QThread):
    finishedSignal = pyqtSignal(str)
    progressSignal = pyqtSignal(int)

    def __init__(self, parent, *args):
        QThread.__init__(self, parent)
        self.archive, self.gallery_df, self.gallery_db, self.save_dir, self.report_dir = args
        self.cachefile = pj(self.save_dir, 'imgcache.0')

        dt = '{}_{}'.format(strftime('%d%m%y'), strftime('%H%M%S'))
        self.reportname = "Huawei Media Cache Report"
        self.out_fn = pj(self.report_dir, 'Huawei_Media_Cache_Report_{}.html'.format(dt))

    def check_gallery(self, ref):
        try:
            row = self.gallery_df.loc[self.gallery_df['local_media_id'] == int(ref)]
            return ("<strong>File Name:</strong> {}<br /r>"
                    "<strong>File Path:</strong> {}<br /r>"
                    "<strong>Status:</strong> Live/Accessible<br /r>".format(row['_display_name'].values[0],
                                                                             dirname(row['_data'].values[0])))
        except:
            return ("<strong>File Name:</strong> -<br /r>"
                    "<strong>File Path:</strong> -<br /r>"
                    "<strong>Status:</strong> Deleted<br /r>")

    def run(self):
        outfile = html_utils.generate_html_grid_container(self.out_fn, self.reportname, basename(self.gallery_db))
        generated = find_jpeg(self.cachefile)
        for count, yielded in enumerate(generated):
            self.progressSignal.emit(count)
            cf, timestamp, gallery_local_media_id = yielded
            thmb_b64 = base64.b64encode(cf)
            thmb_b64 = thmb_b64.decode()

            original_file_metadata = self.check_gallery(gallery_local_media_id)
            # check to see if file is live in gallery and fetch metadata
            float_img = ("""<div class="grid-item">
                                <img src="data:image/jpeg;base64,{}" alt="img" padding: 0px 10px 10px 0px width='200';
                                height='280':">
                            </div>
                            <div class="grid-item">
                                <span style="font-weight:bold; font-family: "Segoe UI"; font-size:16px">
                                Original File Metadata</span><br /r><br /r>
                                <strong>Gallery Local Media ID</strong>: {}<br /r>
                                <strong>Date Taken:</strong> {}<br /r>{}
                            </div>""".format(thmb_b64,
                                             gallery_local_media_id,
                                             datetime.utcfromtimestamp(int(timestamp)).strftime('%d-%m-%Y %H:%M:%S'),
                                             original_file_metadata))
            outfile.write(str.encode(float_img))

        end = """</div></body></html>"""
        outfile.write(str.encode(end))
        outfile.close()

        shutil.rmtree(self.save_dir, ignore_errors=True)
        logging.info('Report successfully created: {}'.format(self.out_fn))
        self.finishedSignal.emit(self.out_fn)
