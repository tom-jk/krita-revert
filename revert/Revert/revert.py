from PyQt5.QtWidgets import QMessageBox, QMdiSubWindow, QApplication
from PyQt5.QtCore import Qt, QObject, QTimer, QPoint, pyqtSignal
from functools import partial
from pathlib import Path
from krita import *

import logging
logger = logging.getLogger("tomjk_revert")

from .utils import *

app = Krita.instance()
app_notifier = app.notifier()
app_notifier.setActive(True)

known_windows = []

class RevertExtension(Extension):
    themeChanged = pyqtSignal()

    def __init__(self, parent):
        super().__init__(parent)
        logger.info("extension init.")
        
        #set_extension(self)

    def setup(self):
        logger.info("extension setup.")
        
        plugin_dir = Path(app.getAppDataLocation()) / "pykrita" / "Revert"
        icons_dir = plugin_dir / "icons"
        
        if not plugin_dir.is_dir():
            # do something about it
            pass
        
        self.icons = {}
        for theme in ("light", "dark"):
            icon = lambda name: QIcon(str(icons_dir/f"{theme}_{name}.svg"))
            self.icons[theme] = {
                "revert": icon("document-revert")
            }
        
        self.set_default_icons()
        
        self.theme_name = ""
        self.theme_is_dark = False
        self.use_custom_icons = False
    
    def set_default_icons(self):
        self.icons["default"] = {
            "revert": app.icon("edit-delete")
        }
    
    def get_icon(self,  *args):
        return self._get_icons_internal(self.icons["default" if not self.use_custom_icons else "light" if self.theme_is_dark else "dark"], *args)
    
    def _get_icons_internal(self, sublist, *args):
        if len(args) > 1:
            return self._get_icons_internal(sublist[args[0]], *args[1:])
        else:
            return sublist[args[0]]
    
    def is_theme_dark(self, theme_name=None):
        # TODO: find out more common keywords used in dark theme names, including non-english.
        theme_name = theme_name or self.theme_name
        if theme_name in ("breeze dark", "breeze high contrast", "krita blender", "krita dark", "krita dark orange", "krita darker"):
            return True
        if any(test in theme_name for test in ("dark", "black", "night", "dusk", "sleep")):
            return True
        return False
    
    def _on_theme_change_triggered(self, theme_name):
        self.theme_name = theme_name
        self.update_action_icons()
    
    def set_action_icons(self):
        for win in known_windows:
            win["revert_action"].setIcon(self.get_icon("revert"))
    
    def update_action_icons(self):
        self.use_custom_icons = True#str2bool(readSetting("use_custom_icons"))
        custom_icons_theme = readSetting("custom_icons_theme")
        
        self.theme_is_dark = True if custom_icons_theme == "dark" else False if custom_icons_theme == "light" else self.is_theme_dark()
        self.set_action_icons()
        self.themeChanged.emit()
    
    def createActions(self, window):
        logger.info("extension createActions")
        
        revert_action = window.createAction("tomjk_revert", "Revert", "file")
        #revert_action.setEnabled(False)
        revert_action.triggered.connect(self._on_revert_triggered)
        
        move_partial = partial(self.moveAction, [revert_action], "file_close", window.qwindow())
        call_later = partial(self.finishCreateActions, move_partial, revert_action, window.qwindow())
        QTimer.singleShot(0, call_later)
    
    def finishCreateActions(self, move_partial, revert_action, qwindow):
        move_partial.func(*move_partial.args)
        
        theme_menu_action = next(
            (a for a in app.actions() if a.objectName() == "theme_menu"), None
        )
        
        for theme_action in theme_menu_action.menu().actions():
            theme_action.triggered.connect(lambda checked, tn=theme_action.text().lower(): self._on_theme_change_triggered(tn))
            if theme_action.isChecked():
                self.theme_name = theme_action.text().lower()
        
        self.theme_is_dark = self.is_theme_dark(self.theme_name)
        
        window = next((w for w in app.windows() if w.qwindow() == qwindow), None)
        if not window:
            logger.warn(f"Couldn't find window assocated with qwindow '{qwindow.objectName()}'.")
            return
        known_windows.append({"window":window, "revert_action":revert_action})
        
        self.update_action_icons()
    
    def moveAction(self, actions_to_move, name_of_action_to_insert_before, qwindow):
        menu_bar = qwindow.menuBar()
        file_menu_action = next(
            (a for a in menu_bar.actions() if a.objectName() == "file"), None
        )
        if file_menu_action:
            file_menu = file_menu_action.menu()
            for file_action in file_menu.actions():
                if file_action.objectName() == name_of_action_to_insert_before:
                    for action in actions_to_move:
                        file_menu.removeAction(action)
                        file_menu.insertAction(file_action, action)
                    break

    def _on_window_closed(self, window):
        #print(f"_on_window_closed: {window=} {window.qwindow().objectName()}")
        for i,win in enumerate(known_windows):
            if window == win["window"]:
                del known_windows[i]
                break

    def _on_revert_triggered(self):
        doc = app.activeDocument()
        
        if not doc:
            logger.info("No document to revert.")
            return
        
        if doc.fileName() == "":
            logger.info("Can't revert an unsaved document.")
            return

        msgBox = QMessageBox(
                QMessageBox.Warning,
                "Krita",
                f"Reload <b>'{Path(doc.fileName()).name}'</b> from disk?<br/><br/>"
                "Any unsaved changes will be lost.",
                parent = Application.activeWindow().qwindow()
        )
        btnCancel = msgBox.addButton(QMessageBox.Cancel)
        btnRevert = msgBox.addButton("Revert", QMessageBox.DestructiveRole)
        btnDoInPlace = QCheckBox("Reuse current views", msgBox)
        btnDoInPlace.setChecked(True)
        msgBox.setCheckBox(btnDoInPlace)
        btnRevert.setIcon(Application.icon('warning'))
        msgBox.setDefaultButton(QMessageBox.Cancel)
        msgBox.exec()
        
        if not msgBox.clickedButton() == btnRevert:
            logger.info("Cancelled revert")
            return
            
        if btnDoInPlace.isChecked():
            logger.info("Revert (in-place)")
            self.reverter = Reverter()
            self.reverter.finished.connect(self._on_reverter_finished)
            self.reverter.revert(doc)

        else:
            logger.info("Revert (open in single view)")
    
    def _on_reverter_finished(self):
        logger.info("Revert completed.")
        del self.reverter


