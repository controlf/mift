"""
Sift

"Copyright Control-F 2021

This software is licensed 'as-is'.  You bear the risk of using it.  
In consideration for use of the software, you agree that you have not 
relied upon any, and we have made no, warranties, whether oral, written, 
or implied, to you in relation to the software.  To the extent permitted 
at law, we disclaim any and all warranties, whether express, implied, 
or statutory, including, but without limitation, implied warranties of 
non-infringement of third party rights, merchantability and fitness 
for purpose.

In no event will we be held liable to you for any loss or damage 
(including without limitation loss of profits or any indirect or 
consequential losses) arising from the use of this software."


Credits

Yogesh Khatri - KTX > PNG script/executable  (Some modifications made)
https://github.com/ydkhatri/MacForensics/tree/master/IOS_KTX_TO_PNG

CCL Forensics Binary Plist Parser
https://github.com/cclgroupltd/ccl-bplist

"""

__author__ = 'Mike Bangham - Control-F'
__version__ = '1.08'
__description__ = 'Smartphone Image Forensics Toolkit'

from PyQt5.QtWidgets import (QApplication, QWidget, QPushButton, QMainWindow, QDialog,
                             QLabel, QGridLayout, QPlainTextEdit, QGroupBox, QDialogButtonBox,
                             QProgressBar, QFileDialog)
from PyQt5.QtGui import QIcon, QFont, QPixmap, QTransform, QTextCursor
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QEvent
import os
import logging
import sys
import platform
from os.path import join as pj
from os.path import dirname, basename, isfile, abspath
from time import strftime
from datetime import datetime
import webbrowser as wb
import sqlite3
import glob
import re
import time
import shutil
import pandas as pd
import codecs
import base64
from io import BytesIO
import plistlib
import zipfile
import tarfile
import tkinter
from tkinter.filedialog import askopenfilename
import liblzfse
import astc_decomp
import struct
from PIL import Image

from src import ccl_bplist

if hasattr(Qt, 'AA_EnableHighDpiScaling'):
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)

if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

start_dir = os.getcwd()
app_data_dir = os.getenv('APPDATA')
os.makedirs(pj(app_data_dir, 'CF_SIFT'), exist_ok=True)
log_file_fp = pj(app_data_dir, 'CF_SIFT', 'logs.txt')

# timedelta is cocoa UTC epoch - unix UTC epoch
delta = datetime(2001, 1, 1) - datetime(1970, 1, 1)


# When creating out executable, we must specify our resource path where accompanying files can be accessed
# standalone script - 'res' added to path. Should be omitted when compiling executable.
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except:
        #base_path = os.path.abspath(".")
        base_path = os.path.abspath(pj(".", 'res'))
    return pj(base_path, relative_path)


# This is a short EULA which will appear at the foot of the output reports.
with open(resource_path('EULA_short.txt'), 'r') as f:
    end_of_report_eula = f.read()


def init_log():
    # init log file
    logging.basicConfig(filename=log_file_fp, level=logging.DEBUG, format='%(asctime)s | %(levelname)s | %(message)s',
                        filemode='a')
    logging.info('{0} Control-F   SIFT   v.{1} {0}'.format('{}'.format('#'*20), __version__))
    logging.info('Program start')
    logging.debug('System: {}'.format(sys.platform))
    logging.debug('Version: {}'.format(sys.version))
    logging.debug('Host: {}'.format(platform.node()))
    logging.info('SIFT Temp directory: {}'.format(pj(app_data_dir, 'CF_SIFT', 'temp')))


def open_log():
    if not isfile(log_file_fp):
        open(log_file_fp, 'a').close()
    wb.open(log_file_fp)


def refresh_temp_dir():
    now = int(time.time())
    # Creates our temporary directory for storing working copies of files.
    # Uses the current unix time to create the dir
    # Important to check it exists. If it does we need to remove it and recreate it.
    temp_out = pj(app_data_dir, 'CF_SIFT', 'temp')
    if os.path.exists(temp_out):
        try:
            # Clear the temporary directory if possible.
            # The program when installed in C:/ will have permission to clear the temp directory,
            # lone execution will not.
            shutil.rmtree(temp_out)
            os.makedirs(pj(temp_out, '{}'.format(now)), exist_ok=True)
        except Exception as e:
            logging.error(e)
            logging.info('Unable to clear the Temp Directory: {}. '
                         'Please do this manually.'.format(temp_out))
    else:
        os.makedirs(pj(temp_out, '{}'.format(now)), exist_ok=True)

    return pj(temp_out, '{}'.format(now))


def clean_path(path):
    path = path.replace('\\', '/')
    path = path.replace('\\\\', '/')
    return path


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
    try:
        if hxd:
            # The bplist was dumped as hex in string format. We can convert the hex
            # and read it as a stream, saving the need to write the bplist out to a file
            converted = BytesIO(codecs.decode(data[2:-1], 'hex'))
            plist = ccl_bplist.load(converted)
        else:
            # using a buffered stream so we can work on them only in memory.
            plist_dict = plistlib.load(BytesIO(data))  # convert our bplist as bytes to a dictionary object
            plist = ccl_bplist.load(BytesIO(plist_dict))  # buffer the dictionary so we can deserialise the keys

        obj_nk = ccl_bplist.deserialise_NsKeyedArchiver(plist, parse_whole_structure=True)
        return obj_nk
    except:
        return False


class VerifyArchiveThread(QThread):
    finishedSignal = pyqtSignal(list)
    progressSignal = pyqtSignal(str)

    def __init__(self, parent, archive, paths, oem):
        QThread.__init__(self, parent)
        self.archive = archive
        self.paths = paths
        self.oem = oem
        self.errors = []

    def run(self):
        if zipfile.is_zipfile(self.archive):
            self.progressSignal.emit('Zip archive confirmed, verifying contents...')
            try:
                with zipfile.ZipFile(self.archive, 'r') as zip_obj:
                    archive_members = zip_obj.namelist()
                    for path in self.paths:
                        if any(path in archive_member for archive_member in archive_members):
                            pass
                        else:
                            self.errors.append('[!] Missing: {}'.format(path))
            except Exception as e:
                logging.error(e)
                self.errors.append('Unable to read zip archive, refer to file>log.')

        elif tarfile.is_tarfile(self.archive):
            self.progressSignal.emit('Tar archive confirmed, verifying contents...')
            try:
                with tarfile.open(self.archive, 'r') as tar_obj:
                    archive_members = tar_obj.getnames()
                    for path in self.paths:
                        if any(path in archive_member for archive_member in archive_members):
                            pass
                        else:
                            self.errors.append('[!] Missing: {}'.format(path))
            except Exception as e:
                logging.error(e)
                self.errors.append('Unable to read tar archive, refer to file>log.')

        else:
            self.errors.append('[!] ERROR\n\nUnrecognised file format\nInput must be a zip or tar archive')

        if self.errors:
            self.errors.append('\nThe file structure of the archive is important. If you are outputting files '
                               'and folders from a vendor, they should be nested to match the file paths listed.')
        
        self.finishedSignal.emit([self.errors, self.oem, self.archive])


class ExtractArchiveThread(QThread):
    finishedSignal = pyqtSignal(str)
    progressSignal = pyqtSignal(str)

    def __init__(self, parent, files_to_extract, save_dir, archive, maintain_dir_structure=False, key_dir=None):
        QThread.__init__(self, parent)
        self.files_to_extract = files_to_extract
        self.save_dir = save_dir
        self.archive = archive
        self.maintain_dir_structure = maintain_dir_structure
        self.key_dir = key_dir

    def run(self):
        os.makedirs(self.save_dir, exist_ok=True)
        if zipfile.is_zipfile(self.archive):
            self.progressSignal.emit('Archive is zipfile, processing members...')
            with zipfile.ZipFile(self.archive, 'r') as zip_obj:
                archive_members = zip_obj.namelist()
                if not self.maintain_dir_structure:
                    for file_member in self.files_to_extract:  # get the index of the file in the archive members
                        file_idxs = [i for i, archive_member in enumerate(archive_members)
                                     if file_member in archive_member]
                        if file_idxs:
                            self.progressSignal.emit('Found {} to extract from the archive. '
                                                     'Extracting...'.format(len(file_idxs)))
                            for idx in file_idxs:
                                if len(basename(archive_members[idx])) != 0:
                                    file = pj(self.save_dir, '{}'.format(basename(archive_members[idx])))
                                    with open(file, 'wb') as file_out:
                                        zip_fmem = zip_obj.read(archive_members[idx])
                                        file_out.write(zip_fmem)
                else:
                    self.progressSignal.emit('Extracting files with base dir: {}/'.format(self.key_dir))
                    for archive_member in archive_members:
                        if self.key_dir in archive_member:
                            if archive_member.endswith('/'):
                                os.makedirs(self.save_dir+'/'+archive_member, exist_ok=True)
                            else:
                                file = self.save_dir+'/{}'.format(archive_member)
                                with open(file, 'wb') as file_out:
                                    zip_fmem = zip_obj.read(archive_member)
                                    file_out.write(zip_fmem)

        else:
            self.progressSignal.emit('Archive is tarfile, processing members...')
            if not self.maintain_dir_structure:
                with tarfile.open(self.archive, 'r') as tar_obj:
                    archive_members = tar_obj.getnames()
                    for file_member in self.files_to_extract:  # get the index of the file in the archive members
                        file_idxs = [i for i, archive_member in enumerate(archive_members)
                                     if file_member in archive_member]
                        if file_idxs:
                            self.progressSignal.emit('Found {} to extract from the archive. '
                                                     'Extracting...'.format(len(file_idxs)))
                            for idx in file_idxs:
                                if len(basename(archive_members[idx])) != 0:
                                    file = pj(self.save_dir, '{}'.format(basename(archive_members[idx])))
                                    with open(file, 'wb') as file_out:
                                        tar_fmem = tar_obj.extractfile(archive_members[idx])
                                        file_out.write(tar_fmem.read())

            else:
                self.progressSignal.emit('Extracting files with base dir: {}/'.format(self.key_dir))
                with tarfile.open(self.archive, 'r') as tar_obj:
                    for member in tar_obj:
                        if self.key_dir in member.name:
                            if member.isdir():
                                os.makedirs(self.save_dir+'/'+member.name.replace(':', ''), exist_ok=True)
                            else:
                                file = self.save_dir+'/{}'.format(member.name.replace(':', ''))
                                with open(file, 'wb') as file_out:
                                    tar_fmem = tar_obj.extractfile(member)
                                    file_out.write(tar_fmem.read())

        self.finishedSignal.emit('Archive processed!')


class GUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Sift')
        self.setWindowIcon(QIcon(resource_path('controlF.ico')))
        self.setFixedSize(600, 255)
        window_widget = QWidget(self)
        self.setCentralWidget(window_widget)
        self.message_count = 0
        init_log()
        self._create_menu()

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.addWidget(self.main_panel(), 0, 0, 1, 1)
        window_widget.setLayout(grid)

    def _get_dir_dialog(self, oem):
        self.select_datadir_btn.hide()
        self.output_display.clear()

        for btn in [self.select_huawei_btn, self.select_samsung_btn, self.select_sony_btn, 
                    self.select_ios_photos_btn, self.select_ios_snapshots_btn]:
            btn.hide()

        tkinter.Tk().withdraw()  # PYQT5 dialog freezes when selecting large zips; tkinter does not
        archive = askopenfilename(title=oem, initialdir=os.getcwd())
        if archive:
            if oem.startswith('Sony'):
                required = [clean_path(pj('com.sonyericsson.album', 'cache')),
                            clean_path(pj('com.sonyericsson.album', 'databases', 'picnic')),
                            clean_path(pj('databases', 'external.db'))]
            elif oem.startswith('Samsung'):
                required = [clean_path(pj('com.sec.android.app.myfiles', 'cache')),
                            clean_path(pj('com.sec.android.app.myfiles', 'databases', 'FileCache.db')),
                            clean_path(pj('com.android.providers.media', 'databases', 'external.db'))]
            elif oem.startswith('Huawei'):
                required = [clean_path(pj('com.android.gallery3d', 'databases')),
                            clean_path(pj('com.android.gallery3d', 'cache', 'imgcache.0'))]
            elif oem.startswith('iOS Photos'):
                required = [clean_path(pj('PhotoData', 'Photos.sqlite')),
                            clean_path(pj('PhotoData', 'Thumbnails', 'V2'))]
            else:  # iOS snapshots
                required = [clean_path(pj('FrontBoard', 'applicationState.db'))]

            self._init_archive_verification(archive, required, oem)

        else:
            self.reset_widgets()

    def _progress_verification(self, txt):
        self.status_lbl.setText('{}'.format(txt))

    def _finished_verification(self, verification_status):
        errors, oem, archive = verification_status
        if not errors:
            self.status_lbl.setText('Verified successfully. Analysing files...')

            # Get the save directory
            dialog = QFileDialog(self, 'Report Save Location', start_dir)
            dialog.setFileMode(QFileDialog.DirectoryOnly)
            if dialog.exec_() == QDialog.Accepted:
                report_dir = dialog.selectedFiles()[0]
            else:
                report_dir = abspath(archive)
            logging.info('Report saved to: {}'.format(report_dir))

            # Create a fresh temp directory
            temp_out = refresh_temp_dir()

            logging.info('User selected: {}'.format(oem))
            logging.info('User selected report output directory: {}'.format(report_dir))
            if oem.startswith('Sony'):
                MakeSonyReport(self, archive, report_dir, temp_out)
            elif oem.startswith('Samsung'):
                MakeSamsungReport(self, archive, report_dir, temp_out)
            elif oem.startswith('Huawei'):
                MakeHuaweiReport(self, archive, report_dir, temp_out)
            elif oem.startswith('iOS Photos'):
                MakeAppleReport(self, archive, report_dir, temp_out)
            else:  # iOS Snapshots
                MakeSnapShotReport(self, archive, report_dir)
        else:
            self.reset_widgets()
            for err in errors:
                logging.error(err)
                self.output_display.insertPlainText('{}\n'.format(err))

    def _init_archive_verification(self, archive, required, oem):
        self._verify_archive_thread = VerifyArchiveThread(self, archive, required, oem)
        self._verify_archive_thread.progressSignal.connect(self._progress_verification)
        self._verify_archive_thread.finishedSignal.connect(self._finished_verification)
        self._verify_archive_thread.start()

    def _show_instructions(self, oem):
        try:
            self.select_datadir_btn.clicked.disconnect()
        except:
            pass
        self.output_display.clear()
        if oem.startswith('Sony'):
            self.output_display.insertPlainText('Sony Cache Parser\n\nRequirements:\nAndroid 9+\nFull File System '
                                                '(.zip archive)\n\nDirectories/Files:'
                                                '\n/data/data/com.sonyericsson.album'
                                                '\n/data/media\n/databases/external.db')
        elif oem.startswith('Samsung'):
            self.output_display.insertPlainText('Samsung Cache Parser\n\nRequirements:\nAndroid 7+\n'
                                                'Full File System (.zip archive)\n\nDirectories/Files:'
                                                '\n/data/data/com.sec.android.app.myfiles\n''/data/media')
        elif oem.startswith('Huawei'):
            self.output_display.insertPlainText('Huawei Cache Parser\n\nRequirements:\nEMUI8+'
                                                '\nFull File System (.zip archive)\n\nDirectories/Files:'
                                                '\n/media/0/Android/data/com.android.gallery3d/cache'
                                                '\n/data/data/com.android.gallery3d/databases')
        elif oem.startswith('iOS Photos'):
            self.output_display.insertPlainText("Apple Photos\n\nRequirements:\niOS 12+\nFull File System "
                                                "(zip/tar archive)\n\nRequired directory: "
                                                "\n/private/var/mobile/Media/PhotoData\n\nSift will ingest the "
                                                "entire file system or you can provide just the PhotoData folder. "
                                                "Sift will only accept zip/tar archives.")
        elif oem.startswith('iOS Snapshots'):
            self.output_display.insertPlainText('Apple Snapshots\n\nRequirements:\niOS 10+\nFull File System '
                                                '(.zip archive)\n\nDirectories/Files:'
                                                '\n/private/var/mobile/Library/FrontBoard/applicationState.db')

        self.select_datadir_btn.clicked.connect(lambda: self._get_dir_dialog(oem))
        self.select_datadir_btn.show()

    def _create_menu(self):
        self.filemenu = self.menuBar().addMenu("&File")
        self.filemenu.addAction('&Logs', lambda: open_log())

        self.aboutmenu = self.menuBar().addMenu("&About")
        self.aboutmenu.addAction('&Info', lambda: AboutSift().exec_())

        self.helpmenu = self.menuBar().addMenu("&Help")
        self.helpmenu.addAction('&Key', lambda: HelpDialog().exec_())

    def main_panel(self):
        groupbox = QGroupBox()
        groupbox.setFont(QFont("Arial", weight=QFont.Bold))
        self.main_layout = QGridLayout()
        self.main_layout.setContentsMargins(2, 2, 2, 2)

        control_f_emblem = QLabel()
        emblem_pixmap = QPixmap(resource_path('ControlF_R_RGB.png')).scaled(200, 200,
                                                                            Qt.KeepAspectRatio, 
                                                                            Qt.SmoothTransformation)
        control_f_emblem.setPixmap(emblem_pixmap)

        self.output_display = QPlainTextEdit()
        self.output_display.setFixedHeight(180)
        self.output_display.setReadOnly(True)
        self.output_display.setStyleSheet('border: 0;')

        self.select_sony_btn = QPushButton('Sony', self)
        self.select_sony_btn.clicked.connect(lambda: self._show_instructions('Sony - Please select the File '
                                                                             'System zip archive'))

        self.select_samsung_btn = QPushButton('Samsung')
        self.select_samsung_btn.clicked.connect(lambda: self._show_instructions('Samsung - Please select the '
                                                                                'File System zip archive'))

        self.select_huawei_btn = QPushButton('Huawei')
        self.select_huawei_btn.clicked.connect(lambda: self._show_instructions('Huawei - Please select the '
                                                                               'File System zip archive'))

        self.select_ios_photos_btn = QPushButton('iOS Photos')
        self.select_ios_photos_btn.clicked.connect(lambda: self._show_instructions('iOS Photos - Please select '
                                                                                   'the zip/tar archive'))

        self.select_ios_snapshots_btn = QPushButton('iOS Snapshots')
        self.select_ios_snapshots_btn.clicked.connect(lambda: self._show_instructions('iOS Snapshots - Please select '
                                                                                      'the File System zip archive'))

        select_folder = resource_path('folder_y.png')
        self.select_datadir_btn = QPushButton()
        self.select_datadir_btn.setIcon(QIcon(select_folder))
        self.select_datadir_btn.hide()

        self.status_lbl = QLabel()

        self.finished_btn = QPushButton('OK')
        self.finished_btn.clicked.connect(lambda: self.reset_widgets())
        self.finished_btn.hide()

        self.progress_bar = QProgressBar()
        self.progress_bar.hide()

        self.main_layout.addWidget(control_f_emblem,				    0, 1, 2, 7, alignment=Qt.AlignRight)
        self.main_layout.addWidget(self.output_display, 				2, 1, 3, 7)
        self.main_layout.addWidget(self.select_sony_btn, 				2, 0, 1, 1, alignment=Qt.AlignTop)
        self.main_layout.addWidget(self.select_samsung_btn, 			3, 0, 1, 1, alignment=Qt.AlignTop)
        self.main_layout.addWidget(self.select_huawei_btn, 				4, 0, 1, 1, alignment=Qt.AlignTop)
        self.main_layout.addWidget(self.select_ios_photos_btn, 			5, 0, 1, 1, alignment=Qt.AlignTop)
        self.main_layout.addWidget(self.select_ios_snapshots_btn, 		6, 0, 1, 1, alignment=Qt.AlignTop)
        self.main_layout.addWidget(self.select_datadir_btn, 			9, 7, 1, 1, alignment=Qt.AlignRight)
        self.main_layout.addWidget(self.status_lbl, 					9, 0, 1, 6, alignment=Qt.AlignLeft)
        self.main_layout.addWidget(self.finished_btn, 					9, 7, 1, 1, alignment=Qt.AlignRight)
        self.main_layout.addWidget(self.progress_bar, 					11, 0, 2, 8)

        groupbox.setLayout(self.main_layout)
        return groupbox

    def reset_widgets(self):
        self.output_display.clear()
        for btn in [self.select_huawei_btn, self.select_samsung_btn, self.select_sony_btn, 
                    self.select_ios_photos_btn, self.select_ios_snapshots_btn]:
            btn.show()
        self.status_lbl.setText('')
        self.progress_bar.setValue(0)
        self.select_datadir_btn.hide()
        self.progress_bar.hide()
        self.finished_btn.hide()


