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

# mift save dailog window

from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
import os
from src.utils import resource_path
start_dir = os.getcwd()


class SaveDialog(QDialog):
    def __init__(self, *args):
        super(SaveDialog, self).__init__()
        self.setFixedSize(420, 200)
        self.oem, self.report_type = args
        self.report_dir = None
        self.save_details = dict()
        self.main_widget()

        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.gb)
        self.setLayout(mainLayout)

        self.setWindowTitle("Save Location")
        self.setWindowIcon(QIcon(resource_path('controlF.ico')))

    def get_value_dict(self):
        return self.save_details

    def update_values(self):
        if self.report_dir:
            # staple parts
            self.save_details['save_dir'] = self.report_dir
            self.save_details['thumbsize'] = self.thumbnail_size.currentText()
            # custom parts
            self.save_details['meta'] = dict()
            self.save_details['meta']['investigator'] = self.name_input.text()
            self.save_details['meta']['collar'] = self.collar_input.text()
            self.save_details['meta']['position'] = self.position_input.text()
            self.save_details['meta']['organisation'] = self.force_input.text()
            self.accept()

    def get_save_dir(self):
        dialog = QFileDialog(self, 'Report Save Location', start_dir)
        dialog.setFileMode(QFileDialog.DirectoryOnly)
        if dialog.exec_() == QDialog.Accepted:
            self.report_dir = dialog.selectedFiles()[0]

            sp = os.path.normpath(self.report_dir).split(os.sep)
            self.save_location.setText('{}../{}/{}'.format(sp[0], sp[-2], sp[-1]))

    def main_widget(self):
        self.gb = QGroupBox()
        layout = QGridLayout()

        info = QLabel('{} Report'.format(self.oem))
        info.setFont(QFont("Arial", weight=QFont.Bold))
        layout.addWidget(info, 0, 0, 1, 4)

        name_header = QLabel('Name')
        name_header.setFont(QFont("Arial", weight=QFont.Bold))
        layout.addWidget(name_header, 1, 0, 1, 1)
        self.name_input = QLineEdit()
        layout.addWidget(self.name_input, 1, 1, 1, 1)

        collar_header = QLabel('Collar')
        collar_header.setFont(QFont("Arial", weight=QFont.Bold))
        layout.addWidget(collar_header, 1, 2, 1, 1)
        self.collar_input = QLineEdit()
        layout.addWidget(self.collar_input, 1, 3, 1, 1)

        position_header = QLabel('Position')
        position_header.setFont(QFont("Arial", weight=QFont.Bold))
        layout.addWidget(position_header, 2, 0, 1, 1)
        self.position_input = QLineEdit()
        layout.addWidget(self.position_input, 2, 1, 1, 1)

        force_header = QLabel('Force')
        force_header.setFont(QFont("Arial", weight=QFont.Bold))
        layout.addWidget(force_header, 2, 2, 1, 1)
        self.force_input = QLineEdit()
        layout.addWidget(self.force_input, 2, 3, 1, 1)

        thumbnail_size_lbl = QLabel('Thumb Size')
        layout.addWidget(thumbnail_size_lbl, 3, 0, 1, 1)
        self.thumbnail_size = QComboBox()
        self.thumbnail_size.addItems(['64', '128', '256', '512'])
        layout.addWidget(self.thumbnail_size, 3, 1, 1, 1)

        folder_img = resource_path('folder_y.png')
        self.save_btn = QPushButton()
        self.save_btn.setIcon(QIcon(folder_img))
        self.save_btn.setIconSize(QSize(15, 15))
        layout.addWidget(self.save_btn, 4, 0, 1, 3, alignment=Qt.AlignLeft)
        self.save_btn.clicked.connect(lambda: self.get_save_dir())

        self.save_location = QLabel('Save Report Location...')
        self.save_location.setFont(QFont("Arial", weight=QFont.Bold))
        layout.addWidget(self.save_location, 4, 1, 1, 1)

        self.okay_btn = QPushButton('OK')
        layout.addWidget(self.okay_btn, 5, 3, 1, 1, alignment=(Qt.AlignRight | Qt.AlignBottom))
        self.okay_btn.clicked.connect(lambda: self.update_values())

        if self.report_type == 'xlsx':
            report_type_img = QPixmap(
                resource_path('xlsx.png')).scaled(35, 35,Qt.KeepAspectRatio, Qt.SmoothTransformation)
        else:
            report_type_img = QPixmap(
                resource_path('html.png')).scaled(35, 35, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        report_type_img_lbl = QLabel()
        report_type_img_lbl.setPixmap(report_type_img)
        layout.addWidget(report_type_img_lbl, 3, 3, 2, 2, alignment=Qt.AlignRight)

        self.gb.setLayout(layout)