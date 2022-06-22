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
from PyQt5.QtGui import QBrush, QPainter


class ImageDelegate(QStyledItemDelegate):
    # Image delegate styles a column by brushing a list of images
    def __init__(self, icons, parent=None):
        super(ImageDelegate, self).__init__(parent)
        self._icons = icons

    def fetch_icon(self, index):
        icon = self._icons[index.row() % len(self._icons)]
        return icon

    def paint(self, painter, option, index):
        pixmap = self.fetch_icon(index)
        #option.widget.setRowHeight(index.row(), pixmap.height())
        # Set the row and column to fit our image inside.
        option.widget.setRowHeight(index.row(), 250)
        option.widget.setColumnWidth(index.row(), 300)
        brush = QBrush(pixmap)
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setBrush(brush)
        painter.setBrushOrigin(option.rect.topLeft())
        painter.drawRoundedRect(option.rect.x(), option.rect.y(), pixmap.width(), pixmap.height(), 20, 20)
        # Important to restore the painter after use, just like a real paint brush!
        painter.restore()