class StoredView():
    def __init__(self,
                 isMaximized,
                 window,
                 geometry,
                 windowState,
                 levelOfDetailMode,
                 mirror,
                 preferredCenter,
                 rotation,
                 wrapAroundMode,
                 zoomLevel,
                 HDRExposure,
                 HDRGamma,
                 backgroundColor,
                 brushRotation,
                 brushSize,
                 currentBlendingMode,
                 currentBrushPreset,
                 currentGradient,
                 currentPattern,
                 disablePressure,
                 eraserMode,
                 foregroundColor,
                 globalAlphaLock,
                 paintingFlow,
                 paintingOpacity,
                 patternSize
    ):
        for k,v in vars().items():
            if k == "self":
                continue
            #print(f"self.{k} = {v}")
            setattr(self, k, v)

    def __repr__(self):
        return "\n".join((f"{k}:{v}" for k,v in self.__dict__.items()))


class Reverter(QObject):
    finished = pyqtSignal()
    
    def revert(self, reverted_doc):
        self.reverted_doc = reverted_doc
        
        app.setBatchmode(True)
        
        doc_file_path = self.reverted_doc.fileName()
        self.docs = []
        self.view_subwin_pairs = []
        self.stored_views = []

        logging.debug("")
        logging.debug("PRE-CLOSE GATHER")
        self.gather_view_subwin_pairs()

        for view, subwin in self.view_subwin_pairs:
            canvas = view.canvas()
            doc = view.document()
    
            #if docs.index(doc) != doc_index:
            if doc != self.reverted_doc:
                continue
    
            # can't capture normal geometry of a maximised window.
            # instead, capture window state, then unmaximise, then
            # capture geometry.
            isMaximized = subwin.isMaximized()
            windowState = subwin.windowState()
            levelOfDetailMode = canvas.levelOfDetailMode()
            mirror = canvas.mirror()
            preferredCenter = canvas.preferredCenter()
            rotation = canvas.rotation()
            wrapAroundMode = canvas.wrapAroundMode()
            zoomLevel = canvas.zoomLevel()
    
            logging.debug(f"{subwin.isMaximized()=}")
            if isMaximized:
                subwin.setVisible(False)
                subwin.showNormal()
                subwin.setVisible(True)
    
            self.stored_views.append(StoredView(
                isMaximized,
                view.window(),
                subwin.geometry(),
                windowState,
                levelOfDetailMode,
                mirror,
                preferredCenter,
                rotation,
                wrapAroundMode,
                zoomLevel,
                view.HDRExposure(),
                view.HDRGamma(),
                view.backgroundColor(),
                view.brushRotation(),
                view.brushSize(),
                view.currentBlendingMode(),
                view.currentBrushPreset(),
                view.currentGradient(),
                view.currentPattern(),
                view.disablePressure(),
                view.eraserMode(),
                view.foregroundColor(),
                view.globalAlphaLock(),
                view.paintingFlow(),
                view.paintingOpacity(),
                view.patternSize()
            ))

        reverted_doc.setModified(False)
        
        # ideally, close reverting document before opening its replacement.
        # however, if it is the last doc, Krita will show the welcome screen.
        # this can(?) mess up restoring views. So, keep reverting document
        # around to avoid that.
        # TODO: closing before won't work in the case of multiple windows
        # where, despite there being many docs open in the app, a given
        # window might only have views open on a single doc. Have to
        # fallback to closing after if true of any open window.
        # For now, default to closing after. optimise later.
        self.close_before_revert = False#len(self.docs) > 1
        
        if self.close_before_revert:
            if not self.reverted_doc.close():
                logger.error("couldn't close the document being reverted?")
            self.reverted_doc = None

        new_doc = app.openDocument(doc_file_path)

        for stored_view in self.stored_views:
            view = stored_view.window.addView(new_doc)
            stored_view.new_view = view
        
        if not self.close_before_revert:
            QTimer.singleShot(0, self.midway)
            return

        QTimer.singleShot(0, self.finish)

    def midway(self):
        logger.debug("midway")
        if not self.reverted_doc.close():
            logger.error("couldn't close the document being reverted?")
        self.reverted_doc = None
        
        QTimer.singleShot(0, self.finish)
        
    def finish(self):
        # (called after giving Krita chance to eg. flush out window.views)
        logger.debug("finish")
        logger.debug("")
        logger.debug("POST-ADDED VIEWS GATHER")
        self.gather_view_subwin_pairs()
        
        self.restore_views()
        
        del self.stored_views
        del self.view_subwin_pairs
        
        app.setBatchmode(False)
        
        self.finished.emit()
    
    def gather_view_subwin_pairs(self):
        self.docs = app.documents()
        
        print()
        for i, doc in enumerate(self.docs):
            logger.debug(f"#{i} {doc} '{doc.fileName()}'")
    
        self.view_subwin_pairs.clear()
        for win in app.windows():
            logger.debug(f"window {win.qwindow().objectName()}")
            views = win.views()
        
            subwins = win.qwindow().findChildren(QMdiSubWindow)
            sorted_subwins = sorted(subwins, key=lambda subwin: int(subwin.widget().objectName().lstrip("view_")))
        
            for i, view in enumerate(views):
                doc = view.document()
                doc_index = self.docs.index(doc) if doc in self.docs else "?"
                subwin = sorted_subwins[i]
                logstr = f"{i}: view of doc {doc_index} {doc=} {doc.fileName()} --> subwin titled '{subwin.windowTitle()}' with widget '{subwin.widget().objectName()}' titled '{subwin.widget().windowTitle()}'"
                logger.debug(logstr)
                self.view_subwin_pairs.append((view, subwin))
                #operate_on(view, subwin)

    def restore_views(self):
        for stored_view in self.stored_views:
            view = stored_view.new_view
            subwin = None
            for pair in self.view_subwin_pairs:
                if pair[0] == view:
                    subwin = pair[1]
                    break
            if not subwin:
                logger.error("couldn't find subwin for view.")
                continue
            
            # TODO: I don't know why this works.
            if stored_view.isMaximized:
                subwin.setGeometry(stored_view.geometry)
                subwin.setWindowState(stored_view.windowState)
            else:
                subwin.setWindowState(stored_view.windowState)
                subwin.setGeometry(stored_view.geometry)
        
            canvas = view.canvas()
            canvas.setMirror(stored_view.mirror)
            canvas.setRotation(stored_view.rotation)
            canvas.setZoomLevel(stored_view.zoomLevel)
            canvas.setPreferredCenter(stored_view.preferredCenter)
            canvas.setWrapAroundMode(stored_view.wrapAroundMode)
            canvas.setLevelOfDetailMode(stored_view.levelOfDetailMode)
            
            # TODO: I don't know how these work.
            if False:
                view.setHDRExposure(stored_view.HDRExposure)
                view.setHDRGamma(stored_view.HDRGamma)
                view.setBackGroundColor(stored_view.backgroundColor)
                view.setBrushRotation(stored_view.brushRotation)
                view.setBrushSize(stored_view.brushSize)
                view.setCurrentBlendingMode(stored_view.currentBlendingMode)
                view.setCurrentBrushPreset(stored_view.currentBrushPreset)
                view.setCurrentGradient(stored_view.currentGradient)
                view.setCurrentPattern(stored_view.currentPattern)
                view.setDisablePressure(stored_view.disablePressure)
                view.setEraserMode(stored_view.eraserMode)
                view.setForeGroundColor(stored_view.foregroundColor)
                view.setGlobalAlphaLock(stored_view.globalAlphaLock)
                view.setPaintingFlow(stored_view.paintingFlow)
                view.setPaintingOpacity(stored_view.paintingOpacity)
                view.setPatternSize(stored_view.patternSize)

# And add the extension to Krita's list of extensions:
app.addExtension(RevertExtension(app))
