# -*- coding: utf-8 -*-

"""
/***************************************************************************
 RioGIS Offline
                                En QGIS plugin
    Denne modulen er ment spesifikt for et kartlag i typen RioGIS. Den vil 
    kun hente spesifikke attributter knyttet til RioGIS modellen.
    Attributtene eksporteres så i et wincan motakelig text format.                                            
                              -------------------
                                                                            
                                                                            
                                                                            
                                                                            
 ***************************************************************************/

/***************************************************************************
 *   Alle står fritt til å bruke denne plugin, men den vil ikke gi noe     *
 *   verdi uten selve RioGIS bakenden.                                     *
 *                                                                         *
 *                                                                         *
 *                                                                         *
 *                                                                         *
 ***************************************************************************/
"""

__all__ = ["plugin"]

# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """
    Handle directory path environment variable and depencdecies, then load RioGIS from file riogis.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """

    # Initialize plugin directory path
    import os
    pdir = os.path.dirname(__file__)
    os.environ['PLUGIN_DIR'] = pdir
    
    
    # Install requirements
    try:
        import azure.storage.blob
        import azure.data.tables
    except:
        from riogisoffline.plugin.dependency_installer import DependencyInstaller
        deps = DependencyInstaller()
        deps.install_requirements()

    # Run program
    from riogisoffline.plugin.riogis import RioGIS
    return RioGIS(iface)