class MakeAppleReport(QWidget):
    def __init__(self, maingui, archive, report_dir, temp_out):
        super(MakeAppleReport, self).__init__(parent=maingui)
        self.maingui = maingui
        self.archive = archive
        self.main_table_name = ''
        self.save_dir = temp_out
        self.report_dir = report_dir
        self._init_archive_extraction(self.save_dir, archive)

    def _progress_archive_extraction(self, txt):
        self.maingui.status_lbl.setText('{}'.format(txt))

    def _finished_archive_extraction(self, txt):
        self.maingui.status_lbl.setText('{}'.format(txt))
        try:
            self.photossqlitedb = [pj(dirpath, filename) for dirpath, _, filenames in os.walk(self.save_dir)
                                   for filename in filenames if filename == 'Photos.sqlite'][0]
            try:
                self.storeclouddb = [pj(dirpath, filename) for dirpath, _, filenames in os.walk(self.save_dir)
                                     for filename in filenames if filename == 'store.cloudphotodb'][0]
            except IndexError as err:
                logging.info(err)
                self.storeclouddb = None

            photodata_dir = dirname(abspath(self.photossqlitedb))
            photos_df = self.build_photos_dataframe()
            cloudstore_df = self.build_cloud_store_dataframe()
            thumbnail_fn = self.parse_thumb_config(photodata_dir)
            self.row_count = len(photos_df.Filename)
            self._init_thread(photos_df, self.archive, thumbnail_fn, photodata_dir, cloudstore_df)
        except Exception as err:
            self.maingui.reset_widgets()
            logging.error(err)
            self.maingui.output_display.insertPlainText('Error - Could not parse the Photos.sqlite.\n\nRefer to logs.')

    def _init_archive_extraction(self, save_dir, archive):
        self._extract_archive_thread = ExtractArchiveThread(self, 
                                                            [clean_path(pj('Thumbnails', 'V2'))], 
                                                            save_dir, 
                                                            archive, 
                                                            maintain_dir_structure=True, 
                                                            key_dir='PhotoData')
        self._extract_archive_thread.progressSignal.connect(self._progress_archive_extraction)
        self._extract_archive_thread.finishedSignal.connect(self._finished_archive_extraction)
        self._extract_archive_thread.start()

    @staticmethod
    def parse_thumb_config(photodata_dir):  # get the name of the thumbnail e.g. 5005 or 5003
        try:
            with open(pj(photodata_dir, 'Thumbnails', 'thumbnailConfiguration'), 'rb') as thumb_config:
                thumbnail_config_dict = plistlib.load(thumb_config)
            return '{}.jpg'.format(thumbnail_config_dict['PLThumbnailManagerThumbnailFormatKey'])
        except:
            thm = glob.glob(photodata_dir+'/Thumbnails/V2/DCIM/*/*/*.JPG')[0]
            if thm:
                logging.info('The thumbnail basename is: {}'.format(basename(thm)))
                return basename(thm)
            else:
                logging.info('Unknown thumbnail basename! Defaulting to: 5003.jpg')
                return '5003.jpg'

    def build_cloud_store_dataframe(self):
        if self.storeclouddb:
            conn = sqlite3.connect(self.storeclouddb)
            cursor = conn.cursor()
            query = """SELECT identifier, relatedIdentifier, quote(serializedRecord) AS RECORD FROM cloudCache"""
            cloudstore_df = pd.read_sql_query(query, conn)
            cursor.close()
            conn.close()
            return cloudstore_df
        else:
            return None

    def build_photos_dataframe(self):
        with open(resource_path('photos_sqlite_query.txt'), 'r') as psq:
            sql_query = psq.read().strip('\n')

        self.maingui.status_lbl.setText('Parsing photos.sqlite...')
        conn = sqlite3.connect(self.photossqlitedb)
        cursor = conn.cursor()

        # check if iOS 12/13 or iOS 14. iOS 14 uses the table named ZASSET, whilst iOS 12/13 uses ZGENERICASSET
        cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        tables = [i[0] for i in cursor]
        if 'ZGENERICASSET' not in tables:  # iOS 14
            logging.info('Detected Version of iOS >= 14. ZASSET is the main table.')
            sql_query = sql_query.replace('#MAIN_ASSET_TABLE#', 'ZASSET')
            self.main_table_name = 'ZASSET'
        else:  # iOS 12/13
            logging.info('Detected Version of iOS < 14. ZGENERICASSET is the main table.')
            sql_query = sql_query.replace('#MAIN_ASSET_TABLE#', 'ZGENERICASSET')
            self.main_table_name = 'ZGENERICASSET'

        # iOS versions interchange the table ZSHARE and ZMOMENTSHARE. Their cols are the same, just their name changes.
        if 'ZSHARE' not in tables:
            logging.info('ZMOMENTSHARE in use, not ZSHARE')
            sql_query = sql_query.replace('#SHARE_TABLE#', 'ZMOMENTSHARE')
        else:
            logging.info('ZSHARE in use, not ZMOMENTSHARE')
            sql_query = sql_query.replace('#SHARE_TABLE#', 'ZSHARE')

        # check to see if specified tables contain certain columns, otherwise omit them from our SQL query
        cursor.execute("PRAGMA table_info(ZMOMENT)")
        if 'ZSUBTITLE' not in cursor.fetchall():
            sql_query = sql_query.replace('ZMOMENT.ZSUBTITLE AS Moment_Subtitle,', '')

        cursor.execute("PRAGMA table_info(ZMOMENTLIST)")
        if 'ZREVERSELOCATIONDATA' not in cursor.fetchall():
            sql_query = sql_query.replace(',quote(ZMOMENTLIST.ZREVERSELOCATIONDATA) AS Moment_Location', '')

        # Apple alters the digits that prefix the "Z_[1-9][1-9]ASSET" table and its embedded columns
        # We need to find out what these digits are before executing our main query
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name GLOB 'Z_[0-9]ASSETS'")
            asset_table = cursor.fetchone()[0]
            cursor.execute('SELECT * FROM {}'.format(asset_table))
        except:
            cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name GLOB 'Z_[0-9][0-9]ASSETS'")
            asset_table = cursor.fetchone()[0]
            cursor.execute('SELECT * FROM {}'.format(asset_table))

        column_names = [description[0] for description in cursor.description]
        r = re.compile(r"Z_\d{1,2}ASSETS")  # regex for 1 or 2 digits
        asset_column = list(filter(r.match, column_names))[0]
        r = re.compile(r".*ALBUMS")
        album_column = list(filter(r.match, column_names))[0]

        # make our replacements
        sql_query = sql_query.replace('#ASSETS_TABLE#', asset_table)
        sql_query = sql_query.replace('#ASSETS_COLUMN#', asset_column)
        sql_query = sql_query.replace('#ALBUM_COLUMN#', album_column)

        photos_df = pd.read_sql_query(sql_query, conn)
        self.maingui.status_lbl.setText('Successfully converted photos.sqlite to dataframe!')

        # remove any floating NaN values from out dataframe
        for col in ['Play_Count', 'View_Count', 'Share_Count', 'Height', 'Width', 'FileSize']:
            photos_df[col] = photos_df[col].fillna(0).astype('int') 

        cursor.close()
        conn.close()
        return photos_df

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

    def _init_thread(self, photos_df, archive, thumbnail_fn, photodata_dir, cloudstore_df):
        self.maingui.progress_bar.show()
        for btn in [self.maingui.select_datadir_btn, self.maingui.select_sony_btn, self.maingui.select_samsung_btn,
                    self.maingui.select_huawei_btn, self.maingui.select_ios_photos_btn,
                    self.maingui.select_ios_snapshots_btn]:
            btn.hide()
        self.maingui.progress_bar.setMaximum(self.row_count)
        self.maingui.progress_bar.setValue(0)
        self._thread = MakeAppleReportThread(self, photos_df, self.photossqlitedb, archive, thumbnail_fn,
                                             photodata_dir, cloudstore_df, self.report_dir)
        self._thread.progressSignal.connect(self._progress_report)
        self._thread.statusSignal.connect(self._status_report)
        self._thread.finishedSignal.connect(self._finished_report)
        self._thread.start()


