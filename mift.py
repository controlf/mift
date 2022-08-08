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


Credits

Yogesh Khatri - KTX > PNG script/executable  (Some modifications made)
https://github.com/ydkhatri/MacForensics/tree/master/IOS_KTX_TO_PNG

CCL Forensics Binary Plist Parser
https://github.com/cclgroupltd/ccl-bplist

HTML report - modified - Mike Bangham - Control-F 2021-2022
Original HTML prior to modification: Copyright (c) Facebook, Inc. and its affiliates.

"""

__author__ = 'Mike Bangham - Control-F'
__description__ = 'Mobile Image Forensic Toolkit'

from PyQt5.QtWidgets import (QApplication, QWidget, QMainWindow, QTabWidget, QGroupBox, QSizePolicy,
                             QGridLayout, QTableView, QTextEdit, QAbstractScrollArea,
                             QAbstractItemView, QLabel, QPushButton, QProgressBar, QLineEdit)
from PyQt5.QtGui import QIcon, QFont, QPixmap, QTextCursor
from PyQt5.QtCore import Qt, QSize, QRegExp, pyqtSlot, QSortFilterProxyModel
import os
import logging
import pandas as pd
import sys
from time import strftime
import platform
from os.path import join as pj
from os.path import isfile, abspath
import webbrowser as wb
import tkinter
import requests
import json
from datetime import datetime
from tkinter.filedialog import askopenfilename

from src import (apple_report, huawei_report, report_builder, samsung_gallery_report,
                 ktx_snapshot_report, samsung_report, sony_report,
                 verify_archive, utils, about_window, help_window,
                 save_dialog, image_delegate, pandas_model)

from src.utils import resource_path

if hasattr(Qt, 'AA_EnableHighDpiScaling'):
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)

if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

start_dir = os.getcwd()
app_data_dir = os.getenv('APPDATA')
os.makedirs(pj(app_data_dir, 'CF_MIFT'), exist_ok=True)
log_file_fp = pj(app_data_dir, 'CF_MIFT', 'logs.txt')
font = QFont('Consolas', 8, QFont.Light)
font.setKerning(True)
font.setFixedPitch(True)
__version__ = open(resource_path('version'), 'r').readlines()[0]
updates_available = [False, '']


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


def check_for_updates():
    global updates_available
    try:
        response = requests.get("https://api.github.com/repos/controlf/mift/releases/latest")
        latest = response.json()['name']
        if latest == 'v{}'.format(__version__):
            pass
        else:
            updates_available = [True, '{} update available - https://github.com/controlf/mift'.format(latest)]
    except:
        updates_available = [False, 'Offline - Check for updates (https://github.com/controlf/mift)']


class GUI(QMainWindow):
    def __init__(self):
        super().__init__()
        init_log()
        check_for_updates()
        self.setWindowTitle('mift           Control-F            v{}    {}'.format(__version__, updates_available[1]))
        self.setWindowIcon(QIcon(resource_path('controlF.ico')))
        window_widget = QWidget(self)
        self.setCentralWidget(window_widget)
        self.function_dict = self.build_function_dict()
        self._create_menu()
        self._init_tabs()

        control_f_emblem = QLabel()
        emblem_pixmap = QPixmap(resource_path('ControlF_R_RGB.png')).scaled(300, 300,
                                                                            Qt.KeepAspectRatio, Qt.SmoothTransformation)
        control_f_emblem.setPixmap(emblem_pixmap)

        self._maingrid = QGridLayout()
        self._maingrid.setContentsMargins(0, 0, 0, 0)
        self._maingrid.addWidget(self.tabs,              0, 0, 98, 20)
        self._maingrid.addWidget(self.log_widget(),      99, 0, 3, 19, alignment=(Qt.AlignLeft | Qt.AlignBottom))
        self._maingrid.addWidget(control_f_emblem,       99, 19, 1, 1, alignment=(Qt.AlignRight | Qt.AlignBottom))
        window_widget.setLayout(self._maingrid)

        self.showMaximized()

        self.init_clean_temp()

    def init_clean_temp(self):
        self.clean_thread = utils.CleanTemp(abspath(pj(app_data_dir, 'CF_MIFT', 'temp')))
        self.clean_thread.start()

    def _create_menu(self):
        self.filemenu = self.menuBar().addMenu("&File")
        self.filemenu.addAction('&Logs', lambda: open_log())

        self.openmenu = self.menuBar().addMenu("&Open")
        for oem, fd in self.func_dict.items():
            self.openmenu.addAction('&{}'.format(oem), (lambda e=oem: self._get_archive_dialog(e)))

        self.aboutmenu = self.menuBar().addMenu("&About")
        self.aboutmenu.addAction('&Info', lambda: about_window.AboutMift().exec_())

        self.helpmenu = self.menuBar().addMenu("&Help")
        self.helpmenu.addAction('&Key', lambda: help_window.HelpDialog().exec_())

    def _init_tabs(self):
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.setElideMode(Qt.ElideRight)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Ignored)
        self.tabs.tabCloseRequested.connect(self._close_tab)

    def _close_tab(self, index):
        tab = self.tabs.widget(index)
        tab.deleteLater()
        self.tabs.removeTab(index)

    def build_function_dict(self):
        # Builds the functions and associated data for easy lookups
        self.func_dict = {'iOS Photos': {'func': apple_report.MakeAppleReport,
                                         'blurb': [],
                                         'required_files': []},
                          'iOS Snapshots': {'func': ktx_snapshot_report.MakeSnapShotReport,
                                            'blurb': [],
                                            'required_files': []},
                          'Huawei Gallery Cache': {'func': huawei_report.MakeHuaweiReport,
                                                   'blurb': [],
                                                   'required_files': []},
                          'Samsung File Cache': {'func': samsung_report.MakeSamsungReport,
                                                 'blurb': [],
                                                 'required_files': []},
                          'Sony Picnic Cache': {'func': sony_report.MakeSonyReport,
                                                'blurb': [],
                                                'required_files': []},
                          'Samsung Gallery': {'func': samsung_gallery_report.MakeSamsungReport,
                                                'blurb': [],
                                                'required_files': []}}

        for oem in self.func_dict.keys():
            with open(resource_path('{}.txt'.format(oem)), 'r') as f:
                content = f.read().splitlines()
                self.func_dict[oem]['blurb'] = content[0]
                self.func_dict[oem]['required'] = content[1:]
        return self.func_dict

    def add_log(self, txt):
        dt = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        self.log_tb.insertPlainText('[{}] {}\n'.format(dt, txt))
        self.log_tb.moveCursor(QTextCursor.End)

    def log_widget(self):
        groupbox = QGroupBox()
        groupbox.setFont(QFont("Arial", weight=QFont.Bold))
        self.log_display_layout = QGridLayout()
        self.log_display_layout.setContentsMargins(0, 0, 0, 0)

        self.log_tb = QTextEdit()
        self.log_tb.setReadOnly(True)
        self.log_display_layout.addWidget(self.log_tb, 0, 0, 1, 1)
        self.log_tb.setFont(font)
        self.log_tb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.log_tb.setMinimumWidth(1600)
        self.log_tb.setMinimumHeight(75)
        self.log_tb.setMaximumWidth(1800)
        self.log_tb.setMaximumHeight(100)
        self.log_tb.verticalScrollBar().hide()
        self.log_tb.horizontalScrollBar().hide()

        groupbox.setLayout(self.log_display_layout)
        return groupbox

    def display_data(self):
        groupbox = QGroupBox()
        groupbox.setFont(QFont("Arial", weight=QFont.Bold))
        self.display_layout = QGridLayout()
        self.display_layout.setContentsMargins(0, 0, 0, 0)

        self.tb = QTextEdit()
        self.display_layout.addWidget(self.tb, 0, 0, 1, 1)
        groupbox.setLayout(self.display_layout)
        return groupbox

    def _get_archive_dialog(self, oem):
        tkinter.Tk().withdraw()  # PYQT5 dialog freezes when selecting large zips; tkinter does not
        archive = askopenfilename(title=oem, initialdir=os.getcwd())
        if archive:
            self._init_archive_verification(archive, self.function_dict[oem]['required'], oem)

    def _progress_verification(self, txt):
        self.add_log('{}'.format(txt))

    def _finished_verification(self, verification_status):
        errors, oem, archive = verification_status
        if errors:
            for err in errors:
                logging.error(err)
                self.add_log(err)
        else:
            self.add_log('Verified successfully. Analysing files...')
            temp_out = utils.refresh_temp_dir()  # Create a fresh temp directory
            logging.info('User selected: {}'.format(oem))

            # call the function for the chosen oem
            self.tabs.addTab(DisplayTab(self, self.function_dict[oem]['func'], archive, temp_out, oem), oem)

    def _init_archive_verification(self, archive, required, oem):
        self._verify_archive_thread = verify_archive.VerifyArchiveThread(self, archive, required, oem)
        self._verify_archive_thread.progressSignal.connect(self._progress_verification)
        self._verify_archive_thread.finishedSignal.connect(self._finished_verification)
        self._verify_archive_thread.setTerminationEnabled(True)
        self._verify_archive_thread.start()


class DisplayTab(QWidget):
    def __init__(self, *args):
        super().__init__(parent=None)
        self.maingui, self.function, self.archive, self.temp_out, self.oem = args
        self.df = pd.DataFrame()

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.hide()

        self.grid = QGridLayout()
        self.grid.setContentsMargins(1, 1, 1, 1)
        self.grid.addWidget(self.progress_bar, 1, 0, 1, 1, alignment=Qt.AlignBottom)
        self.setLayout(self.grid)

        self.init_df_generation()

    def _progress_archive_extraction(self, objects):
        val, text = objects
        if val:
            self.progress_bar.setValue(val)
        if text:
            self.maingui.add_log(text)

    def _finished_archive_extraction(self, df):
        self.df = df
        self.grid.addWidget(self.table_view_panel(), 0, 0, 1, 1, alignment=Qt.AlignTop)
        self.progress_bar.hide()

    def init_df_generation(self):
        self.progress_bar.show()
        self.progress_bar.show()
        self.df_thread = self.function(self, self.maingui, self.archive, self.temp_out)
        self.df_thread.progressSignal.connect(self._progress_archive_extraction)
        self.df_thread.finishedSignal.connect(self._finished_archive_extraction)
        self.df_thread.start()

    def table_view_panel(self):
        groupbox = QGroupBox()
        layout = QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.tableview = QTableView()
        # Set our model to incorporate a dataframe
        model = pandas_model.PandasModel(self.df)

        # set our proxy so that we can use a search function on our tableview
        self.proxy = QSortFilterProxyModel(model)
        self.proxy.setSourceModel(model)
        self.tableview.setModel(self.proxy)

        self.tableview.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
        self.tableview.horizontalHeader().setMaximumSectionSize(300)
        self.tableview.resizeColumnsToContents()
        self.tableview.horizontalHeader().setStretchLastSection(True)
        self.tableview.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tableview.setSelectionBehavior(QAbstractItemView.SelectRows)

        if not self.df.empty:
            if 'media' in self.df.columns:
                self.has_media = True
                media_col = self.df['media']
                self.df.drop(labels=['media'], axis=1, inplace=True)
                self.df.insert(0, 'Media', media_col)

                column_icon = self.df.columns.values.tolist().index('Media')
                self.tableview.setItemDelegateForColumn(column_icon, image_delegate.ImageDelegate(self.tableview))

            else:
                self.has_media = False

        self.tableview.resizeRowsToContents()
        layout.addWidget(self.tableview, 0, 0, 1, 100)

        if not self.df.empty:
            self.dump_to_html_btn = QPushButton('')
            self.dump_to_html_btn.clicked.connect(lambda: self._init_report_thread('html', df))
            self.dump_to_html_btn.setIcon(QIcon(resource_path('html.png')))
            self.dump_to_html_btn.setIconSize(QSize(25, 25))
            layout.addWidget(self.dump_to_html_btn, 1, 0, 1, 1)

            self.dump_to_xlsx_btn = QPushButton('')
            self.dump_to_xlsx_btn.clicked.connect(lambda: self._init_report_thread('xlsx', df))
            self.dump_to_xlsx_btn.setIcon(QIcon(resource_path('xlsx.png')))
            self.dump_to_xlsx_btn.setIconSize(QSize(25, 25))
            layout.addWidget(self.dump_to_xlsx_btn, 1, 1, 1, 1)

            self.search_lbl = QLabel('Search')
            self.search_lbl.setFont(QFont("Arial", weight=QFont.Bold))
            layout.addWidget(self.search_lbl, 1, 3, 1, 1)
            self.search_input = QLineEdit()
            layout.addWidget(self.search_input, 1, 4, 1, 20)
            self.search_input.textChanged.connect(self.search_input_changed)

        groupbox.setLayout(layout)
        return groupbox

    @pyqtSlot(str)
    def search_input_changed(self, text):
        search = QRegExp(text, Qt.CaseInsensitive, QRegExp.RegExp)
        self.proxy.setFilterRegExp(search)
        self.proxy.setFilterKeyColumn(-1)  # search all columns

    def _thread_progress(self, i):
        self.progress_bar.setValue(i)

    def _thread_status(self, s):
        self.maingui.add_log(s)

    def _thread_complete(self, s):
        wb.open(s)
        self.progress_bar.setValue(0)
        self.progress_bar.hide()
        self.maingui.add_log('Report Generated!')

    def _init_report_thread(self, report_type, df):
        sd = save_dialog.SaveDialog(self.oem, report_type)
        rc = sd.exec_()
        if rc == 1:
            save_details = sd.get_value_dict()
            self.maingui.add_log('Generating {} report...'.format(report_type))

            dt = '{}_{}'.format(strftime('%d%m%y'), strftime('%H%M%S'))
            report_name = '{} Report'.format(self.oem)
            report_sub_dir = '{}_{}_{}'.format(report_type, self.oem, dt)
            os.makedirs(pj(save_details['save_dir'], report_sub_dir), exist_ok=True)

            self.progress_bar.show()
            if report_type == 'xlsx':
                out_fp = pj(save_details['save_dir'], report_sub_dir, '{} Report {}.xlsx'.format(self.oem, dt))
                self.xlsx_thread = report_builder.XLSXReportThread(report_name, out_fp, df,
                                                                   save_details,
                                                                   self.has_media, self.temp_out)
                self.xlsx_thread.statusSignal.connect(self._thread_status)
                self.xlsx_thread.progressSignal.connect(self._thread_progress)
                self.xlsx_thread.finishedSignal.connect(self._thread_complete)
                self.xlsx_thread.start()

            else:
                out_fp = pj(save_details['save_dir'], report_sub_dir, '{} Report {}.html'.format(self.oem, dt))
                self.html_thread = report_builder.HTMLReportThread(report_name, out_fp, df,
                                                                   save_details,
                                                                   self.has_media, self.temp_out)
                self.html_thread.statusSignal.connect(self._thread_status)
                self.html_thread.progressSignal.connect(self._thread_progress)
                self.html_thread.finishedSignal.connect(self._thread_complete)
                self.html_thread.start()


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(open(resource_path('dark_style.qss')).read())
    ex = GUI()
    ex.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
