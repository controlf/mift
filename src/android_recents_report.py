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


from PyQt5.QtCore import *
import os
import logging
from os.path import join as pj
from os.path import *
from datetime import datetime
from io import BytesIO
import pandas as pd
import shutil
import xml.etree.ElementTree as ET

from src import extract_archive, ktx_2_png
from src.utils import resource_path, decode_bplist, build_dataframe

# timedelta is cocoa UTC epoch - unix UTC epoch
delta = datetime(2001, 1, 1) - datetime(1970, 1, 1)


class MakeRecentsReport(QThread):
    finishedSignal = pyqtSignal(object)
    progressSignal = pyqtSignal(list)

    def __init__(self, *args):
        QThread.__init__(self, args[0])
        self.tab_widget, self.maingui, self.archive, self.save_dir = args

    def get_metadata(self):
        # parse each xml in the 'recent_tasks' directory and joins the associated snapshot with it
        recents_dict = dict()
        rt_xmls = [pj(self.save_dir, f) for f in os.listdir(self.save_dir) if f.endswith('_task.xml')]

        for count, rt in enumerate(rt_xmls):
            tree = ET.parse(rt)
            root = tree.getroot()

            task_dict = {
                'task_id': '', 
                'host_process_name': '', 
                'user_id': '', 
                'real_activity': '',
                'last_time_moved': '', 
                'effective_uid': '', 
                'calling_package': ''
                }

            for task, value in task_dict.items():
                task_dict[task] = root.attrib.get(task)

            if isfile(pj(self.save_dir, '{}.jpg'.format(task_dict['task_id']))):
                task_dict['media'] = pj(self.save_dir, '{}.jpg'.format(task_dict['task_id']))

            recents_dict[task_dict['task_id']] = task_dict
            self.progressSignal.emit([count/len(rt_xmls)*100, 'Parsed {}'.format(basename(rt))])

        return recents_dict

    def build_df(self, recents_dict):
        df = pd.DataFrame(recents_dict).T.reset_index()
        df.rename(columns={
            'host_process_name': 'Process Name', 
            'task_id': 'Task ID',
            'user_id': 'User ID', 
            'real_activity': 'Real Activity',
            'last_time_moved': 'Last Time Moved', 
            'effective_uid': 'UID',
            'calling_package': 'Calling Package'
            }, inplace=True)
        df = df[['media', 'Process Name', 'Task ID', 'Last Time Moved',
                 'Calling Package', 'Real Activity', 'User ID', 'UID']]
        df = df.fillna('')
        return df

    def run(self):
        extract_instance = extract_archive.ExtractArchive(self, ['system_ce'], self.save_dir, self.archive)
        out = extract_instance.extract()
        self.progressSignal.emit([100, out])
        recents_dict = self.get_metadata()
        self.progressSignal.emit([100, '{} recents recovered!'.format(len(recents_dict.keys()))])
        df = self.build_df(recents_dict)
        self.finishedSignal.emit(df)
