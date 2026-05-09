from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QTimer, pyqtSignal
from functools import partial
from pathlib import Path
from krita import *

import logging
logger = logging.getLogger("tomjk_revert")

from .utils import *
from .reverter import *

app = Krita.instance()
app_notifier = app.notifier()
app_notifier.setActive(True)

known_windows = []

class RevertExtension(Extension):
    themeChanged = pyqtSignal()
    
    def __init__(self, parent):
        super().__init__(parent)
        logger.info("extension init.")

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
        win = app.activeWindow()
        
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
                parent = win.qwindow()
        )
        btnCancel = msgBox.addButton(QMessageBox.Cancel)
        btnRevert = msgBox.addButton("Revert", QMessageBox.DestructiveRole)
        btnDoInPlace = QCheckBox("Reuse current views", msgBox)
        btnDoInPlace.setChecked(True)
        msgBox.setCheckBox(btnDoInPlace)
        btnRevert.setIcon(app.icon('warning'))
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
            filename = doc.fileName()
            app.setBatchmode(True)
            doc.setModified(False)
            doc.close()
            doc.waitForDone()
            doc = app.openDocument(filename)
            view = win.addView(doc)
            app.setBatchmode(False)
    
    def _on_reverter_finished(self):
        logger.info("Revert completed.")
        del self.reverter

# And add the extension to Krita's list of extensions:
if len(Application.windows()) > 0:
    logger.warning("Activated mid-Krita session. Please restart Krita.")
else:
    app.addExtension(RevertExtension(app))
