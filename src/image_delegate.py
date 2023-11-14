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

from PyQt5.QtWidgets import QStyledItemDelegate
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import Qt


class ImageDelegate(QStyledItemDelegate):
    '''
    Manages the style and presentation of media displayed in the QTableView.
    '''
    def __init__(self, parent):
        QStyledItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        data = index.data()
        if data:
            image = QImage(data)
            rect = option.rect
            scaledImage = image.scaled(rect.width(), rect.height(),
                                       Qt.KeepAspectRatio, Qt.SmoothTransformation)
            pixmap = QPixmap.fromImage(scaledImage)
            # Set rect at center of item
            rect.translate((rect.width() - pixmap.width()) // 2,
                           (rect.height() - pixmap.height()) // 2)
            rect.setSize(pixmap.size())
            painter.drawPixmap(rect, pixmap)
            # Set the row and column to fit our image inside.
            option.widget.setRowHeight(index.row(), 250)
            option.widget.setColumnWidth(index.row(), 300)