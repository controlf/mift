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

from PyQt5.QtWidgets import QWidget
import os
from os.path import join as pj
from os.path import basename, abspath
import zipfile
import tarfile
import logging

from src.utils import resource_path


class ExtractArchive(QWidget):
    def __init__(self, parent, files_to_extract, save_dir, archive, maintain_dir_structure=False, key_dir=None):
        super().__init__(parent=None)
        self.files_to_extract = files_to_extract
        self.save_dir = save_dir
        self.archive = archive
        self.maintain_dir_structure = maintain_dir_structure
        self.key_dir = key_dir

    def extract(self):
        os.makedirs(self.save_dir, exist_ok=True)
        if zipfile.is_zipfile(self.archive):
            with zipfile.ZipFile(self.archive, 'r') as zip_obj:
                archive_members = zip_obj.namelist()
                if not self.maintain_dir_structure:
                    for file_member in self.files_to_extract:  # get the index of the file in the archive members
                        file_idxs = [i for i, archive_member in enumerate(archive_members)
                                     if file_member in archive_member]
                        if file_idxs:
                            for idx in file_idxs:
                                if len(basename(archive_members[idx])) != 0:
                                    file = pj(self.save_dir, '{}'.format(basename(archive_members[idx])))
                                    with open(file, 'wb') as file_out:
                                        zip_fmem = zip_obj.read(archive_members[idx])
                                        file_out.write(zip_fmem)
                else:
                    for archive_member in archive_members:
                        if self.key_dir in archive_member:
                            if archive_member.endswith('/'):
                                os.makedirs(self.save_dir+'/'+archive_member, exist_ok=True)
                            else:
                                file = abspath(self.save_dir+'/{}'.format(archive_member))
                                try:
                                    with open(file, 'wb') as file_out:
                                        zip_fmem = zip_obj.read(archive_member)
                                        file_out.write(zip_fmem)
                                except:
                                    logging.error('cant copy file: {}'.format(file))

        else:
            if not self.maintain_dir_structure:
                with tarfile.open(self.archive, 'r') as tar_obj:
                    archive_members = tar_obj.getnames()
                    for file_member in self.files_to_extract:  # get the index of the file in the archive members
                        file_idxs = [i for i, archive_member in enumerate(archive_members)
                                     if file_member in archive_member]
                        if file_idxs:
                            for idx in file_idxs:
                                if len(basename(archive_members[idx])) != 0:
                                    file = pj(self.save_dir, '{}'.format(basename(archive_members[idx])))
                                    with open(file, 'wb') as file_out:
                                        tar_fmem = tar_obj.extractfile(archive_members[idx])
                                        file_out.write(tar_fmem.read())

            else:
                with tarfile.open(self.archive, 'r') as tar_obj:
                    for member in tar_obj:
                        if self.key_dir in member.name:
                            if member.isdir():
                                os.makedirs(self.save_dir+'/'+member.name.replace(':', ''), exist_ok=True)
                            else:
                                file = self.save_dir+'/{}'.format(member.name.replace(':', ''))
                                try:
                                    with open(file, 'wb') as file_out:
                                        tar_fmem = tar_obj.extractfile(member)
                                        file_out.write(tar_fmem.read())
                                except:
                                    logging.error('cant copy file: {}'.format(file))

        return 'Archive Processed'