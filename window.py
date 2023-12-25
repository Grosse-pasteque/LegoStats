# -*- coding: utf-8 -*-
from __future__ import annotations
import os
import json
import requests
import webbrowser
from typing import Callable
from threading import Thread, Timer
from PyQt5 import QtCore, QtGui, QtWidgets


REQUESTS_HEADER = {"user-agent": "Mozilla/5.0"}

SETS_TABLE_HEADER = ["N°", "Name", "Theme", "Quantity", "Boxes", "Instructions", "Parts", "Weight", "MPrts", "MFgs", "Notes"]
PARTS_TABLE_HEADER = ["N°", "Color", "Quantity"]
FIGS_TABLE_HEADER = ["N°", "Quantity"]

SETS_API = "https://cdn.rebrickable.com/media/sets/%s.jpg"
PARTS_API = "https://img.bricklink.com/ItemImage/PL/%s.png"
FIGS_API = "https://img.bricklink.com/ItemImage/MN/0/%s.png"
WEIGHT_API = "https://www.bricklink.com/v2/catalog/catalogitem.page?S=%s"

BLACK = QtGui.QColor(0, 0, 0)
RED = QtGui.QColor(200, 0, 0)
BLUE = QtGui.QColor(0, 128, 255)
YELLOW = QtGui.QColor(255, 165, 0)
EMPTY = QtGui.QColor(0, 0, 0, 0)

COLOR_GROUPS = ["Solid", "Transparent", "Chrome", "Pearl", "Satin", "Metallic", "Milky", "Glitter", "Speckle", "Modulex"]
COLOR_SHEET = "background-color: %s; border: 0; color: black; font-size: 14pt;"

Handler = Callable[[], None]
RowType = list[int | str]

def load(path: str) -> object:
    with open("LegoStats/" + path + ".json") as file:
        return json.load(file)

def toggle(widget: QtWidgets.QWidget) -> Handler:
    return lambda: widget.show() if widget.isHidden() else widget.hide()


def readFloat(text: str) -> float:
    return float(text.replace("-", "."))


class IntTableWidgetItem(QtWidgets.QTableWidgetItem):
    def __lt__(self, other: IntTableWidgetItem) -> bool:
        return readFloat(self.text()) < readFloat(other.text())


class ColorDialog(QtWidgets.QDialog):
    colors = load("ressources/colors")

    def __init__(self, item):
        super().__init__()
        self.setWindowTitle("Select Color")
        self.resize(400, 300)
        self.item = item
        mainLayout = QtWidgets.QHBoxLayout(self)
        scrollArea = QtWidgets.QScrollArea()
        scrollArea.setWidgetResizable(True)
        scrollArea.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        content = QtWidgets.QWidget()
        verticalLayout = QtWidgets.QVBoxLayout(content)
        verticalLayout.setContentsMargins(0, 0, 0, 0)
        verticalLayout.setSpacing(0)

        last = 0
        for color in self.colors:
            if last != color["group"]:
                title = QtWidgets.QLabel(COLOR_GROUPS[last])
                title.setStyleSheet(
                    "padding-left: 100px;"
                    "padding-top: 40px;"
                    "padding-bottom: 40px;"
                    "font-size: 32pt;"
                    "font-weight: bold;")
                verticalLayout.addWidget(title)
                last += 1

            pushButton = QtWidgets.QPushButton(color["name"])
            pushButton.setStyleSheet(COLOR_SHEET % f"rgb{tuple(color['rgb'])}")
            pushButton.clicked.connect(self.select(color))
            verticalLayout.addWidget(pushButton)

        scrollArea.setWidget(content)
        mainLayout.addWidget(scrollArea)

    def select(self, color: dict):
        def handler():
            self.item.setText(color["name"])
            self.item.setBackground(QtGui.QColor(*color["rgb"]))
            self.accept()
        return handler

    @classmethod
    def get(cls, **kwargs):
        for color in cls.colors:
            if all(color[k] == v for k, v in kwargs.items()):
                return color


