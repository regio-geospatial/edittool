# -*- coding: utf-8 -*-

import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor, QCursor, QIcon
from qgis.PyQt.QtWidgets import QApplication, QMenu

try:
    from qgis.PyQt.QtGui import QAction  # Qt6
except ImportError:
    from qgis.PyQt.QtWidgets import QAction  # Qt5

from qgis.core import (
    QgsFeatureRequest,
    QgsGeometry,
    QgsMapLayer,
    QgsPointXY,
    QgsWkbTypes,
)
from qgis.gui import QgsMapToolIdentify, QgsRubberBand

# Qt enum compatibility
try:
    _ArrowCursor = Qt.CursorShape.ArrowCursor
    _LeftButton = Qt.MouseButton.LeftButton
    _RightButton = Qt.MouseButton.RightButton
    _ControlModifier = Qt.KeyboardModifier.ControlModifier
except AttributeError:
    _ArrowCursor = Qt.ArrowCursor
    _LeftButton = Qt.LeftButton
    _RightButton = Qt.RightButton
    _ControlModifier = Qt.ControlModifier

# QGIS enum compatibility
try:
    _PolygonGeometry = QgsWkbTypes.GeometryType.Polygon
except AttributeError:
    _PolygonGeometry = QgsWkbTypes.PolygonGeometry

try:
    _VectorLayerType = QgsMapLayer.LayerType.VectorLayer
except AttributeError:
    _VectorLayerType = QgsMapLayer.VectorLayer

try:
    _IdentifyLayerSelection = QgsMapToolIdentify.Type.LayerSelection
    _IdentifyVectorLayer = QgsMapToolIdentify.Type.VectorLayer
except AttributeError:
    _IdentifyLayerSelection = QgsMapToolIdentify.LayerSelection
    _IdentifyVectorLayer = QgsMapToolIdentify.VectorLayer

try:
    _ExactIntersect = QgsFeatureRequest.Flag.ExactIntersect
except AttributeError:
    _ExactIntersect = QgsFeatureRequest.ExactIntersect


class EditTool:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        self.action = QAction(
            QIcon(os.path.join(self.plugin_dir, "icons", "editTool.png")),
            "Edit Tool",
            self.iface.mainWindow(),
        )
        self.action.setWhatsThis("Start editing selected feature")
        self.action.setCheckable(True)
        self.action.triggered.connect(self.run)

        self.iface.digitizeToolBar().addAction(self.action)
        self.iface.addPluginToMenu("&Edit Tool", self.action)

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        self.iface.removePluginMenu("&Edit Tool", self.action)
        self.iface.digitizeToolBar().removeAction(self.action)

    def run(self):
        """Run method that performs all the real work."""
        self.action.setChecked(True)

        cursor = QCursor()
        cursor.setShape(_ArrowCursor)
        self.iface.mainWindow().centralWidget().setCursor(cursor)

        self.mapTool = GeometryInfoMapTool(self.iface)
        self.mapTool.setAction(self.action)
        self.iface.mapCanvas().setMapTool(self.mapTool)


