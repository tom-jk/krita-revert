from PyQt5.QtWidgets import QMdiSubWindow
from PyQt5.QtCore import QObject, QTimer, pyqtSignal
from krita import *

import logging
logger = logging.getLogger("tomjk_revert")

app = Krita.instance()

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