class MakeAppleReportThread(QThread):
    finishedSignal = pyqtSignal(str)
    progressSignal = pyqtSignal(int)
    statusSignal = pyqtSignal(str)

    def __init__(self, parent, *args):
        QThread.__init__(self, parent)
        self.photos_df = args[0]
        self.photos_sqlite_db = args[1]
        self.archive = args[2]
        self.thumbnail_fn = args[3]
        self.photodata_dir = args[4]
        self.cloudstore_df = args[5]
        self.report_dir = args[6]

        self.date = '{}_{}'.format(strftime('%d%m%y'), strftime('%H%M%S'))
        self.reports_dir = pj(self.report_dir, 'Apple_Report_{}'.format(self.date))
        os.makedirs(self.reports_dir, exist_ok=True)
        self.excel_report = pj(self.reports_dir, 'photosqlite_{}.xlsx'.format(self.date))

    @staticmethod
    def get_address(hex_string):
        obj_nk = decode_bplist(hex_string, hxd=True)
        try:
            address = ''
            for part in ['_street', '_city', '_postalCode', '_country']:
                address += '{} '.format(obj_nk['root']['postalAddress'][part])
            return address
        except:
            return 'unknown'

    def get_cloud_information(self):
        cloud_user_details = ''

        info_plist = glob.glob(self.photodata_dir+'/PhotoCloudSharingData/*/*/info.plist')
        if info_plist and isfile(info_plist[0]):
            with open(info_plist[0], 'rb') as info_f:
                plist_data = plistlib.load(info_f)

            required = ['cloudOwnerEmail', 'cloudOwnerFirstName', 'cloudOwnerLastName']
            for k, v in plist_data.items():
                if k in required:
                    cloud_user_details += '{}: {}<br /r>'.format(k, v)

        if isfile(pj(self.photodata_dir, 'cpl_enabled_marker')):
            with open(pj(self.photodata_dir,  'cpl_enabled_marker'), 'r') as cpl_enabled_f:
                cloud_user_details += 'Cloud Enabled Timestamp: {}<br /r>'.format(cpl_enabled_f.readline().strip())

        if isfile(pj(self.photodata_dir, 'cpl_download_finished_marker')):
            with open(pj(self.photodata_dir, 'cpl_download_finished_marker'), 'r') as cpl_download_f:
                cloud_user_details += 'Cloud Last Synced: {}<br /r>'.format(cpl_download_f.readline().strip())

        return cloud_user_details

    @staticmethod
    def get_file_metatdata(hex_string):  # from cloud bplist ZCLOUDMASTERMEDIAMETADATA.ZDATA
        info = ''
        try:
            file_metadata_dict = plistlib.loads(codecs.decode(hex_string[2:-1], 'hex'))
            wanted_keys = ['Make', 'Model', 'Software', 'DateTime', 'DateTimeOriginal', 'DateTimeDigitized',
                           'LensModel', 'Latitude', 'Longitude', 'Altitude', 'PixelWidth', 'PixelHeight',
                           'ColorModel', 'name']

            def dictionary_recursor(dic):  # TO DO - convert to lambda function
                for k, v in dic.items():
                    if type(v) is dict:
                        yield from dictionary_recursor(v)
                    else:
                        yield k, v

            for key, value in dictionary_recursor(file_metadata_dict):
                if key in wanted_keys:
                    if key == '2':
                        info += '<strong>{}:</strong> {}<br /r>'.format(key, value)
                    else:
                        info += '<strong>{}:</strong> {}<br /r>'.format(key, value)
        except:
            pass

        return info

    def parse_cloud_owner(self, row):
        cloud_owner = ''
        try:
            if len(self.cloudstore_df) > 0:
                for cloud_row in self.cloudstore_df.itertuples():
                    if cloud_row.relatedIdentifier == row.Master_Fingerprint:
                        d = ccl_bplist.load(BytesIO(codecs.decode(cloud_row.RECORD[2:-1], 'hex')))
                        cloud_owner += '{}'.format(ccl_bplist.load(BytesIO(d['p']['anch']))['p']['ckmd'])
                        break
        except Exception:
            pass
        return cloud_owner

    @staticmethod
    def parse_adjustment_info(row):
        adjustment_info = ''
        if row.Adjusted == 'Yes':
            adjustment_info += '{}'.format(row.Adjusted)
            if row.Adjustment_Package:
                adjustment_info += '<br /r><strong>Adjustment Package:<br /r></strong> {}<br /r>{} ({})<br /r>' \
                                 '<strong>Adjusted Timestamp:</strong> {}'.format(row.Adjustment_Package,
                                                                                  row.Adjustment_Format_ID,
                                                                                  row.Adjustment_Format_Name,
                                                                                  row.Adjusted_Timestamp)
        return adjustment_info

    @staticmethod
    def parse_memories(row):  # not used
        memory_info = ''
        if row.Memory_Title:
            memory_info += '<strong>Memory</strong><br /r>' \
                           '<strong>Title: </strong>{}<br /r>' \
                           '<strong>Created: </strong>{}<br /r>' \
                           '<strong>Last Viewed: </strong>{}<br /r>'.format(row.Memory_Title,
                                                                            row.Memory_Creation_Timestamp,
                                                                            row.Memory_Last_Viewed_Date)
        return memory_info

    def parse_moments(self, row):  # not used
        moments_info = '<strong>Moment</strong><br /r>' \
                       '<strong>Title: </strong>{}<br /r>' \
                        '<strong>Start/End: </strong>{}<strong> - </strong>{}</strong><br /r>' \
                        '<strong>GPS: </strong>{}, {}'.format(row.Moment_Title,
                                                              row.Moment_Start_Date,
                                                              row.Moment_End_Date,
                                                              row.Moment_Latitude,
                                                              row.Moment_Longitude)
        try:
            moments_info += '<br /r><strong>Moment Reverse ' \
                            'Location:</strong> {}<br /r>'.format(self.get_address(row.Moment_Location))
        except:
            moments_info += '<br /r>'

        return moments_info

    @staticmethod
    def parse_album_info(row):
        album_info = ''
        if row.Album_Title:
            album_info += '<strong>Name:</strong> {}<br /r>' \
                         '<strong>Album (Cloud State):</strong> {}'.format(row.Album_Title,
                                                                           row.Album_Local_Cloudstate)
            if row.Invitee_Fullname:
                album_info += '<br /r><strong>Album Shared With: </strong>{}  {}'.format(row.Invitee_Fullname,
                                                                                         row.Invitee_Invited_Date)
            else:
                album_info += '<br /r><br /r><br /r>'
        else:
            album_info += '<br /r><br /r><br /r><br /r>'
        return album_info

    @staticmethod
    def parse_share_details(row):
        share_details = ''
        try:
            if row.Shared_URL:
                share_details += '<strong>URL:</strong> {}<br /r>' \
                                 '<strong>From:</strong> {}<br /r>' \
                                 '<strong>Expires:</strong>{}'.format(row.Shared_URL,
                                                                      row.Shared_From,
                                                                      row.Shared_Ends)
        except:
            share_details += 'None'

    @staticmethod
    def parse_hash(row):
        original_hash = ''
        if row.Original_Hash:
            original_hash += row.Original_Hash

        return original_hash

    def create_html(self, count, total):
        html_reportname = abspath(pj(self.reports_dir, 'Apple_Report_{}.html'.format(count)))
        outfile = open(html_reportname, 'wb')

        s = """<!DOCTYPE html><head><meta http-equiv="content-type" content="text/html;charset=utf-8" /><style>
            p.a {
              font-family: "Segoe UI";
            }
            img {
                object-fit: cover;
                width: 300px;
                height: 100%;
                object-fit: cover;
            }

            .item0 { grid-area: pic; }
            .item1 { grid-area: file_prop_header; }
            .item2 { grid-area: file_prop_labels; }
            .item3 { grid-area: file_prop_values; }
            .item4 { grid-area: additional_prop_header; }
            .item5 { grid-area: additional_prop_labels; }
            .item6 { grid-area: additional_prop_values; }
            .item7 { grid-area: cloud_prop_header; }
            .item8 { grid-area: cloud_prop_labels; }
            .item9 { grid-area: cloud_prop_values; }

            .grid-container {
                display: grid; 
                grid-template-areas:
                    'pic file_prop_header file_prop_header additional_prop_header additional_prop_header 
                    cloud_prop_header cloud_prop_header'
                    'pic file_prop_labels file_prop_values additional_prop_labels additional_prop_values 
                    cloud_prop_labels cloud_prop_values'
                    'pic file_prop_labels file_prop_values additional_prop_labels additional_prop_values 
                    cloud_prop_labels cloud_prop_values';
                grid-gap: 15px;
                padding: 5px;
                font-family: "Segoe UI";
                font-size: 12px;
                text-align: left;
                background-color: white;
                border: 1px solid black;
            }
            </style>
            </head>
            <body>"""
        outfile.write(str.encode(s))
        s = """<p class="a"><span style="font-weight:bold; font-size:30px">Apple Photos Artefact Report {}/{}</span>
        <br /r><span style="font-weight:bold; font-size:12px">Photos.sqlite Database: {}<br />Report Date: {}
        <br /r><br />{}<br /></span></p>""".format(count, total, self.photos_sqlite_db, self.date,
                                                   self.get_cloud_information())
        outfile.write(str.encode(s))
        return outfile

    def run(self):
        self.photos_df.to_excel(self.excel_report)

        self.row_count = len(self.photos_df.Filename)
        self.statusSignal.emit('Generating HTML report ({} entries)...'.format(self.row_count))
        report_split_count = int(self.row_count / 500)

        for count in range(0, report_split_count+1):
            outfile = self.create_html(count, report_split_count)
            row_position = count*500
            for row in self.photos_df.iloc[row_position:row_position+500].itertuples():
                self.progressSignal.emit(1)
                decode_bplist(row.Location_Lookup)
                # lets use the thumbnails to display the image and the videos in the html report. Apple have already
                # converted the HEIF files to JPGs and they are good quality.
                thumbnail_path_absolute = pj(self.photodata_dir, 'Thumbnails',
                                             'V2', dirname(row.Directory), 
                                             basename(row.Directory), 
                                             row.Filename,
                                             self.thumbnail_fn)

                if isfile(thumbnail_path_absolute):
                    thmb_data = open(thumbnail_path_absolute, 'rb').read()
                else:
                    thmb_data = open(resource_path('blank_jpeg.jpg'), 'rb').read()
                thmb_b64 = base64.b64encode(thmb_data)
                # now we can embed the thumbnail in our report so it is portable.
                thmb_b64 = thmb_b64.decode()

                main_body = ("""<div class="grid-container">
                                    <div class="item0">
                                        <img src="data:image/jpeg;base64,{}" alt="img";padding: 0px 10px 10px 0px;">
                                    </div>
    
                                    <div class="item1">
                                        <span style="font-weight:bold; font-size:20px">File Properties</span>
                                    </div>
                                    
                                    <div class="item2">
                                        <strong>Current Filename:</strong><br/r>
                                        <strong>Folder Path:</strong><br/r>
                                        <strong>Original Filename:</strong><br/r><br/r>
                                        <strong>Imported By:</strong><br /r>
                                        <strong>Parent Application:</strong><br/r>
                                        <strong>File Type:</strong><br /r>
                                        <strong>Orientation:</strong><br /r>
                                        <strong>Duration:</strong><br /r>
                                        <strong>Playback Style:</strong><br /r>
                                        <strong>File Size:</strong><br /r>
                                        <strong>Dimensions:</strong><br /r><br /r>
                                        <strong>Thumbnail Index:</strong><br /r>
                                        <strong>Thumbnail Filename:</strong><br /r><br /r>
                                        <strong>Created Timestamp:</strong><br /r>
                                        <strong>Modified Timestamp:</strong><br /r>
                                        <strong>Added Timestamp:</strong><br /r>
                                        <strong>EXIF Timestamp:</strong><br /r><br /r>
                                        <strong>Geo-Coords:</strong><br /r>
                                        <strong>Location Lookup:</strong><br /r>
                                        <strong>Original Hash:</strong>	
                                    </div>
                                    
                                    <div class="item3">
                                        {}<br /r>
                                        {}<br /r>
                                        {}<br /r><br /r>
                                        {}<br /r>
                                        {}<br /r>
                                        {}<br /r>
                                        {}<br /r>
                                        {} seconds<br /r>
                                        {}<br /r>
                                        {}b  [{}]<br /r>
                                        {} x {}<br /r><br /r>
                                        {}<br /r>
                                        {}<br /r><br /r>
                                        {}<br /r>
                                        {}<br /r>
                                        {}<br /r>
                                        {}<br /r><br /r>
                                        {}, {}<br /r>
                                        {}<br /r>
                                        {}
                                    </div>
                                    
                                    <div class="item4">
                                        <span style="font-weight:bold; font-size:20px">Additional Properties</span>
                                    </div>
                                    
                                    <div class="item5">
                                        <strong>Album:</strong><br /r><br /r><br /r><br /r>
                                        <strong>Trash State:</strong><br /r>
                                        <strong>Trashed Date:</strong><br /r><br /r>
                                        <strong>Hidden:</strong><br /r>
                                        <strong>Favourite:</strong><br /r>
                                        <strong>View Count:</strong><br /r>
                                        <strong>Play Count:</strong><br /r><br /r>	
                                        <strong>Adjustment/Mutation:</strong><br /r><br /r><br /r><br /r>		
                                    </div>
                                    
                                    <div class="item6">
                                        {}
                                        {}<br /r>
                                        {}<br /r><br /r>
                                        {}<br /r>
                                        {}<br /r>
                                        {}<br /r>
                                        {}<br /r><br /r>
                                        {}
                                    </div>
                                    
                                    <div class="item7">
                                        <span style="font-weight:bold; font-size:20px">Cloud Properties</span>
                                    </div>
                                    
                                    <div class="item8">
                                        <strong>Cloud State:</strong><br /r>
                                        <strong>Saved Asset Type:</strong><br /r>
                                        <strong>Share Count:</strong><br /r>
                                        <strong>Share Details:</strong><br /r><br /r>
                                        <strong>Cloud Owner:</strong><br /r><br /r><br /r>
                                        <strong>Cloud Fingerprint:</strong><br /r><br /r><br /r>
                                        <strong>Recovered Cloud Metadata</strong><br /r><br /r>
                                    </div>
                                    
                                    <div class="item9">
                                        {}<br /r>
                                        {}<br /r>
                                        {}<br /r>
                                        {}<br /r><br /r>
                                        {}<br /r><br /r><br /r>
                                        {}<br /r><br /r><br /r>
                                        {}
                                    </div>
                                </div>""".format(
                                                thmb_b64,
                                                row.Filename,
                                                row.Directory,
                                                row.Original_Filename,
                                                row.Imported_Via,
                                                row.Application_Package,
                                                row.FileType,
                                                row.Orientation,
                                                int(row.Duration),
                                                row.Play_Back_Style,
                                                row.FileSize, row.FileSize_MB,
                                                int(row.Height), int(row.Width),
                                                row.Thumbnail_Index,
                                                self.thumbnail_fn,
                                                row.Created_Date,
                                                row.Modified_Date,
                                                row.Added_Date,
                                                row.EXIF_Timestamp,
                                                row.Latitude, row.Longitude,
                                                self.get_address(row.Location_Lookup),
                                                self.parse_hash(row),
                                                self.parse_album_info(row),
                                                row.Trashed_State,
                                                row.Trashed_Date,
                                                row.Hidden,
                                                row.Favourited,
                                                str(int(row.View_Count)),
                                                str(int(row.Play_Count)),
                                                self.parse_adjustment_info(row),
                                                row.File_Local_Cloudstate,
                                                row.Saved_Asset_Type,
                                                str(int(row.Share_Count)),
                                                self.parse_share_details(row),
                                                self.parse_cloud_owner(row),
                                                row.Master_Fingerprint,
                                                self.get_file_metatdata(row.Cloud_Media_Metadata)))
                outfile.write(str.encode(main_body))

            end = """<p class="a"></br></br></br></br>{}</p></body></html>""".format(end_of_report_eula)
            outfile.write(str.encode(end))
            outfile.close()

        refresh_temp_dir()
        logging.info('Report successfully generated: {}'.format(self.reports_dir))
        self.finishedSignal.emit(self.reports_dir)


