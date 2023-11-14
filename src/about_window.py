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

__author__ = 'mike.bangham@controlf.co.uk'
__description__ = 'Mobile Image Forensic Toolkit'

from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
import os
from os.path import join as pj

from src.utils import resource_path, transform_image

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


class AboutMift(QDialog):
    def __init__(self):
        super(AboutMift, self).__init__()
        self.setFixedSize(850, 850)
        buttonbox = QDialogButtonBox(QDialogButtonBox.Cancel)
        buttonbox.rejected.connect(self.reject)

        with open(resource_path('credits.txt'), 'r') as credits_in:
            self.credits = credits_in.read()
        with open(resource_path('EULA.txt'), 'r') as eula_in:
            self.eula = eula_in.read()
        with open(resource_path('release_notes.txt'), 'r') as updates_in:
            self.releasenotes = updates_in.read()

        grid = QGridLayout()
        grid.setContentsMargins(5,5,5,5)
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
        self.setWindowTitle("About")
        self.setWindowIcon(QIcon(resource_path('controlF.ico')))

    def eula_widget(self):
        groupbox = QGroupBox()
        groupbox.setFlat(True)
        layout = QGridLayout()
        header = QLabel('Licence Agreement')
        header.setStyleSheet("color: '#e6ccb3';")
        layout.addWidget(header, 0, 0, 1, 1)
        eula_agreement = QPlainTextEdit()
        eula_agreement.setFixedHeight(180)
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
        credit_text_box.setFixedHeight(180)
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
        updates_text_box.setFixedHeight(180)
        layout.addWidget(updates_text_box, 1, 0, 1, 1)
        updates_text_box.insertPlainText('{}'.format(self.releasenotes))
        updates_text_box.setReadOnly(True)
        updates_text_box.moveCursor(QTextCursor.Start, QTextCursor.MoveAnchor)
        groupbox.setLayout(layout)
        return groupbox