class GeometryInfoMapTool(QgsMapToolIdentify):
    def __init__(self, iface):
        super().__init__(iface.mapCanvas())
        self.iface = iface

        self.cursor = QCursor()
        self.cursor.setShape(_ArrowCursor)
        self.setCursor(self.cursor)

        self.plugin_dir = os.path.dirname(__file__)
        self.rb = None
        self.x0 = None
        self.y0 = None
        self._move = False

    def _identify_at_event(self, event):
        """Helper: identify using pixel coordinates from QgsMapMouseEvent."""
        p = event.originalPixelPoint()  # QPoint
        return self.identify(
            p.x(),
            p.y(),
            _IdentifyLayerSelection,
            _IdentifyVectorLayer,
        )

    def _cleanup_rb(self):
        """Remove any active rubber band from the canvas."""
        if self.rb:
            self.iface.mapCanvas().scene().removeItem(self.rb)
            self.rb = None
        self._move = False

    def deactivate(self):
        """Clean up rubber band when the tool is deactivated."""
        self._cleanup_rb()
        super().deactivate()

    def canvasDoubleClickEvent(self, event):
        found_features = self._identify_at_event(event)
        if found_features:
            layer = found_features[0].mLayer
            feature = found_features[0].mFeature
            layer.select(feature.id())
            self.iface.setActiveLayer(layer)
            self.iface.actionVertexTool().trigger()

    def canvasPressEvent(self, event):
        if event.button() == _LeftButton:
            self.rb = QgsRubberBand(self.iface.mapCanvas(), _PolygonGeometry)
            self.rb.setFillColor(QColor(255, 255, 255, 20))
            self.rb.setColor(QColor(0, 0, 0, 50))

            # Use map coords directly from QgsMapMouseEvent (unsnapped)
            pt = event.originalMapPoint()
            self.x0 = pt.x()
            self.y0 = pt.y()
            self._move = False
            return

        if event.button() == _RightButton:
            found_features = self._identify_at_event(event)

            # Deselect all (as your original code)
            for a in self.iface.attributesToolBar().actions():
                if a.objectName() == "mActionDeselectAll":
                    a.trigger()

            if not found_features:
                return

            layer = found_features[0].mLayer
            feature = found_features[0].mFeature
            layer.select(feature.id())
            self.iface.setActiveLayer(layer)

            menu = QMenu()
            menu.addAction("Layer: " + layer.name())
            menu.addSeparator()

            openPropertiesAction = menu.addAction(
                QIcon(os.path.join(self.plugin_dir, "icons", "settings.png")),
                "Layer properties",
            )
            openPropertiesAction.triggered.connect(self.openPropertiesFunc)

            if layer.type() == _VectorLayerType:
                if layer.isEditable():
                    stopEditingAction = menu.addAction(
                        QIcon(os.path.join(self.plugin_dir, "icons", "stopEditing.png")),
                        "Stop editing",
                    )
                    stopEditingAction.triggered.connect(self.stopEditingFunc)

                    addFeatureAction = menu.addAction(
                        QIcon(os.path.join(self.plugin_dir, "icons", "addPolygon.svg")),
                        "Add feature",
                    )
                    addFeatureAction.triggered.connect(self.addFeatureFunc)

                    reshapeFeatureAction = menu.addAction(
                        QIcon(os.path.join(self.plugin_dir, "icons", "reshape.svg")),
                        "Reshape feature",
                    )
                    reshapeFeatureAction.triggered.connect(self.reshapeFeatureFunc)

                    nodeToolAction = menu.addAction(
                        QIcon(os.path.join(self.plugin_dir, "icons", "nodeTool.svg")),
                        "Node tool",
                    )
                    nodeToolAction.triggered.connect(self.nodeToolFunc)
                else:
                    startEditingAction = menu.addAction(
                        QIcon(os.path.join(self.plugin_dir, "icons", "startEditing.png")),
                        "Start editing",
                    )
                    startEditingAction.triggered.connect(self.startEditingFunc)

                openAttributeTableAction = menu.addAction(
                    QIcon(os.path.join(self.plugin_dir, "icons", "attributeTable.png")),
                    "Attribute table",
                )
                openAttributeTableAction.triggered.connect(self.openAttributeTableFunc)

                editFeatureAction = menu.addAction(
                    QIcon(os.path.join(self.plugin_dir, "icons", "editAttributes.png")),
                    "Edit attributes",
                )
                editFeatureAction.triggered.connect(self.editFeatureFunc)

                zoomToFeatureAction = menu.addAction(
                    QIcon(os.path.join(self.plugin_dir, "icons", "zoomToFeature.png")),
                    "Zoom to feature",
                )
                zoomToFeatureAction.triggered.connect(self.zoomToFeatureFunc)

            zoomToLayerAction = menu.addAction(
                QIcon(os.path.join(self.plugin_dir, "icons", "zoomToLayer.png")),
                "Zoom to layer",
            )
            zoomToLayerAction.triggered.connect(self.zoomToLayerFunc)

            menu.exec(QCursor.pos())  # Qt6: exec()

    def stopEditingFunc(self):
        self.iface.actionToggleEditing().trigger()

    def startEditingFunc(self):
        self.iface.actionToggleEditing().trigger()

    def addFeatureFunc(self):
        self.iface.actionAddFeature().trigger()

    def reshapeFeatureFunc(self):
        for a in self.iface.advancedDigitizeToolBar().actions():
            if a.objectName() == "mActionReshapeFeatures":
                a.trigger()

    def nodeToolFunc(self):
        self.iface.actionVertexTool().trigger()

    def openPropertiesFunc(self):
        self.iface.showLayerProperties(self.iface.activeLayer())

    def openAttributeTableFunc(self):
        self.iface.showAttributeTable(self.iface.activeLayer())

    def editFeatureFunc(self):
        featureForm = self.iface.getFeatureForm(
            self.iface.activeLayer(),
            self.iface.activeLayer().selectedFeatures()[0],
        )
        featureForm.show()

    def zoomToLayerFunc(self):
        self.iface.actionZoomToLayer().trigger()

    def zoomToFeatureFunc(self):
        self.iface.actionZoomToSelected().trigger()

    def canvasMoveEvent(self, event):
        if not self.rb:
            return

        self._move = True
        curr = event.originalMapPoint()
        currx = curr.x()
        curry = curr.y()

        self.rb.reset(_PolygonGeometry)

        points = [(self.x0, self.y0), (self.x0, curry), (currx, curry), (currx, self.y0)]
        polygon = [QgsPointXY(x, y) for (x, y) in points]
        self.rb.setToGeometry(QgsGeometry.fromPolygonXY([polygon]), None)

    def canvasReleaseEvent(self, event):
        modifiers = QApplication.keyboardModifiers()

        if self.rb and self._move:
            if modifiers != _ControlModifier:
                for a in self.iface.selectionToolBar().actions():
                    if a.objectName() == "ActionDeselection":
                        for b in a.defaultWidget().actions():
                            if b.objectName() == "mActionDeselectAll":
                                b.trigger()

            if self.rb.numberOfVertices() > 2:
                geom = self.rb.asGeometry()
                request = QgsFeatureRequest()
                request.setFilterRect(geom.boundingBox())
                request.setFlags(_ExactIntersect)

                for layer in self.iface.mapCanvas().layers():
                    if layer.type() == _VectorLayerType and layer.isEditable():
                        selectedFeatures = layer.selectedFeatureIds()
                        for feature in layer.getFeatures(request):
                            if feature.id() in selectedFeatures:
                                layer.deselect(feature.id())
                            else:
                                layer.select(feature.id())
                                selectedFeatures = layer.selectedFeatureIds()
                                self.iface.setActiveLayer(layer)

            self.rb.setColor(QColor(255, 255, 255, 0))
            self.rb = None
            self._move = False
            return

        if self.rb and not self._move:
            self.rb = None

            found_features = self._identify_at_event(event)
            if found_features:
                layer = found_features[0].mLayer
                feature = found_features[0].mFeature
                self.iface.setActiveLayer(layer)

                if modifiers == _ControlModifier:
                    selectedFeatures = layer.selectedFeatureIds()
                    if feature.id() in selectedFeatures:
                        layer.deselect(feature.id())
                    else:
                        layer.select(feature.id())
                else:
                    for a in self.iface.selectionToolBar().actions():
                        if a.objectName() == "ActionDeselection":
                            for b in a.defaultWidget().actions():
                                if b.objectName() == "mActionDeselectAll":
                                    b.trigger()
                    layer.select(feature.id())
            else:
                for a in self.iface.selectionToolBar().actions():
                    if a.objectName() == "ActionDeselection":
                        for b in a.defaultWidget().actions():
                            if b.objectName() == "mActionDeselectAll":
                                b.trigger()