class MakeSonyReport(QWidget):
    def __init__(self, maingui, archive, report_dir, temp_out):
        super(MakeSonyReport, self).__init__(parent=maingui)
        self.maingui = maingui
        self.archive = archive
        self.save_dir = temp_out
        self.report_dir = report_dir
        self.picnic_db = pj(self.save_dir, 'picnic')
        self._init_archive_extraction()

    def _progress_archive_extraction(self, txt):
        self.maingui.status_lbl.setText('{}'.format(txt))

    def _finished_archive_extraction(self, txt):
        self.maingui.status_lbl.setText('{}'.format(txt))
        try:
            self.row_count = get_sqlite_rowcount(self.picnic_db, 'ThumbnailRecord')
            self.maingui.status_lbl.setText('Found {} thumbnail records'.format(self.row_count))
            self._init_thread(self.archive, self.picnic_db, self.save_dir)
        except Exception as err:
            self.maingui.reset_widgets()
            self.maingui.output_display.insertPlainText('Error - Could not parse picnic database.\n\nRefer to logs.')
            logging.error(err)

    def _init_archive_extraction(self):
        self._extract_archive_thread = ExtractArchiveThread(self, 
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
        self.archive = args[0]
        self.picnic_db = args[1]
        self.save_dir = args[2]
        self.report_dir = args[3]

        dt = '{}_{}'.format(strftime('%d%m%y'), strftime('%H%M%S'))
        self.reportname = pj(self.report_dir, 'Sony_Report_{}.html'.format(dt))

    def create_html(self):
        outfile = open(self.reportname, 'wb')
        s = """<!DOCTYPE html><head><style>
            p.a {
              font-family: "Segoe UI";
            }
            .grid-container {
                display: grid; 
                grid-template-columns: 500px auto;
                grid-template-rows: 500px auto;
                background-color: black; 
                padding: 1px;
            }
            .grid-item {
                background-color: rgba(255, 255, 255, 255);
                border: 1px solid rgba(0, 0, 0, 0);
                padding: 25px;
                font-family: "Segoe UI";
                font-size: 12px;
                text-align: left;
            }
            </style>
            </head>
            <body>"""

        outfile.write(str.encode(s))
        s = """<p class="a">
                    <span style="font-weight:bold; font-size:30px">Sony Album Thumbnail Report</span>
                    <br /r><span style=font-weight:bold; font-size:12px">
                    Database: 'picnic'<br />Report Date: {} {}<br /r><br /></span>
                </p>
                <div class="grid-container">""".format(strftime('%d-%m-%y'), strftime('%H:%M:%S'))
        outfile.write(str.encode(s))
        return outfile

    def run(self):
        outfile = self.create_html()
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
        logging.info('Report successfully created: {}'.format(self.reportname))
        self.finishedSignal.emit(self.reportname)


class MakeSamsungReport(QWidget):
    def __init__(self, maingui, archive, report_dir, temp_out):
        super(MakeSamsungReport, self).__init__(parent=maingui)
        self.maingui = maingui
        self.archive = archive
        self.save_dir = temp_out
        self.report_dir = report_dir
        self.filecachedb = pj(self.save_dir, 'FileCache.db')
        self._init_archive_extraction()

    def _progress_archive_extraction(self, txt):
        self.maingui.status_lbl.setText('{}'.format(txt))

    def _finished_archive_extraction(self, txt):
        self.maingui.status_lbl.setText('{}'.format(txt))
        try:
            self.row_count = get_sqlite_rowcount(self.filecachedb, 'FileCache')
            cache_df = self.build_dataframe(self.filecachedb)
            self._init_thread(cache_df, self.filecachedb, self.archive, self.save_dir)
        except Exception as err:
            self.maingui.reset_widgets()
            self.maingui.output_display.insertPlainText('Error - Could not parse the FileCache.db\n\nRefer to logs.')
            logging.error(err)

    def _init_archive_extraction(self):
        self._extract_archive_thread = ExtractArchiveThread(self, 
                                                            [clean_path(pj('com.sec.android.app.myfiles', 'databases',
                                                                           'FileCache.db')), 'external.db',
                                                             clean_path(pj('com.sec.android.app.myfiles', 'cache'))],
                                                            self.save_dir, 
                                                            self.archive)
        self._extract_archive_thread.progressSignal.connect(self._progress_archive_extraction)
        self._extract_archive_thread.finishedSignal.connect(self._finished_archive_extraction)
        self._extract_archive_thread.start()

    @staticmethod
    def build_dataframe(filecachedb):
        fc_conn = sqlite3.connect(filecachedb)
        filecache_df = pd.read_sql_query("SELECT * FROM FileCache", fc_conn, index_col=['_index'])
        fc_conn.close()
        return filecache_df

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
        self.filecache_df = args[0]
        self.filecachedb = args[1]
        self.archive = args[2]
        self.save_dir = args[3]
        self.report_dir = args[4]

        dt = '{}_{}'.format(strftime('%d%m%y'), strftime('%H%M%S'))
        self.reportname = pj(self.report_dir, 'Samsung_Report_{}.html'.format(dt))

    def create_html(self):
        outfile = open(self.reportname, 'wb')
        s = """<!DOCTYPE html><head><style>
            p.a {
              font-family: "Segoe UI";
            }
            .grid-container {
                display: grid; 
                grid-template-columns: 500px auto;
                grid-template-rows: 500px auto;
                background-color: black; 
                padding: 1px;
            }
            .grid-item {
                background-color: rgba(255, 255, 255, 255);
                border: 1px solid rgba(0, 0, 0, 0);
                padding: 25px;
                font-family: "Segoe UI";
                font-size: 12px;
                text-align: left;
            }
            </style>
            </head>
            <body>"""
        outfile.write(str.encode(s))
        s = """<p class="a">
                    <span style="font-weight:bold; font-size:30px">Samsung Media Artefact Report</span><br /r>
                    <span style="font-weight:bold; font-size:12px">
                    Database: 'FileCache.db'<br />Report Date: {} {}<br /r><br />
                    </span>
                </p>
                <div class="grid-container">""".format(strftime('%d-%m-%y'), strftime('%H:%M:%S'))
        outfile.write(str.encode(s))
        return outfile

    def run(self):
        outfile = self.create_html()
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
        logging.info('Report successfully created: {}'.format(self.reportname))
        self.finishedSignal.emit(self.reportname)


class MakeHuaweiReport(QWidget):
    def __init__(self, maingui, archive, report_dir, temp_out):
        super(MakeHuaweiReport, self).__init__(parent=maingui)
        self.archive = archive
        self.maingui = maingui
        self.save_dir = temp_out
        self.report_dir = report_dir
        self.gallery_db = pj(self.save_dir, 'gallery.db')
        self._init_archive_extraction()

    def _progress_archive_extraction(self, txt):
        self.maingui.status_lbl.setText('{}'.format(txt))

    def _finished_archive_extraction(self, txt):
        self.maingui.status_lbl.setText('{}'.format(txt))
        try:
            gallery_df = self.build_dataframe(self.gallery_db)
            self._init_thread(self.archive, gallery_df, self.gallery_db, self.save_dir)
        except Exception as err:
            self.maingui.reset_widgets()
            self.maingui.output_display.insertPlainText('Error - Could not parse the gallery.db.\n\nRefer to logs')
            logging.error(err)

    def _init_archive_extraction(self):
        self._extract_archive_thread = ExtractArchiveThread(self,
                                                            [clean_path(pj('com.android.gallery3d', 'databases',
                                                                           'gallery.db')),
                                                             clean_path(pj('Android', 'data', 'com.android.gallery3d',
                                                                           'cache'))],
                                                            self.save_dir, 
                                                            self.archive)
        self._extract_archive_thread.progressSignal.connect(self._progress_archive_extraction)
        self._extract_archive_thread.finishedSignal.connect(self._finished_archive_extraction)
        self._extract_archive_thread.start()

    @staticmethod
    def build_dataframe(gallery_db):
        fc_conn = sqlite3.connect(gallery_db)
        gallery_df = pd.read_sql_query("SELECT * FROM gallery_media", fc_conn)
        fc_conn.close()
        return gallery_df

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
        self.archive = args[0]
        self.gallery_df = args[1]
        self.gallery_db = args[2]
        self.save_dir = args[3]
        self.report_dir = args[4]
        self.cachefile = pj(self.save_dir, 'imgcache.0')

        dt = '{}_{}'.format(strftime('%d%m%y'), strftime('%H%M%S'))
        self.reportname = pj(self.report_dir, 'Huawei_Report_{}.html'.format(dt))

    def find_jpeg(self):
        cachefile = open(self.cachefile, 'rb')
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

    def create_html(self):
        outfile = open(self.reportname, 'wb')
        s = """<!DOCTYPE html><head><style>
            p.a {
              font-family: "Segoe UI";
            }
            .grid-container {
                display: grid; 
                grid-template-columns: 500px auto;
                grid-template-rows: 500px auto;
                background-color: black; 
                padding: 1px;
            }
            .grid-item {
                background-color: rgba(255, 255, 255, 255);
                border: 1px solid rgba(0, 0, 0, 0);
                padding: 25px;
                font-family: "Segoe UI";
                font-size: 12px;
                text-align: left;
            }
            </style>
            </head>
            <body>"""
        outfile.write(str.encode(s))
        s = """<p class="a">
                    <span style="font-weight:bold; font-size:30px">Huawei Media Cache Artefact Report</span><br /r>
                    <span style="font-weight:bold; font-size:12px">
                    Cache File: 'imgcache.0'<br />Report Date: {} {}<br /r><br /></span>
                </p>
                <div class="grid-container">""".format(strftime('%d-%m-%y'), strftime('%H:%M:%S'))
        outfile.write(str.encode(s))
        return outfile

    def run(self):
        outfile = self.create_html()
        generated = self.find_jpeg()  # generator object for parsing our cache file
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
        logging.info('Report successfully created: {}'.format(self.reportname))
        self.finishedSignal.emit(self.reportname)


class MakeSnapShotReport(QWidget):
    def __init__(self, maingui, archive, report_dir):
        super(MakeSnapShotReport, self).__init__(parent=maingui)
        self.maingui = maingui
        self.archive = archive
        # Store the KTX snapshots as JPG files in the following location
        self.save_dir = pj(report_dir, 'snapshots')
        self.application_state_db = pj(self.save_dir, 'applicationState.db')
        self._init_archive_extraction()

    def _progress_archive_extraction(self, txt):
        self.maingui.status_lbl.setText('{}'.format(txt))

    def _finished_archive_extraction(self, txt):
        self.maingui.status_lbl.setText('{}'.format(txt))
        try:
            snapshot_rows = self.build_snapshot_dict(self.application_state_db)
            self.row_count = len(snapshot_rows)
            self._init_thread(self.archive, self.application_state_db, snapshot_rows, self.save_dir)
        except Exception as err:
            self.maingui.reset_widgets()
            self.maingui.output_display.insertPlainText('Error - Could not parse the applicationState.db.\n\n'
                                                        'Refer to logs.')
            logging.error(err)

    def _init_archive_extraction(self):
        self._extract_archive_thread = ExtractArchiveThread(self, 
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
        self.archive = args[0]
        self.application_state_db = args[1]
        self.snapshot_rows = args[2]
        self.save_dir = args[3]

        self.date = '{}_{}'.format(strftime('%d%m%y'), strftime('%H%M%S'))
        self.reportname = pj(dirname(self.save_dir), 'iOS_Snapshot_Report_{}.html'.format(self.date))

    def run(self):
        html_report = self.create_html()
        self.statusSignal.emit('Parsing binary plists...')
        all_snapshots_dict = self.get_metadata(self.snapshot_rows)
        self.statusSignal.emit('{} KTX files found. Some files may not be recoverable. '
                               'Initiating...'.format(len(all_snapshots_dict.keys())))

        count = 0
        with zipfile.ZipFile(self.archive, 'r') as zip_obj:
            filepaths = zip_obj.namelist()
            for fn in filepaths:
                if fn.endswith('.ktx'):
                    ktx_file = pj(self.save_dir, '{}'.format(basename(fn)))
                    ktx_png = pj(self.save_dir, '{}.png'.format(basename(fn)))
                    with open(ktx_file, 'wb') as ktx_out:
                        f = zip_obj.read(fn)
                        ktx_out.write(f)

                    with open(ktx_file, 'rb') as f:
                        ktx = KTXReader()
                        try:
                            ktx.convert_to_png(f, ktx_png)
                        except Exception as err:
                            logging.error('{} - {}'.format(basename(ktx_file), err))
                            pass
                    os.remove(ktx_file)

                    snapshot_fn = basename(ktx_png)[:36]
                    snapshot_path_relative = 'snapshots/{}'.format(basename(ktx_png))

                    if isfile(pj(self.save_dir, basename(ktx_png))):
                        self.statusSignal.emit('Decompressing: {}...'.format(basename(ktx_png)))
                        if snapshot_fn in all_snapshots_dict:
                            metadata = all_snapshots_dict.get(snapshot_fn)

                            metadata_prettified = ''
                            for k, v in metadata.items():
                                if k in ['creationDate', 'lastUsedDate', 'expirationDate']:
                                    metadata_prettified += '<strong>{}:</strong> ' \
                                                           '{}<br /r>'.format(k,
                                                                              datetime.fromtimestamp(int(float(v)))
                                                                              + delta)
                                else:
                                    metadata_prettified += '<strong>{}:</strong> {}<br /r>'.format(k, v)

                                float_img = ("""<div class="grid-item">
                                                    <img src="{}" alt="img" padding: 0px 10px 10px 0px width='200';
                                                    height='280':">
                                                </div>
                                                <div class="grid-item">
                                                    <span style="font-weight:bold; font-family: "Segoe UI"; 
                                                    font-size:16px">Snapshot Properties</span><br /r><br /r>
                                                    <strong>Snapshot Filename:</strong> {}<br /r><br /r>
                                                    <strong>Metadata</strong><br /r>{}		
                                                </div>""".format(snapshot_path_relative,
                                                                 basename(ktx_png),
                                                                 metadata_prettified))

                                html_report.write(str.encode(float_img))

                        else:
                            float_img = ("""<div class="grid-item">
                                                <img src="{}" alt="img" padding: 0px 10px 10px 0px width='200';
                                                height='280':">
                                            </div>
                                            <div class="grid-item">
                                                <span style="font-weight:bold; font-family: "Segoe UI"; font-size:16px">
                                                Snapshot Properties</span><br /r><br /r>
                                                <strong>Snapshot Filename:</strong> {}<br /r><br /r>
                                                <strong>Metadata</strong><br /r>None		
                                            </div>""".format(snapshot_path_relative,
                                                             basename(ktx_png)))

                            html_report.write(str.encode(float_img))

                        self.progressSignal.emit(count)
                        count += 1

        end = """</div></body></html>"""
        html_report.write(str.encode(end))
        html_report.close()
        logging.info('Report successfully created: {}'.format(self.reportname))
        self.finishedSignal.emit(self.reportname)

    def create_html(self):
        outfile = open(self.reportname, 'wb')
        s = """<!DOCTYPE html><head><style>
            p.a {
              font-family: "Segoe UI";
            }
            .grid-container {
                display: grid; 
                grid-template-columns: 500px auto;
                grid-template-rows: 500px auto;
                background-color: black; 
                padding: 1px;
            }
            .grid-item {
                background-color: rgba(255, 255, 255, 255);
                border: 1px solid rgba(0, 0, 0, 0);
                padding: 25px;
                font-family: "Segoe UI";
                font-size: 12px;
                text-align: left;
            }
            </style>
            </head>
            <body>"""
        outfile.write(str.encode(s))
        s = """<p class="a">
                    <span style="font-weight:bold; font-size:30px">Apple Carousel Snapshot Report</span><br /r>
                    <strong>Report Date: {}</strong><br /r><br />
                </p>
                <div class="grid-container">""".format(self.date)
        outfile.write(str.encode(s))
        return outfile

    @staticmethod
    def get_metadata(snapshot_rows):
        # parse the applicationState.db and produce a dictionary for use to match the converted snapshots with
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
                            if k == 'creationDate':
                                try:
                                    metadata[k] = '{}'.format(obj_nk['root']['snapshots']['NS.objects'][count]
                                                              ['snapshots']['NS.objects'][count][k]['NS.time'])
                                except:
                                    pass
                            if k == 'expirationDate':
                                try:
                                    metadata[k] = '{}'.format(obj_nk['root']['snapshots']['NS.objects'][count]
                                                              ['snapshots']['NS.objects'][count][k]['NS.time'])
                                except:
                                    pass
                            if k == 'lastUsedDate':
                                try:
                                    metadata[k] = '{}'.format(obj_nk['root']['snapshots']['NS.objects'][count]
                                                              ['snapshots']['NS.objects'][count][k]['NS.time'])
                                except:
                                    pass
                            if k == 'identifier':
                                identifier = v

                            all_snapshots_dict['{}'.format(identifier)] = metadata

        return all_snapshots_dict


class KTXReader:
    # Yogesh Khatri KTX > PNG (Some modifications made)
    def __init__(self):
        # KTX header fields
        self.identifier = b''  # b"«KTX 11»\r\n\x1A\x0A"
        self.endianness = ''
        self.glType = 0
        self.glTypeSize = 0
        self.glFormat = 0
        self.glInternalFormat = 0
        self.glBaseInternalFormat = 0
        self.pixelWidth = 0
        self.pixelHeight = 0
        self.pixelDepth = 0
        self.numberOfArrayElements = 0
        self.numberOfFaces = 0
        self.numberOfMipmapLevels = 0
        self.bytesOfKeyValueData = 0
        self.is_aapl_file = False
        self.aapl_data_pos = 0
        self.aapl_data_size = 0
        self.aapl_is_compressed = False

    def validate_header(self, f):
        f.seek(0)
        header = f.read(0x40)
        if len(header) < 0x40:
            logging.error("{} - File too small or can't read".format(f))
            return False

        self.identifier = header[0:12]
        self.endianness = header[12:16]
        if self.endianness == bytes.fromhex('01020304'):
            endianness = '<'
        else:
            endianness = '>'
        if self.identifier[0:7] == b'\xabKTX 11':
            self.glType,\
            self.glTypeSize, \
            self.glFormat, \
            self.glInternalFormat, \
            self.glBaseInternalFormat, \
            self.pixelWidth, \
            self.pixelHeight, \
            self.pixelDepth, \
            self.numberOfArrayElements, \
            self.numberOfFaces, \
            self.numberOfMipmapLevels, \
            self.bytesOfKeyValueData = \
                struct.unpack(endianness + '12I', header[16:64])
            return True
        elif self.identifier[0:4] == b'\xabKTX':  # different version
            logging.error("{} - Unknown KTX version".format(f))
        elif self.identifier[0:8] == b'AAPL\x0D\x0A\x1A\x0A':  # Not KTX, but similar!!
            self.is_aapl_file = True
            return self.parse_aapl_file(f)
        else:
            logging.error("{} - Not a KTX file".format(f))
        return False

    def parse_aapl_file(self, f):
        ret = False
        next_header_pos = 8
        f.seek(next_header_pos)
        data = f.read(8)
        while data:
            item_size = struct.unpack('<I', data[0:4])[0]
            item_identifier = data[4:8]
            if item_identifier == b'HEAD':
                item_data = f.read(item_size)
                # read metadata here...
                _, _, _, _, \
                self.glInternalFormat, \
                self.glBaseInternalFormat, \
                self.pixelWidth, \
                self.pixelHeight, \
                self.pixelDepth, \
                self.numberOfArrayElements, \
                self.numberOfFaces = \
                    struct.unpack('<11I', item_data[0:44])
                ret = True
            elif item_identifier == b'LZFS':
                self.aapl_data_pos = f.tell() + 4
                self.aapl_data_size = item_size - 4
                self.aapl_is_compressed = True
            elif item_identifier == b'astc':
                self.aapl_data_pos = f.tell() + 4
                self.aapl_data_size = item_size - 4
            next_header_pos += 8 + item_size
            f.seek(next_header_pos)
            data = f.read(8)
        return ret

    def get_uncompressed_texture_data(self, f):
        if self.glInternalFormat == 0x93B0:
            if self.is_aapl_file:
                f.seek(self.aapl_data_pos)
                data = f.read(self.aapl_data_size)
                if self.aapl_is_compressed:
                    decompressed = liblzfse.decompress(data)
                    return decompressed
                else:
                    return data
            else:
                f.seek(0x40)
                k_v_data = f.read(self.bytesOfKeyValueData)
                compressed = True if k_v_data.find(b'Compression_APPLE') >= 0 else False
                f.seek(0x40 + self.bytesOfKeyValueData)
                data = f.read()
                if compressed:
                    if data[12:15] == b'bvx':
                        decompressed = liblzfse.decompress(data[12:])
                        return decompressed
                    else:
                        raise ValueError('Unsupported compression, not lzfse!')
                else:
                    return data[4:]  # first 4 bytes is size (which is practically rest of file)
        else:
            raise ValueError('Unsupported Format')

    def convert_to_png(self, f, save_to_path):
        if self.validate_header(f):
            data = self.get_uncompressed_texture_data(f)
            dec_img = Image.frombytes('RGBA', (self.pixelWidth, self.pixelHeight), data, 'astc', (4, 4, False))
            dec_img.save(save_to_path, "PNG")
            return True
        return False

    def save_uncompressed_texture(self, f, save_to_path):
        if self.validate_header(f):
            data = self.get_uncompressed_texture_data(f)
            f = open(save_to_path, 'wb')
            f.write(data)
            f.close()
            return True
        return False


class HelpDialog(QDialog):
    def __init__(self):
        super(HelpDialog, self).__init__()
        self.setFixedSize(1900, 620)
        buttonbox = QDialogButtonBox(QDialogButtonBox.Cancel)
        buttonbox.rejected.connect(self.reject)

        cloudmastermediametadata = 'Photos.sqlite\nZCLOUDMASTERMEDIAMETADATA.ZDATA\nMedia metadata attributed to the ' \
                                   'media file stored by the iCloud account.'
        self.helper_dict = {
            'File Properties': {
                'Current Filename': ['IMG_1123.MOV',
                                     'Photos.sqlite\nZASSET.ZFILENAME'],
                'Folder Path': ['DCIM/110APPLE',
                                'Photos.sqlite\nZASSET.ZDIRECTORY'],
                'Original Filename': ['chat-media-video-02cd54e6-3097.mov',
                                      'Photos.sqlite\nZASSET.ZORIGINALFILENAME'],
                'Imported By': ['3rd Party Package/App',
                                'Photos.sqlite\nZADDITIONALASSETATTRIBUTES.ZIMPORTEDBY\n1 = Back Camera\n'
                                '2 = Front Camera\n3 = 3rd Party Package/App\n6 = 3rd Party Package/App\n'
                                '8 = System Package/App\n9 = Native Package/App'],
                'Parent Application': ['com.toyopagroup.picaboo',
                                       'Photos.sqlite\nZADDITIONALASSETATTRIBUTES.ZCREATORBUNDLEID'],
                'File Type': ['Video',
                              'Photos.sqlite\nZASSET.ZKIND\n1 = Video\n0 = Image'],
                'Orientation': ['Vertical (Up)',
                                'Photos.sqlite\nZASSET.ZORIENTATION\n1 = Horizontal (Left)\n3 = Horizontal (Right)\n'
                                '6 = Vertical (Up)\n8 = Vertical (Down)'],
                'Duration': ['9 seconds',
                             'Photos.sqlite\nZASSET.ZDURATION'],
                'Playback Style': ['Video Frames',
                                   'Photos.sqlite\nZASSET.ZPLAYBACKSTYLE\n1 = Static Image\n3 = Live Image '
                                   '(embedded frames)\n4 = Video Frames'],
                'File Size': ['2514767b [2.4MB]',
                              'Photos.sqlite\nZADDITIONALASSETATTRIBUTES.ZORIGINALFILESIZE'],
                'Dimensions': ['544 x 976',
                               'Photos.sqlite\nZADDITIONALASSETATTRIBUTES.ZORIGINALWIDTH\n'
                               'ZADDITIONALASSETATTRIBUTES.ZORIGINALHEIGHT'],
                'Thumbnail Index': ['32',
                                    'Photos.sqlite\nZASSET.ZTHUMBNAILINDEX'],
                'Thumbnail Filename': ['5005.JPG',
                                       'PhotoData/Thumbnails/thumbnailConfiguration'],
                'Created Timestamp': ['2021-02-14 09:04:16',
                                      'Photos.sqlite\nZASSET.ZDATECREATED\nCocoa Timstamp'],
                'Modified Timestamp': ['2021-02-14 09:04:36',
                                       'Photos.sqlite\nZASSET.ZMODIFICATIONDATE\nCocoa Timstamp'],
                'Added Timestamp': ['2021-02-14 09:04:40',
                                    'Photos.sqlite\nZASSET.ZADDEDDATE\nCocoa Timstamp'],
                'EXIF Timestamp': ['2021:02:14 09:04:16',
                                   'Photos.sqlite\nZADDITIONALASSETATTRIBUTES.ZEXIFTIMESTAMPSTRING\nCocoa Timstamp'],
                'Geo-Coords': ['40.7567765, -73.9870375',
                               'Photos.sqlite\nZASSET.ZLATITUDE\nZASSET.ZLONGITUDE\n'
                               'Approximate location resolved by the iOS device using the '
                               'devices internet connection.'],
                'Location Lookup': ['Times Square, Manhattan, NY 10036, United States',
                                    'Photos.sqlite\nZADDITIONALASSETATTRIBUTES.ZREVERSELOCATIONDATA\n'
                                    'Approximate location resolved by the iOS device using the '
                                    'devices internet connection.'],
                'Original Hash': ['0169C10B8525E5EC8F1C568FF30BBAC83CE05EA819',
                                  'Photos.sqlite\nZADDITIONALASSETATTRIBUTES.ZORIGINALHASH']},

            'Additional Properties': {
                'Album': ['USA',
                          'Photos.sqlite\nZGENERICALBUM.ZTITLE'],
                'Album (Cloud State)': ['Remote',
                                        'Photos.sqlite\nZGENERICALBUM.ZCLOUDLOCALSTATE\n'
                                        '0 = Local (Stored only on the device)\n'
                                        '1 = Remote (Is also stored in the cloud)'],
                'Trash State': ['Not Deleted',
                                'Photos.sqlite\nZASSET.ZTRASHEDSTATE\n'
                                'Can be found in the iOS Trash folder (remains for 30 days before the media is '
                                'securely deleted)'],
                'Trashed Date': ['None',
                                 'Photos.sqlite\nZASSET.ZTRASHEDDATE'],
                'Hidden': ['Yes',
                           'Photos.sqlite\nZASSET.ZHIDDEN\n0 = No\n1 = Yes'],
                'Favourite': ['No',
                              'Photos.sqlite\nZASSET.ZFAVORITE\n0 = No\n1 = Yes'],
                'View Count': ['5',
                               'Photos.sqlite\nZADDITIONALASSETATTRIBUTES.ZVIEWCOUNT'],
                'Play Count': ['5',
                               'Photos.sqlite\nZADDITIONALASSETATTRIBUTES.ZPLAYCOUNT'],
                '\n\nAdjusted/Mutated': ['', "iOS gives users to ability to modify and adjust captured or stored media."
                                             "This can include cropping, enhancing and converting a photo or trimming "
                                             "a video by reducing the frames. An adjusted media file can be saved as "
                                             "a new file, or in place of the existing file. The original filename and "
                                             "the adjustment details can provide insight into the previous name, the "
                                             "application used to make the adjustment and the timestamp of the "
                                             "adjustment. If the mutated version is saved a new file, the original "
                                             "file is kept in the DCIM directory while the mutated copy is stored "
                                             "in /PhotoData/Mutations/"],
                '\nAdjusted': ['\nYes',
                               'Photos.sqlite\nZASSET.ZHASADJUSTMENTS\n0 = No\n1 = Yes'],
                'Adjusted using': ['com.apple.mobileslideshow com.apple.photo (Photos)',
                                   'Photos.sqlite\nZADDITIONALASSETATTRIBUTES.ZEDITORBUNDLEID\n'
                                   'ZUNMANAGEDADJUSTMENT.ZADJUSTMENTFORMATIDENTIFIER'],
                'Adjusted Timestamp': ['2021-02-26 20:14:02',
                                       'Photos.sqlite\nZUNMANAGEDADJUSTMENT.ZADJUSTMENTTIMESTAMP\nCocoa Timestamp']},

            'Cloud Properties': {
                'Cloud State': ['Remote',
                                'Photos.sqlite\nZASSET.ZCLOUDLOCALSTATE\n'
                                '0 = Local (Stored only on the device)\n'
                                '1 = Remote (Is also stored in the cloud)'],
                'Saved Asset Type': ['From Device',
                                     'Photos.sqlite\nZASSET.ZSAVEDASSETTYPE\n6 = From Cloud\n3 = From Device'],
                'Share Count': ['1',
                                'Photos.sqlite\nZADDITIONALASSETATTRIBUTES.ZSHARECOUNT\nNumber of times shared with '
                                'other iCloud users or publicly'],
                'Shared URL': ['https://share.icloud.com/photos/06p9iNM-fg',
                               'Photos.sqlite\nZSHARE.ZSHAREURL'],
                'Shared From': ['2020-02-19 18:45:45',
                                'Photos.sqlite\nZSHARE.ZSTARTDATE\nCocoa Timestamp'],
                'Shared Expires': ['2021-04-19 20:18:37',
                                   'Photos.sqlite\nZSHARE.ZEXPIRYDATE\nCocoa Timestamp'],
                'Cloud Owner': ["David's iPhone",
                                'store.cloudphotodb\ncloudCache.SerializedRecord\nThe device name responsible for '
                                'primarily syncing the file to the cloud. Apple also refer to this as the Default '
                                'Owner.'],
                'File Fingerprint': ['Ad1XQdDwxuHQ5gyKNSUlkXGdQYJX',
                                     'Photos.sqlite\nZADDITIONALASSETATTRIBUTES.ZMASTERFINGERPRINT'],
                '\n\nRecovered Cloud Metadata': ['', "iCloud\niCloud Photos automatically stores an original copy of "
                                                     "all user photos and videos on remote Apple servers, syncing said "
                                                     "media across all connected devices that share the same iCloud "
                                                     "account. Unless a user modifies the settings, lightweight, "
                                                     "lower resolution copies of these files are synced with said "
                                                     "devices while the originals remain on the server. iCloud offers "
                                                     "Shared Albums to users so they can share an album with selected "
                                                     "individuals. Comments can be created for media by those who have "
                                                     "shared access."],
                '\nSoftware': ['\n14.1', cloudmastermediametadata],
                'DateTime': ['2021-02-14 09:04:16', cloudmastermediametadata],
                'Model': ['iPhone 8 Plus', cloudmastermediametadata],
                'Make': ['Apple', cloudmastermediametadata],
                'DateTimeOriginal': ['2021-02-14 09:04:16', cloudmastermediametadata],
                'DateTimeDigitized': ['2021-02-14 09:04:16', cloudmastermediametadata],
                'LensModel': ['iPhone 8 Plus back dual camera 3.99mm f/1.8', cloudmastermediametadata],
                'Latitude': ['40.7567765', cloudmastermediametadata],
                'Longitude': ['-73.9870375', cloudmastermediametadata],
                'PixelHeight': ['544', cloudmastermediametadata],
                'ColorModel': ['RGB', cloudmastermediametadata],
                'PixelWidth': ['976', cloudmastermediametadata]}
                       }

        grid = QGridLayout()
        grid.setContentsMargins(1, 1, 1, 1)
        grid.addWidget(self.info_panel(), 0, 0, 1, 4)
        grid.addWidget(self.image_widget(), 1, 0, 2, 1)
        grid.addWidget(self.file_properties_widget(), 1, 1, 2, 1)
        grid.addWidget(self.additional_properties_widget(), 1, 2, 1, 1)
        grid.addWidget(self.cloud_properties_widget(), 1, 3, 2, 1)
        self.setLayout(grid)

        self.setWindowTitle("SIFT Helper")
        self.setWindowIcon(QIcon(resource_path('controlF.ico')))

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Enter:
            obj.setToolTip(obj.objectName())
        return False

    @classmethod
    def info_panel(cls):
        groupbox = QGroupBox()
        layout = QGridLayout()

        header = QLabel('Sift Help & Report Key\n')
        header.setFont(QFont("Consolas", 18, weight=QFont.Bold))
        header.setStyleSheet("color: '#e6ccb3';")
        layout.addWidget(header, 0, 0, 1, 1)

        instructions = QLabel('Please hover over the report fields (including headers) for details regarding the '
                              'property and the database, e.g. Photos.sqlite.'
                              '\n\nWhere a database is cited, further details regarding the table '
                              'and column will be given, e.g ZASSET.ZFILENAME. If the values have been decoded, '
                              'details of the conversions made will be listed e.g Boolean values such as: 1 = Yes')
        layout.addWidget(instructions, 1, 0, 1, 1)

        groupbox.setLayout(layout)
        return groupbox

    @staticmethod
    def image_widget():
        groupbox = QGroupBox()
        layout = QGridLayout()

        img = QLabel()
        img.setPixmap(transform_image(pj(resource_path('times_square.jpg')), 600, 600))
        layout.addWidget(img, 0, 0, 1, 1, alignment=Qt.AlignTop)

        groupbox.setLayout(layout)
        return groupbox

    def file_properties_widget(self):
        groupbox = QGroupBox()
        layout = QGridLayout()
        header = QLabel('File Properties\n')
        header.setFont(QFont("Consolas", weight=QFont.Bold))
        header.setStyleSheet("color: '#e6ccb3';")
        layout.addWidget(header, 0, 0, 1, 1)
        count = 1
        for field, details in self.helper_dict['File Properties'].items():
            field_lbl = QLabel('{}: '.format(field))
            field_lbl.setFont(QFont("Consolas", weight=QFont.Bold))
            layout.addWidget(field_lbl, count, 0, 1, 1)
            lbl = QLabel('{}'.format(details[0]))
            lbl.setObjectName(details[1])
            lbl.installEventFilter(self)
            layout.addWidget(lbl, count, 1, 1, 1)
            count += 1
        groupbox.setLayout(layout)
        return groupbox

    def additional_properties_widget(self):
        groupbox = QGroupBox()
        layout = QGridLayout()
        header = QLabel('Additional Properties\n')
        header.setFont(QFont("Consolas", weight=QFont.Bold))
        header.setStyleSheet("color: '#e6ccb3';")
        layout.addWidget(header, 0, 0, 1, 1)
        count = 1
        for field, details in self.helper_dict['Additional Properties'].items():
            field_lbl = QLabel('{}: '.format(field))
            field_lbl.setFont(QFont("Consolas", weight=QFont.Bold))
            layout.addWidget(field_lbl, count, 0, 1, 1)
            lbl = QLabel('{}'.format(details[0]))
            lbl.setObjectName(details[1])
            lbl.installEventFilter(self)
            layout.addWidget(lbl, count, 1, 1, 1)
            count += 1
        groupbox.setLayout(layout)
        return groupbox

    def cloud_properties_widget(self):
        groupbox = QGroupBox()
        layout = QGridLayout()
        header = QLabel('Cloud Properties\n')
        header.setFont(QFont("Consolas", weight=QFont.Bold))
        header.setStyleSheet("color: '#e6ccb3';")
        layout.addWidget(header, 0, 0, 1, 1)
        count = 1
        for field, details in self.helper_dict['Cloud Properties'].items():
            field_lbl = QLabel('{}: '.format(field))
            field_lbl.setFont(QFont("Consolas", weight=QFont.Bold))
            layout.addWidget(field_lbl, count, 0, 1, 1)
            lbl = QLabel('{}'.format(details[0]))
            lbl.setObjectName(details[1])
            lbl.installEventFilter(self)
            layout.addWidget(lbl, count, 1, 1, 1)
            count += 1
        groupbox.setLayout(layout)
        return groupbox


class AboutSift(QDialog):
    def __init__(self):
        super(AboutSift, self).__init__()
        self.setFixedSize(500, 800)
        buttonbox = QDialogButtonBox(QDialogButtonBox.Cancel)
        buttonbox.rejected.connect(self.reject)

        with open(resource_path('credits.txt'), 'r') as credits_in:
            self.credits = credits_in.read()
        with open(resource_path('EULA.txt'), 'r') as eula_in:
            self.eula = eula_in.read()
        with open(resource_path('release_notes.txt'), 'r') as updates_in:
            self.releasenotes = updates_in.read()

        grid = QGridLayout()
        grid.setContentsMargins(1, 1, 1, 1)
        header = QLabel('Sift\n')
        header.setFont(QFont("Arial", 18, weight=QFont.Bold))
        header.setStyleSheet("color: '#e6ccb3';")

        description_header = QLabel(__description__)
        contact = QLabel('Contact: info@controlf.net')
        author = QLabel('Author: {}'.format(__author__))
        version = QLabel('Version: {}'.format(__version__))
        grid.addWidget(header,                      0, 0, 1, 1)
        grid.addWidget(description_header,          1, 0, 1, 1)
        grid.addWidget(contact,                     2, 0, 1, 1)
        grid.addWidget(author,                      3, 0, 1, 1)
        grid.addWidget(version,                     4, 0, 1, 1)
        grid.addWidget(self.eula_widget(),          5, 0, 3, 1)
        grid.addWidget(self.credits_widget(),       8, 0, 1, 1)
        grid.addWidget(self.updates_widget(),       11, 0, 1, 1)

        self.setLayout(grid)
        self.setWindowTitle("About Sift")
        self.setWindowIcon(QIcon(resource_path('controlF.ico')))

    def eula_widget(self):
        groupbox = QGroupBox()
        groupbox.setFlat(True)
        layout = QGridLayout()
        header = QLabel('Licence Agreement')
        header.setStyleSheet("color: '#e6ccb3';")
        layout.addWidget(header, 0, 0, 1, 1)
        eula_agreement = QPlainTextEdit()
        layout.addWidget(eula_agreement, 1, 0, 1, 1)
        eula_agreement.insertPlainText('{}'.format(self.eula))
        eula_agreement.setReadOnly(True)
        eula_agreement.moveCursor(QTextCursor.Start, QTextCursor.MoveAnchor)
        groupbox.setLayout(layout)
        return groupbox

    def credits_widget(self):
        groupbox = QGroupBox()
        groupbox.setFlat(True)
        layout = QGridLayout()
        header = QLabel('Credits')
        header.setStyleSheet("color: '#e6ccb3';")
        layout.addWidget(header, 0, 0, 1, 1)
        credit_text_box = QPlainTextEdit()
        layout.addWidget(credit_text_box, 1, 0, 1, 1)
        credit_text_box.insertPlainText('{}'.format(self.credits))
        credit_text_box.setReadOnly(True)
        groupbox.setLayout(layout)
        return groupbox

    def updates_widget(self):
        groupbox = QGroupBox()
        groupbox.setFlat(True)
        layout = QGridLayout()
        header = QLabel('Release Notes')
        header.setStyleSheet("color: '#e6ccb3';")
        layout.addWidget(header, 0, 0, 1, 1)
        updates_text_box = QPlainTextEdit()
        layout.addWidget(updates_text_box, 1, 0, 1, 1)
        updates_text_box.insertPlainText('{}'.format(self.releasenotes))
        updates_text_box.setReadOnly(True)
        updates_text_box.moveCursor(QTextCursor.Start, QTextCursor.MoveAnchor)
        groupbox.setLayout(layout)
        return groupbox


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(open(resource_path('dark_style.qss')).read())
    ex = GUI()
    ex.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
