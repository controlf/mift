

class ProxyModel(QtCore.QSortFilterProxyModel):
    def filterAcceptsRow(self, sourceRow, sourceParent):
        print("Entered filterAcceptsRow function with source row: {}".format(sourceRow))
        idx = self.sourceModel().index(sourceRow, 2, sourceParent)
        value = idx.data()
        if value == "TRUE":
            return True
        if value == "FALSE":
            return False