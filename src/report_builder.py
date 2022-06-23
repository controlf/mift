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
import sys
import json
from os.path import dirname, basename, expanduser, abspath, isfile
from os.path import join as pj
import PIL.Image
import base64
import time
import cv2
import shutil
import filetype
import numpy as np
import pandas as pd
from io import BytesIO
from subprocess import Popen

from src.utils import *


class XLSXReportThread(QThread):
    finishedSignal = pyqtSignal(str)
    progressSignal = pyqtSignal(int)
    statusSignal = pyqtSignal(str)

    def __init__(self, *args, parent=None):
        QThread.__init__(self, parent)
        self.report_name, self.output_fp, self.df, self.save_details, self.has_media, self.temp_dir = args
        self.output_dir = dirname(self.output_fp)
        self.report_files = pj(self.output_dir, 'files')
        os.makedirs(self.report_files, exist_ok=True)

    def run(self):
        if self.has_media:
            self.progressSignal.emit(50)
            self.statusSignal.emit('Copying files to report location...')
            copy_files(self.df['Media'].values.tolist(), self.temp_dir, self.report_files)
            self.progressSignal.emit(100)

        writer = pd.ExcelWriter(self.output_fp, engine='xlsxwriter')
        if 'meta' in self.save_details:
            meta_df = pd.DataFrame(self.save_details['meta'], index=[0])
            meta_df.to_excel(writer, sheet_name='Info')
        self.df.to_excel(writer, sheet_name='data')
        writer.save()
        self.finishedSignal.emit(self.output_dir)


class HTMLReportThread(QThread):
    finishedSignal = pyqtSignal(str)
    progressSignal = pyqtSignal(int)
    statusSignal = pyqtSignal(str)

    def __init__(self, *args, parent=None):
        QThread.__init__(self, parent)
        self.report_name, self.output_fp, self.df, self.save_details, self.has_media, self.temp_dir = args
        self.output_dir = dirname(self.output_fp)
        self.thumbsize = self.save_details['thumbsize']
        self.report_files = pj(self.output_dir, 'files')
        os.makedirs(self.report_files, exist_ok=True)

        # copy our base index.html file to the report output dir
        shutil.copy(resource_path('index.html'), self.output_dir)
        os.rename(pj(self.output_dir, 'index.html'), self.output_fp)
        self.json_data = self.generate_json_object()
        self.apply_meta_data(["casename", "Report", self.report_name])

    def run(self):
        # Optional metadata
        if 'meta' in self.save_details:
            for metaname, metadata in self.save_details['meta'].items():
                self.apply_meta_data(["{}".format(metaname.lower()), "{}".format(metaname.lower().capitalize()), metadata])

        if self.has_media:
            self.apply_column_data("Media Source", [{"name": "Miniature", "displayName": "Thumbnail",
                                                     "filter": 'null', "visibleIndex": 0},
                                                    {"name": "MediaLink", "displayName": "Link",
                                                     "filter": 'null', "visibleIndex": 1}])

            copy_files(self.df['Media'].values.tolist(), self.temp_dir, self.report_files)

        column_data = list()
        for col_count, col in enumerate(self.df.columns.values.tolist(), start=2):
            column_data.append({"name": col, "displayName": col, "filter": 'null', "visibleIndex": col_count})

        self.apply_column_data("File Information", column_data)

        row_data = []
        self.df.reset_index(inplace=True)

        for col in self.df.columns:
            if self.df[col].dtype != 'object':
                try:
                    self.df[col] = self.df[col].astype(str)
                except ValueError:
                    pass

        count = 0
        for index, row in self.df.iterrows():
            row_ = dict()
            if self.has_media:
                row_ = {"id": index,
                        "Miniature": generate_thumbnail(pj(self.output_dir, 'files', basename(row['Media'])), self.thumbsize),
                        "MediaLink": os.path.relpath(pj('files', basename(row['Media']))),
                        "filename": basename(row['Media']),
                        "filepath": row['Media']}
            for k, v in row.items():
                if k not in row_:
                    try:
                        v = v.decode('utf8')
                    except:
                        pass
                    row_.update({k: v})

            row_data.append(row_)

            count += 1
            self.progressSignal.emit(int(count/len(self.df.index)*100))

        self.apply_row_data(row_data)

        self.convert_json_to_javascript(json.dumps(self.json_data, cls=NpEncoder))
        self.finishedSignal.emit(self.output_dir)

    def apply_meta_data(self, meta_list):
        self.json_data['window.caseData']['metaData'][meta_list[0]] = {"title": meta_list[1], "value": meta_list[2]}

    def apply_column_data(self, group_name, column_data):
        # Groups of columns can reside in the below column field.
        # The displayName is how the column will be named in the report.
        # The name is an object name.
        # The filter allows the user to filter the column.
        # visibleIndex is the column number (starts at 0)
        # filter is either 'null' or 'selection'
        # e.g. {"groupName": "Media Source", "columns": [{"name": "Miniature", "displayName": "Thumbnail",
        # "filter": 'null', "visibleIndex": 0}]}
        self.json_data['window.caseData']['columns'].append({"groupName": group_name, "columns": column_data})

    def apply_row_data(self, row_data):
        if isinstance(row_data, dict):
            self.json_data['window.caseData']['rows'].append(row_data)
        elif isinstance(row_data, list):
            for row in row_data:
                self.json_data['window.caseData']['rows'].append(row)

    def generate_json_object(self):
        json_data = dict()
        json_data['window.caseData'] = dict()
        json_data['window.caseData']['metaData'] = dict()
        json_data['window.caseData']['columns'] = list()
        json_data['window.caseData']['rows'] = list()
        json_data['window.caseData']['logo'] = {"width": 320, "height": 65,
                                                "image": (base64.b64encode(open(resource_path('ControlF_R_RGB.png'), 'rb').read()).decode())}
        # casename is a default key that must remain. It is used to display a 'title' for the report
        return json_data    

    def convert_json_to_javascript(self, json_data):
        newdata = (json_data.replace('{"window.caseData":', 'window.caseData =')
                   .replace('True', 'true')
                   .replace('False', 'false')
                   .replace('None', 'null')
                   .replace('True', 'true')
                   .replace('}}}', '},};'))

        data_file = pj(self.output_dir, 'data_{}.js'.format(self.report_name.split('.')[0]))
        f = open(data_file, 'w')
        f.write(newdata)
        f.close()

        with open(self.output_fp, 'r', encoding='utf8') as index_file:
            content = index_file.read()
            content = content.replace('<script src="data.js"></script>',
                                      '<script src="{}"></script>'.format(basename(data_file)))

        with open(self.output_fp, 'w', encoding='utf8') as index_file:
            index_file.write(content)
