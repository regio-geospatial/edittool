# -*- coding: utf-8 -*-

def classFactory(iface):  # pylint: disable=invalid-name
    """Load EditTool class from file EditTool.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .edit_tool import EditTool
    return EditTool(iface)
