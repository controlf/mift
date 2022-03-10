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


Credits

Yogesh Khatri - KTX > PNG script/executable  (Some modifications made)
https://github.com/ydkhatri/MacForensics/tree/master/IOS_KTX_TO_PNG

CCL Forensics Binary Plist Parser
https://github.com/cclgroupltd/ccl-bplist

"""

__author__ = 'Mike Bangham - Control-F'
__version__ = '1.09'
__description__ = 'Mobile Image Forensic Toolkit'

from PyQt5.QtWidgets import (QApplication, QWidget, QPushButton, QMainWindow, QDialog, QLabel, QGridLayout,
                             QPlainTextEdit, QGroupBox, QDialogButtonBox, QProgressBar, QFileDialog)
from PyQt5.QtGui import QIcon, QFont, QPixmap, QTextCursor
from PyQt5.QtCore import Qt, QEvent
import os
import logging
import sys
import platform
from os.path import join as pj
from os.path import isfile, abspath
import webbrowser as wb
import tkinter
from tkinter.filedialog import askopenfilename

from src import (apple_report, huawei_report,
                 ktx_snapshot_report, samsung_report, sony_report,
                 verify_archive, utils)

from src.utils import resource_path, transform_image

if hasattr(Qt, 'AA_EnableHighDpiScaling'):
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)

if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

start_dir = os.getcwd()
app_data_dir = os.getenv('APPDATA')
os.makedirs(pj(app_data_dir, 'CF_MIFT'), exist_ok=True)
log_file_fp = pj(app_data_dir, 'CF_MIFT', 'logs.txt')


def init_log():
    # init log file
    logging.basicConfig(filename=log_file_fp, level=logging.DEBUG, format='%(asctime)s | %(levelname)s | %(message)s',
                        filemode='a')
    logging.info('{0} Control-F   mift   v.{1} {0}'.format('{}'.format('#'*20), __version__))
    logging.info('Program start')
    logging.debug('System: {}'.format(sys.platform))
    logging.debug('Version: {}'.format(sys.version))
    logging.debug('Host: {}'.format(platform.node()))
    logging.info('mift Temp directory: {}'.format(pj(app_data_dir, 'CF_MIFT', 'temp')))


def open_log():
    if not isfile(log_file_fp):
        open(log_file_fp, 'a').close()
    wb.open(log_file_fp)


class GUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('mift')
        self.setWindowIcon(QIcon(resource_path('controlF.ico')))
        self.setFixedSize(600, 255)
        window_widget = QWidget(self)
        self.setCentralWidget(window_widget)
        self.message_count = 0
        self.function_dict = self.build_function_dict()
        init_log()
        self._create_menu()

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.addWidget(self.main_panel(), 0, 0, 1, 1)
        window_widget.setLayout(grid)

    def build_function_dict(self):
        # Builds the functions and associated data for easy lookups
        fd = {'iOS Photos': {'func': apple_report.MakeAppleReport,
                             'blurb': [],
                             'required_files': []},
              'iOS Snapshots': {'func': ktx_snapshot_report.MakeSnapShotReport,
                                'blurb': [],
                                'required_files': []},
              'Huawei': {'func': huawei_report.MakeHuaweiReport,
                         'blurb': [],
                         'required_files': []},
              'Samsung': {'func': samsung_report.MakeSamsungReport,
                          'blurb': [],
                          'required_files': []},
              'Sony': {'func': sony_report.MakeSonyReport,
                       'blurb': [],
                       'required_files': []}}

        for oem in fd.keys():
            with open(resource_path(pj('config', '{}.txt'.format(oem))), 'r') as f:
                content = f.read().splitlines()
                fd[oem]['blurb'] = content[0]
                fd[oem]['required'] = content[1:]
        return fd

    def _get_dir_dialog(self, oem):
        self.select_datadir_btn.hide()
        self.output_display.clear()

        for btn in [self.select_huawei_btn, self.select_samsung_btn, self.select_sony_btn, 
                    self.select_ios_photos_btn, self.select_ios_snapshots_btn]:
            btn.hide()

        tkinter.Tk().withdraw()  # PYQT5 dialog freezes when selecting large zips; tkinter does not
        archive = askopenfilename(title=oem, initialdir=os.getcwd())
        if archive:
            self._init_archive_verification(archive, self.function_dict[oem]['required'], oem)
        else:
            self.reset_widgets()

    def _progress_verification(self, txt):
        self.status_lbl.setText('{}'.format(txt))

    def _finished_verification(self, verification_status):
        errors, oem, archive = verification_status
        if errors:
            self.reset_widgets()
            for err in errors:
                logging.error(err)
                self.output_display.insertPlainText('{}\n'.format(err))
        else:
            self.status_lbl.setText('Verified successfully. Analysing files...')

            # Get the save directory
            dialog = QFileDialog(self, 'Report Save Location', start_dir)
            dialog.setFileMode(QFileDialog.DirectoryOnly)
            if dialog.exec_() == QDialog.Accepted:
                report_dir = dialog.selectedFiles()[0]
            else:
                report_dir = abspath(archive)

            logging.info('Report saved to: {}'.format(report_dir))
            temp_out = utils.refresh_temp_dir()  # Create a fresh temp directory
            logging.info('User selected: {}'.format(oem))
            logging.info('User selected report output directory: {}'.format(report_dir))

            # call the function for the chosen owm
            self.function_dict[oem]['func'](self, archive, report_dir, temp_out)

    def _init_archive_verification(self, archive, required, oem):
        self._verify_archive_thread = verify_archive.VerifyArchiveThread(self, archive, required, oem)
        self._verify_archive_thread.progressSignal.connect(self._progress_verification)
        self._verify_archive_thread.finishedSignal.connect(self._finished_verification)
        self._verify_archive_thread.setTerminationEnabled(True)
        self._verify_archive_thread.start()

    def _show_instructions(self, oem):
        try:
            self.select_datadir_btn.clicked.disconnect()
        except:
            pass
        self.output_display.clear()
        self.output_display.insertPlainText('\n'.join(self.function_dict[oem]['blurb'].split('||')))
        self.select_datadir_btn.clicked.connect(lambda: self._get_dir_dialog(oem))
        self.select_datadir_btn.show()

    def _create_menu(self):
        self.filemenu = self.menuBar().addMenu("&File")
        self.filemenu.addAction('&Logs', lambda: open_log())

        self.aboutmenu = self.menuBar().addMenu("&About")
        self.aboutmenu.addAction('&Info', lambda: AboutMift().exec_())

        self.helpmenu = self.menuBar().addMenu("&Help")
        self.helpmenu.addAction('&Key', lambda: HelpDialog().exec_())

    def main_panel(self):
        groupbox = QGroupBox()
        groupbox.setFont(QFont("Arial", weight=QFont.Bold))
        self.main_layout = QGridLayout()
        self.main_layout.setContentsMargins(2, 2, 2, 2)

        control_f_emblem = QLabel()
        emblem_pixmap = QPixmap(resource_path('ControlF_R_RGB.png')).scaled(200, 200, Qt.KeepAspectRatio,
                                                                            Qt.SmoothTransformation)
        control_f_emblem.setPixmap(emblem_pixmap)

        self.output_display = QPlainTextEdit()
        self.output_display.setFixedHeight(180)
        self.output_display.setReadOnly(True)
        self.output_display.setStyleSheet('border: 0;')

        self.select_sony_btn = QPushButton('Sony')
        self.select_sony_btn.clicked.connect(lambda: self._show_instructions('Sony'))

        self.select_samsung_btn = QPushButton('Samsung')
        self.select_samsung_btn.clicked.connect(lambda: self._show_instructions('Samsung'))

        self.select_huawei_btn = QPushButton('Huawei')
        self.select_huawei_btn.clicked.connect(lambda: self._show_instructions('Huawei'))

        self.select_ios_photos_btn = QPushButton('iOS Photos')
        self.select_ios_photos_btn.clicked.connect(lambda: self._show_instructions('iOS Photos'))

        self.select_ios_snapshots_btn = QPushButton('iOS Snapshots')
        self.select_ios_snapshots_btn.clicked.connect(lambda: self._show_instructions('iOS Snapshots'))

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

        self.setWindowTitle("mift Helper")
        self.setWindowIcon(QIcon(resource_path('controlF.ico')))

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Enter:
            obj.setToolTip(obj.objectName())
        return False

    @staticmethod
    def info_panel():
        groupbox = QGroupBox()
        layout = QGridLayout()

        header = QLabel('mift - Help & Report Key\n')
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


class AboutMift(QDialog):
    def __init__(self):
        super(AboutMift, self).__init__()
        self.setFixedSize(500, 600)
        buttonbox = QDialogButtonBox(QDialogButtonBox.Cancel)
        buttonbox.rejected.connect(self.reject)

        with open(resource_path('credits.txt'), 'r') as credits_in:
            self.credits = credits_in.read()
        with open(resource_path('EULA.txt'), 'r') as eula_in:
            self.eula = eula_in.read()
        with open(resource_path('release_notes.txt'), 'r') as updates_in:
            self.releasenotes = updates_in.read()

        grid = QGridLayout()
        grid.setContentsMargins(0,0,0,0)
        header = QLabel('mift')
        header.setFont(QFont("Arial", 16, weight=QFont.Bold))
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
        grid.addWidget(self.eula_widget(),          5, 0, 1, 1)
        grid.addWidget(self.credits_widget(),       6, 0, 1, 1)
        grid.addWidget(self.updates_widget(),       7, 0, 1, 1)

        self.setLayout(grid)
        self.setWindowTitle("About mift")
        self.setWindowIcon(QIcon(resource_path('controlF.ico')))

    def eula_widget(self):
        groupbox = QGroupBox()
        groupbox.setFlat(True)
        layout = QGridLayout()
        header = QLabel('Licence Agreement')
        header.setStyleSheet("color: '#e6ccb3';")
        layout.addWidget(header, 0, 0, 1, 1)
        eula_agreement = QPlainTextEdit()
        eula_agreement.setFixedHeight(150)
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
        credit_text_box.setFixedHeight(80)
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
