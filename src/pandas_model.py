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

from PyQt5.QtCore import Qt, QAbstractTableModel, QVariant, QSize
import numpy as np
import pandas as pd


class PandasModel(QAbstractTableModel):
    def __init__(self, df, parent=None):
        QAbstractTableModel.__init__(self, parent)
        self._df = np.array(df.values)
        self.original_df = df.copy()

        self._cols = df.columns
        self.r, self.c = np.shape(self._df)

    def rowCount(self, parent=None):
        return self.r

    def columnCount(self, parent=None):
        return self.c

    def data(self, index, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return QVariant()

        if not index.isValid():
            return QVariant()

        return QVariant(str(self._df[index.row(), index.column()]))

    def setData(self, index, value, role):
        row = self._df[index.row()]
        col = self._df[index.column()]

        if hasattr(value, 'toPyObject'):
            value = value.toPyObject()
        else:
            dtype = self._df.dtype
            if dtype != object:
                value = None if value == '' else dtype.type(value)
        table_row = row[0]-1
        table_col = col[0]-1
        self._df[table_row, table_col] = value
        if role == Qt.EditRole and self.reason == 'Read':
            column_name = self.original_df.columns[table_col]
            self.original_df.loc[table_row, column_name] = value

            my_df = pd.DataFrame(self._df)
            my_df.columns = self.original_df.columns
            self.conSig.dataChanged.emit(table_row, table_col, my_df)
        return True

    def headerData(self, p_int, orientation, role):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return self._cols[p_int]
            elif orientation == Qt.Vertical:
                return p_int
        return None