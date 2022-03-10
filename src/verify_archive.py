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

from PyQt5.QtCore import pyqtSignal, QThread
import os
import logging
import platform
import zipfile
import tarfile


class VerifyArchiveThread(QThread):
    finishedSignal = pyqtSignal(list)
    progressSignal = pyqtSignal(str)

    def __init__(self, parent, archive, paths, oem):
        QThread.__init__(self, parent)
        self.archive = archive
        self.paths = paths
        self.oem = oem
        self.errors = []

    def close(self):
        self.terminate()

    def run(self):
        archive_members = None

        if zipfile.is_zipfile(self.archive):
            self.progressSignal.emit('Zip archive confirmed, verifying contents...')
            try:
                with zipfile.ZipFile(self.archive, 'r') as zip_obj:
                    archive_members = zip_obj.namelist()
            except Exception as e:
                logging.error(e)
                self.errors.append('Unable to read zip archive, refer to file>log.')

        elif tarfile.is_tarfile(self.archive):
            self.progressSignal.emit('Tar archive confirmed, verifying contents...')
            try:
                with tarfile.open(self.archive, 'r') as tar_obj:
                    archive_members = tar_obj.getnames()
            except Exception as e:
                logging.error(e)
                self.errors.append('Unable to read tar archive, refer to file>log.')

        else:
            self.errors.append('[!] ERROR\n\nUnrecognised file format\nInput must be a zip or tar archive')

        if archive_members:
            for path in self.paths:
                if any(path in archive_member for archive_member in archive_members):
                    pass
                else:
                    self.errors.append('[!] Missing: {}'.format(path))
        else:
            self.errors.append('No files were processed.')

        if self.errors:
            self.errors.append('\nThe file structure of the archive is important. If you are outputting files '
                               'and folders from a vendor, they should be nested to match the file paths listed.')

        self.finishedSignal.emit([self.errors, self.oem, self.archive])