class Window(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.selected = True
        self.loadingImage = QtGui.QPixmap("LegoStats/loading.png")

        self.sets = load("ressources/sets")
        self.themes = load("ressources/themes")
        self.mainThemes = load("ressources/main-themes")
        self.originalData = load("ressources/stats")
        self.completeData = self.complete(self.originalData)
        self.originalData = {r[0]: r[1:] for r in self.originalData}
        self.version = tuple(load("proj")["version"])
        self.setWindowTitle("LegoStats - %d.%d.%d" % self.version)
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap("LegoStats/ressources/icon.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.setWindowIcon(icon)
        self.resize(800, 600)
        self.centralwidget = QtWidgets.QWidget(self)

        mainLayout = QtWidgets.QVBoxLayout(self.centralwidget)

        self.setsTable = QtWidgets.QTableWidget(self.centralwidget)
        self.addSearchBar(
            self.centralwidget,
            mainLayout,
            self.addSet,
            self.removeSet,
            self.searchSet
        )

        self.setsTable.itemClicked.connect(lambda item: self.selectSet(item.row()))
        self.setsTable.verticalHeader().setDefaultSectionSize(39)
        self.loadSets()

        mainLayout.addWidget(self.setsTable)
        self.setCentralWidget(self.centralwidget)
        self.loadSidePanel()
        self.loadStatusBar()
        self.updateStatusBar()
        self.loadMenuBar()
        self.togglePanel()

    def numberGetError(self, line: QtWidgets.QLineEdit, number: str):
        p = line.placeholderText()
        line.setPlaceholderText(f"Error: {number!r} not found !")
        Timer(4, line.setPlaceholderText, (p, )).start()

    def addSet(self, line: QtWidgets.QLineEdit):
        row = self.getSet(line)
        line.clear()
        if row is None:
            return
        rowPosition = self.setsTable.rowCount()
        self.setsTable.insertRow(rowPosition)
        self.addSetRow(rowPosition, row)

    def addPart(self, line: QtWidgets.QLineEdit):
        rowPosition = self.partsTable.rowCount()
        self.partsTable.insertRow(rowPosition)
        self.addPartRow(rowPosition, [line.text(), 11, 1])
        line.clear()

    def addFig(self, line: QtWidgets.QLineEdit):
        rowPosition = self.figsTable.rowCount()
        self.figsTable.insertRow(rowPosition)
        self.addFigRow(rowPosition, [line.text(), 1])
        line.clear()

    def removeSet(self, line: QtWidgets.QLineEdit):
        self.deselectSet()
        number = line.text()
        if "-" not in number: number += "-1"
        line.clear()
        for row in range(self.setsTable.rowCount()):
            if self.setsTable.item(row, 0).text() == number:
                self.setsTable.removeRow(row)
                self.originalData.pop(number)
                return
        self.numberGetError(line, number)

    def removePart(self, line: QtWidgets.QLineEdit):
        number = line.text()
        line.clear()
        for row in range(self.partsTable.rowCount()):
            if self.partsTable.item(row, 0).text() == number:
                self.partsTable.removeRow(row)
                return
        self.numberGetError(line, number)

    def removeFig(self, line: QtWidgets.QLineEdit):
        number = line.text()
        line.clear()
        for row in range(self.figsTable.rowCount()):
            if self.figsTable.item(row, 0).text() == number:
                self.figsTable.removeRow(row)
                return
        self.numberGetError(line, number)

    def updateSetItem(
        self,
        x: int,
        value: int | str | None,
        item: QtWidgets.QTableWidgetItem
    ):
        item.setForeground(BLACK)
        item.setBackground(EMPTY)
        if x == 2:
            item.setText(value[1])
            item.setForeground(QtGui.QColor(*value[0]))
        else:
            item.setText(str(value))
        if not value:
            item.setForeground(EMPTY)
        elif x in (4, 5):
            item.setForeground(YELLOW)
        elif x in (8, 9):
            item.setBackground(BLUE)
        elif x == 10:
            item.setBackground(RED)
        return item

    def addSetRow(self, y: int, line: RowType):
        for x, value in enumerate(line):
            self.setsTable.setItem(
                y, x, self.updateSetItem(
                    x, value, (
                        IntTableWidgetItem if x not in (1, 2)
                        else QtWidgets.QTableWidgetItem
                    )(self.setsTable.horizontalHeaderItem(x))
                )
            )

    def addPartRow(self, y: int, line: RowType):
        item = QtWidgets.QTableWidgetItem(line[0], 0)
        item.setTextAlignment(QtCore.Qt.AlignCenter)
        self.partsTable.setItem(y, 0, item)

        color = ColorDialog.get(id=line[1])
        item = QtWidgets.QTableWidgetItem(color["name"], 1)
        item.setTextAlignment(QtCore.Qt.AlignCenter)
        item.setBackground(QtGui.QColor(*color["rgb"]))
        self.partsTable.setItem(y, 1, item)

        item = IntTableWidgetItem(str(line[2]), 1)
        item.setTextAlignment(QtCore.Qt.AlignCenter)
        self.partsTable.setItem(y, 2, item)

    def addFigRow(self, y: int, line: RowType):
        item = QtWidgets.QTableWidgetItem(line[0], 0)
        item.setTextAlignment(QtCore.Qt.AlignCenter)
        self.figsTable.setItem(y, 0, item)
        item = IntTableWidgetItem(str(line[1]), 1)
        item.setTextAlignment(QtCore.Qt.AlignCenter)
        self.figsTable.setItem(y, 1, item)

    def getSet(self, line: QtWidgets.QLineEdit):
        number = line.text()
        if "-" not in number: number += "-1"
        try:
            name, _, thm, prts = self.sets[number]
        except KeyError:
            return self.numberGetError(line, number)
        wgh = None
        try:
            req = requests.get(WEIGHT_API % number, headers=REQUESTS_HEADER)
            if req.status_code in (200, 418):
                content = req.text
                i = content.index("-info\">") + 7
                dat = content[i:i + 6].split("g")[0]
                if dat[0] != "?":
                    wgh = int(dat.split(".")[0])
        except ConnectionError:
            pass
        self.originalData[number] = [1, 0, 0, wgh, [], [], ""]
        return [number, name, self.getTheme(thm), 1, 0, 0, prts, wgh, 0, 0, 0]

    def searchSet(self, line: QtWidgets.QLineEdit):
        content = line.text().strip()
        for row in range(self.setsTable.rowCount()):
            # Only N°, Name, Thm
            if content:
                org = self.originalData[self.setsTable.item(row, 0).text()]
                if any(content in r[0] for r in org[4] + org[5]) or any(
                    content in self.setsTable.item(row, column).text()
                    for column in range(3)
                ):
                    self.setsTable.showRow(row)
                else:
                    self.setsTable.hideRow(row)
            else:
                self.setsTable.showRow(row)

    def search(self, table: QtWidgets.QTableWidget):
        def handler(line: QtWidgets.QLineEdit):
            content = line.text().strip()
            for row in range(table.rowCount()):
                if not content or content in table.item(row, 0).text():
                    table.showRow(row)
                else:
                    table.hideRow(row)
        return handler

    def deselectSet(self):
        # update missing parts/figs and notes
        ref = self.originalData[self.selected]
        tp, tf = self.partsTable.item, self.figsTable.item
        ref[4] = [
            (
                tp(row, 0).text(),
                ColorDialog.get(name=tp(row, 1).text())["id"],
                int(tp(row, 2).text())
            )
            for row in range(self.partsTable.rowCount())
        ]
        self.partsTable.setRowCount(0)
        ref[5] = [
            (
                tf(row, 0).text(),
                int(tf(row, 1).text())
            )
            for row in range(self.figsTable.rowCount())
        ]
        self.figsTable.setRowCount(0)
        ref[6] = self.notesArea.toPlainText()
        self.notesArea.clear()

        # table updates
        for lasty in range(self.setsTable.rowCount()):
            if self.setsTable.item(lasty, 0).text() == self.selected:
                break
        if (item := self.setsTable.item(lasty, 4)).text() != "0":
            item.setForeground(YELLOW)
        if (item := self.setsTable.item(lasty, 5)).text() != "0":
            item.setForeground(YELLOW)
        self.updateSetItem(8, sum(x[2] for x in ref[4]), self.setsTable.item(lasty, 8))
        self.updateSetItem(9, sum(x[1] for x in ref[5]), self.setsTable.item(lasty, 9))
        self.updateSetItem(10, len(ref[6].splitlines()), self.setsTable.item(lasty, 10))
        self.togglePanel()

    def selectSet(self, y: int):
        if self.selected:
            self.deselectSet()
        self.selected = self.setsTable.item(y, 0).text()
        try:
            date = str(self.sets.get(self.selected)[1])
        except:
            date = "-"
        self.labelSetNumber.setText(self.selected)
        self.labelSetDate.setText(date)
        path = "LegoStats/assets/%s.jpg" % self.selected
        if os.path.exists(path):
            self.setImage.setPixmap(QtGui.QPixmap(path).scaledToHeight(300))
        else:
            self.setImage.setPixmap(self.loadingImage)
            Thread(target=self.downloadImage, args=(self.selected,)).start()
        for n in self.originalData:
            if n == self.selected:
                break
        row = self.originalData[n]
        self.dockSet.show()
        self.loadParts(row[4])
        self.loadFigs(row[5])
        self.loadNotes(row[6])

    def downloadImage(self, number: str):
        path = "LegoStats/assets/%s.jpg" % number
        try:
            req = requests.get(SETS_API % number, headers=REQUESTS_HEADER)
        except ConnectionError:
            return
        if req.status_code not in (200, 418):
            return
        with open(path, "wb") as f:
            f.write(req.content)
        self.setImage.setPixmap(QtGui.QPixmap(path).scaledToHeight(300))

    def addSearchBar(
        self,
        parent: QtWidgets.QWidget,
        layout: QtWidgets.QLayout,
        addHandler: Handler,
        removeHandler: Handler,
        searchHandler: Handler
    ):
        horizontalLayout = QtWidgets.QHBoxLayout()
        lineEditSearch = QtWidgets.QLineEdit(parent)
        lineEditSearch.setPlaceholderText("Search (Press Enter) / Add / Remove")
        lineEditSearch.returnPressed.connect(lambda: searchHandler(lineEditSearch))

        pushButtonAdd = QtWidgets.QPushButton(parent)
        pushButtonAdd.setAutoFillBackground(False)
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap("LegoStats/ressources/list-add.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        pushButtonAdd.setIcon(icon)
        pushButtonAdd.setIconSize(QtCore.QSize(30, 30))
        pushButtonAdd.setStyleSheet(
            "background-color: transparent;"
            "border: 0px;")

        pushButtonRemove = QtWidgets.QPushButton(parent)
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap("LegoStats/ressources/list-remove.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        pushButtonRemove.setIcon(icon)
        pushButtonRemove.setIconSize(QtCore.QSize(30, 30))
        pushButtonRemove.setStyleSheet(
            "background-color: transparent;"
            "border: 0px;")

        pushButtonAdd.clicked.connect(lambda: addHandler(lineEditSearch))
        pushButtonRemove.clicked.connect(lambda: removeHandler(lineEditSearch))

        horizontalLayout.addWidget(lineEditSearch)
        horizontalLayout.addWidget(pushButtonAdd)
        horizontalLayout.addWidget(pushButtonRemove)
        layout.addLayout(horizontalLayout)

    def loadSidePanel(self):
        dockArea = QtCore.Qt.DockWidgetArea(2)

        self.dockSet = QtWidgets.QDockWidget(self)
        self.dockSet.setWindowTitle("Set Infos")
        dockWidgetContents = QtWidgets.QWidget()
        verticalLayout = QtWidgets.QVBoxLayout(dockWidgetContents)

        header = QtWidgets.QWidget()
        header.setFixedHeight(30)
        headerLayout = QtWidgets.QHBoxLayout(header)

        self.labelSetNumber = QtWidgets.QLabel(dockWidgetContents)
        self.labelSetNumber.setStyleSheet(
            "font-size: 16pt;"
            "font-weight: bold;")

        self.labelSetDate = QtWidgets.QLabel(dockWidgetContents)
        self.labelSetDate.setStyleSheet(
            "font-size: 16pt;"
            "font-weight: bold;"
            "color: blue;")
        self.labelSetDate.setAlignment(
            QtCore.Qt.AlignRight
            | QtCore.Qt.AlignTrailing
            | QtCore.Qt.AlignVCenter)

        headerLayout.addWidget(self.labelSetNumber)
        headerLayout.addWidget(self.labelSetDate)

        self.setImage = QtWidgets.QLabel(dockWidgetContents)

        verticalLayout.addWidget(header)
        verticalLayout.addWidget(self.setImage)

        # TODO: fix on Windows the header gets cut so weird :|
        # verticalLayout.addItem(QtWidgets.QSpacerItem(1, 1,
        #     QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding))

        self.dockSet.setWidget(dockWidgetContents)
        self.addDockWidget(dockArea, self.dockSet)

        self.dockParts = QtWidgets.QDockWidget(self)
        self.dockParts.setWindowTitle("Missing Parts")
        dockWidgetContents = QtWidgets.QWidget()
        verticalLayout = QtWidgets.QVBoxLayout(dockWidgetContents)

        self.partsTable = QtWidgets.QTableWidget(dockWidgetContents)
        self.addSearchBar(
            dockWidgetContents,
            verticalLayout,
            self.addPart,
            self.removePart,
            self.search(self.partsTable)
        )

        self.partsTable.setColumnCount(len(PARTS_TABLE_HEADER))
        self.partsTable.setSortingEnabled(True)
        self.partsTable.itemClicked.connect(
            lambda item: (
                item.column() == 0 and webbrowser.open(PARTS_API % item.text())) or (
                item.column() == 1 and ColorDialog(item).exec_())
        )
        self.partsTable.setStyleSheet(
            "font-size: 14pt;"
            "background-color: white;"
            "color: black;")

        header = self.partsTable.horizontalHeader()
        for i, name in enumerate(PARTS_TABLE_HEADER):
            item = QtWidgets.QTableWidgetItem(name)
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.partsTable.setHorizontalHeaderItem(i, item)
            header.setSectionResizeMode(i, QtWidgets.QHeaderView.Stretch)

        verticalLayout.addWidget(self.partsTable)
        self.dockParts.setWidget(dockWidgetContents)
        self.addDockWidget(dockArea, self.dockParts)

        self.dockFigs = QtWidgets.QDockWidget(self)
        self.dockFigs.setWindowTitle("Missing Figs")
        dockWidgetContents = QtWidgets.QWidget()
        verticalLayout = QtWidgets.QVBoxLayout(dockWidgetContents)

        self.figsTable = QtWidgets.QTableWidget(dockWidgetContents)
        self.addSearchBar(
            dockWidgetContents,
            verticalLayout,
            self.addFig,
            self.removeFig,
            self.search(self.figsTable)
        )

        self.figsTable.setColumnCount(len(FIGS_TABLE_HEADER))
        self.figsTable.setSortingEnabled(True)
        self.figsTable.itemClicked.connect(
            lambda item: item.column() == 0 and webbrowser.open(FIGS_API % item.text()))
        self.figsTable.setStyleSheet(
            "font-size: 14pt;"
            "background-color: white;"
            "color: black;")

        header = self.figsTable.horizontalHeader()
        for i, name in enumerate(FIGS_TABLE_HEADER):
            item = QtWidgets.QTableWidgetItem(name)
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.figsTable.setHorizontalHeaderItem(i, item)
            header.setSectionResizeMode(i, QtWidgets.QHeaderView.Stretch)

        verticalLayout.addWidget(self.figsTable)
        self.dockFigs.setWidget(dockWidgetContents)
        self.addDockWidget(dockArea, self.dockFigs)

        self.dockNotes = QtWidgets.QDockWidget(self)
        self.dockNotes.setWindowTitle("Notes")
        dockWidgetContents = QtWidgets.QWidget()
        verticalLayout = QtWidgets.QVBoxLayout(dockWidgetContents)

        self.notesArea = QtWidgets.QPlainTextEdit(dockWidgetContents)
        self.notesArea.setStyleSheet(
            "font-size: 14pt;"
            "background-color: white;"
            "color: black;")

        verticalLayout.addWidget(self.notesArea)
        self.dockNotes.setWidget(dockWidgetContents)
        self.addDockWidget(dockArea, self.dockNotes)

    def loadStatusBar(self):
        statusBar = self.statusBar()
        statusBar.setStyleSheet("QLabel { font-size: 12pt; }")
        # TODO: Use the the status bar to display error messages
        # statusBar.showMessage("Message")
        self.setsCount = QtWidgets.QLabel()
        self.partsCount = QtWidgets.QLabel()
        self.weightCount = QtWidgets.QLabel()
        self.boxesCount = QtWidgets.QLabel()
        self.noticesCount = QtWidgets.QLabel()
        self.themesCount = QtWidgets.QLabel()
        self.missingPartsCount = QtWidgets.QLabel()
        self.missingFigsCount = QtWidgets.QLabel()
        statusBar.addPermanentWidget(self.setsCount)
        statusBar.addPermanentWidget(self.newLineWidget())
        statusBar.addPermanentWidget(self.partsCount)
        statusBar.addPermanentWidget(self.newLineWidget())
        statusBar.addPermanentWidget(self.weightCount)
        statusBar.addPermanentWidget(self.newLineWidget())
        statusBar.addPermanentWidget(self.boxesCount)
        statusBar.addPermanentWidget(self.newLineWidget())
        statusBar.addPermanentWidget(self.noticesCount)
        statusBar.addPermanentWidget(self.newLineWidget())
        statusBar.addPermanentWidget(self.themesCount)
        statusBar.addPermanentWidget(self.newLineWidget())
        statusBar.addPermanentWidget(self.missingPartsCount)
        statusBar.addPermanentWidget(self.newLineWidget())
        statusBar.addPermanentWidget(self.missingFigsCount)

    def loadSets(self):
        self.setsTable.setColumnCount(len(SETS_TABLE_HEADER))
        self.setsTable.setRowCount(len(self.completeData))
        self.setsTable.setSortingEnabled(True)
        self.setsTable.setStyleSheet(
            "font-size: 14pt;"
            "background-color: white;"
            "color: black;")

        header = self.setsTable.horizontalHeader()
        for i, name in enumerate(SETS_TABLE_HEADER):
            item = QtWidgets.QTableWidgetItem(name)
            if i not in (1, 2, 6, 7):
                item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.setsTable.setHorizontalHeaderItem(i, item)
            if i in (1, 2):
                header.setSectionResizeMode(i, QtWidgets.QHeaderView.Stretch)
            else:
                header.setSectionResizeMode(i, QtWidgets.QHeaderView.ResizeToContents)
        for y, line in enumerate(self.completeData):
            self.addSetRow(y, line)

    def loadMenuBar(self):
        menuBar = QtWidgets.QMenuBar(self)
        menuFile = QtWidgets.QMenu("File", menuBar)
        menuToggle = QtWidgets.QMenu("Toggle", menuBar)
        actionNew = QtWidgets.QAction("New", self)
        actionOpen = QtWidgets.QAction("Open", self)
        actionSave = QtWidgets.QAction("Save", self)
        actionSaveAs = QtWidgets.QAction("Save As", self)
        actionSetInfos = QtWidgets.QAction("Set Infos", self)
        actionMissingParts = QtWidgets.QAction("Missing Parts", self)
        actionMissingFigs = QtWidgets.QAction("Missing Figs", self)
        actionNotes = QtWidgets.QAction("Notes", self)
        menuFile.addAction(actionNew)
        menuFile.addAction(actionOpen)
        menuFile.addSeparator()
        menuFile.addAction(actionSave)
        menuFile.addAction(actionSaveAs)
        menuToggle.addAction(actionSetInfos)
        menuToggle.addAction(actionMissingParts)
        menuToggle.addAction(actionMissingFigs)
        menuToggle.addAction(actionNotes)
        menuBar.addAction(menuFile.menuAction())
        menuBar.addAction(menuToggle.menuAction())

        actionNew.triggered.connect(lambda: print("NEW"))
        actionNew.setShortcut("Ctrl+N")

        actionOpen.triggered.connect(lambda: print("OPEN"))
        actionOpen.setShortcut("Ctrl+O")

        actionSave.triggered.connect(self.save)
        actionSave.setShortcut("Ctrl+S")

        actionSaveAs.triggered.connect(lambda: print("SAVE AS"))
        actionSaveAs.setShortcut("Ctrl+Shift+S")

        actionSetInfos.triggered.connect(toggle(self.dockSet))
        actionMissingParts.triggered.connect(toggle(self.dockParts))
        actionMissingFigs.triggered.connect(toggle(self.dockFigs))
        actionNotes.triggered.connect(toggle(self.dockNotes))
        self.setMenuBar(menuBar)

    def loadParts(self, parts: list[list[str, int, int]]):
        if parts:
            self.partsTable.setRowCount(len(parts))
            for y, line in enumerate(parts):
                self.addPartRow(y, line)
        self.dockParts.show()

    def loadFigs(self, figs: list[list[str, int]]):
        if figs:
            self.figsTable.setRowCount(len(figs))
            for y, line in enumerate(figs):
                self.addFigRow(y, line)
        self.dockFigs.show()

    def loadNotes(self, notes: str):
        self.notesArea.setPlainText(notes)
        self.dockNotes.show()

    def updateStatusBar(self):
        tbxs, tins, tprts, n, twgh, nwgh, thms, tmprts, tmfigs = 0, 0, 0, 0, 0, 0, set(), 0, 0
        for num, _, (_, thm), qty, bxs, ins, prts, wgh, mprts, mfigs, _ in self.completeData:
            tbxs += bxs
            tins += ins
            tprts += prts * qty
            n += qty
            tmprts += mprts
            tmfigs += mfigs
            thms.add(thm)
            if wgh:
                twgh += wgh * qty
                nwgh += qty
        self.setsCount.setText(f"Sets: {n} ({len(self.completeData)})")
        self.partsCount.setText(f"Parts: {tprts - tmprts}")
        self.weightCount.setText(f"Weight: {round(twgh / 1000)}kg")
        self.boxesCount.setText(f"Boxes: {tbxs}")
        self.noticesCount.setText(f"Instructions: {tins}")
        self.themesCount.setText(f"Themes: {len(thms)}")
        self.missingPartsCount.setText(f"Missing Parts: {tmprts}")
        self.missingFigsCount.setText(f"Missing Figs: {tmfigs}")

    def togglePanel(self):
        if self.selected:
            self.dockSet.hide()
            self.dockParts.hide()
            self.dockFigs.hide()
            self.dockNotes.hide()
            self.selected = None
        else:
            self.dockSet.show()
            self.dockParts.show()
            self.dockFigs.show()
            self.dockNotes.show()

    def newLineWidget(self):
        line = QtWidgets.QFrame(self.centralwidget)
        line.setFrameShape(QtWidgets.QFrame.VLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)
        return line

    def getTheme(self, thm: int):
        thm = str(thm)
        ns = []
        while True:
            if thm in self.mainThemes:
                n, c = self.mainThemes[thm]
                ns.insert(0, n)
                return c, ": ".join(ns)
            else:
                n, thm = self.themes[thm]
                ns.insert(0, n)

    def complete(self, data: list):
        thms = {}
        for num, qty, bx, ins, wgh, mprts, mfigs, nts in data:
            th = self.getTheme(self.sets[num][2])
            thms.setdefault(th[1], []).append([
                num,
                self.sets[num][0],
                th,
                qty,
                bx,
                ins,
                self.sets[num][3],
                wgh or "",
                sum(x[2] for x in mprts),
                sum(x[1] for x in mfigs),
                len(nts.splitlines())
            ])
        data = []
        for _, rows in sorted(thms.items(), key=lambda x: x[0]):
            data += sorted(rows, key=lambda x: readFloat(x[0]))
        return data

    def save(self):
        if self.selected:
            self.deselectSet()
        item = self.setsTable.item
        for y in range(self.setsTable.rowCount()):
            ref = self.originalData[item(y, 0).text()]
            ref[0] = int(item(y, 3).text())
            ref[1] = int(item(y, 4).text())
            ref[2] = int(item(y, 5).text())
            ref[3] = int(item(y, 7).text() or 0) or None
        with open("LegoStats/ressources/stats.json", "w") as f:
            json.dump([[k, *v] for k, v in self.originalData.items()], f)

    def closeEvent(self, event):
        self.save()
        super().closeEvent(event)
