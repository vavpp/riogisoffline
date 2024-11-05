import os
from qgis.PyQt.QtGui import QColor, QFont
from qgis.core import (
    Qgis,
    QgsProject,
    QgsVectorLayer,
    QgsRuleBasedRenderer,
    QgsSymbol,
    QgsCoordinateReferenceSystem,
    QgsPalLayerSettings,
    QgsTextFormat,
    QgsTextBufferSettings,
    QgsVectorLayerSimpleLabeling
)
from qgis.utils import iface
import riogisoffline.plugin.utils as utils


bg_filepath = os.getenv('BACKGROUND_MAP')
source_filepath = os.getenv('SOURCE_MAP')

LAYERS = [
            {
                "group": "RioGIS",
                "items": [
                    {
                        "rules": [
                            {
                                "expression": '"status_internal" = 1',
                                "color": QColor(255, 170, 0, alpha=255),
                                "legend_label": "Bestilt",
                                "width": 1,
                            },
                            {
                                "expression": '"status_internal" = 2',
                                "color": QColor(169, 0, 230, alpha=255),
                                "legend_label": "Under utførelse",
                                "width": 1,
                            },
                            {
                                "expression": '"status_internal" = 3',
                                "color": QColor(230, 0, 0, alpha=255),
                                "legend_label": "Ikke inspisert",
                                "width": 1,
                            },
                            {
                                "expression": '"status_internal" = 4',
                                "color": QColor(0, 115, 76, alpha=255),
                                "legend_label": "Fullført",
                                "width": 1,
                            },
                            {
                                "expression": '"status_internal" = 5',
                                "color": QColor(230, 230, 0, alpha=255),
                                "legend_label": "Avbrutt",
                                "width": 1,
                            },
                        ],
                        "geometry": QgsVectorLayer(
                            f"{source_filepath}|layername=Bestillinger",
                            "Bestillinger",
                            "ogr",
                        ),
                        "label": "lsid",
                    },
                    
                    {
                        "rules": [
                            {
                                "expression": '"status" = 1',
                                "color": QColor(255, 170, 0, alpha=255),
                                "outline": True,
                                "width": 1,
                                "legend_label": "Bestilt",
                                "fill": "transparent",
                            },
                            {
                                "expression": '"status" = 2',
                                "color": QColor(169, 0, 230, alpha=255),
                                "outline": True,
                                "width": 1,
                                "legend_label": "Under utførelse",
                                "fill": "transparent",
                            },
                            {
                                "expression": '"status" = 4',
                                "color": QColor(0, 115, 76, alpha=255),
                                "outline": True,
                                "width": 1,
                                "legend_label": "Fullført",
                                "fill": "transparent",
                            },
                        ],
                        "geometry": QgsVectorLayer(
                            f"{source_filepath}|layername=Prosjekt", "Prosjekt", "ogr"
                        ),
                        "label": "project_name || ': \n' ||comments",
                    },
                    
                ],
            },
            {
                "group": "VA-data",
                "items": [
                    {
                        "rules": [
                            {
                                "expression": "",
                                "color": QColor(122, 122, 122, alpha=200),
                                "legend_label": "Kum",
                                "size": 1.5,
                            }
                        ],
                        "geometry": QgsVectorLayer(
                            f"{source_filepath}|layername=Kum", "Kum", "ogr"
                        ),
                        "label": "psid",
                    },
                    {
                        "rules": [
                            {
                                "expression": "\"fcode\" = 'VL'",
                                "color": QColor(0, 0, 200, alpha=200),
                                "legend_label": "Vannledning",
                            }
                        ],
                        "geometry": QgsVectorLayer(
                            f"{source_filepath}|layername=Vannledning", "Vannledning", "ogr"
                        ),
                        "label": "dim || ' ' || material || ' ' || fcode || lsid || '  '",
                    },
                    {
                        "rules": [
                            {
                                "expression": "\"fcode\" = 'AF'",
                                "color": QColor(234, 10, 0, alpha=200),
                                "legend_label": "Avløpsledning",
                            },
                            {
                                "expression": "\"fcode\" = 'SP'",
                                "color": QColor(0, 200, 0, alpha=200),
                                "legend_label": "Spillvannsledning",
                            },
                            {
                                "expression": "\"fcode\" = 'OV'",
                                "color": QColor(0, 0, 0, alpha=200),
                                "legend_label": "Overvannsledning",
                            }
                        ],
                        "geometry": QgsVectorLayer(
                            f"{source_filepath}|layername=Avløpsledning", "Avløpsledning", "ogr"
                        ),
                        "label": "dim || ' ' || material || ' ' || fcode || lsid || '  '",
                    }
                ],
            },
            {
                "group": "Bakgrunnskart",
                "items": [
                    {
                        "rules": [
                            {
                                "expression": "",
                                "color": QColor(72, 196, 255, alpha=255),
                                "outline": True,
                                "width": 0.2,
                                "legend_label": "",
                                "fill": QColor(72, 196, 255, alpha=65),
                            }
                        ],
                        "geometry": QgsVectorLayer(
                            f"{bg_filepath}|layername=T32_0301vann_flate", "Vann", "ogr"
                        ),
                    },
                    {
                        "rules": [
                            {
                                "expression": "",
                                "color": QColor(175, 175, 175, alpha=255),
                                "outline": True,
                                "width": 0.2,
                                "legend_label": "",
                                "fill": QColor(230, 230, 230, alpha=255),
                            }
                        ],
                        "geometry": QgsVectorLayer(
                            f"{bg_filepath}|layername=T32_0301veg_flate", "Veg", "ogr"
                        ),
                    },              
                    {
                        "rules": [
                            {
                                "expression": "",
                                "color": QColor(190, 150, 130, alpha=255),
                                "outline": True,
                                "width": 0.2,
                                "legend_label": "",
                                "fill": QColor(235, 231, 222, alpha=255),
                            }
                        ],
                        "geometry": QgsVectorLayer(
                            f"{bg_filepath}|layername=T32_0301bygning_flate",
                            "Bygning",
                            "ogr",
                        ),
                    },
                    {
                        "rules": [
                            {
                                "expression": "",
                                "color": QColor(255, 0, 0, alpha=255),
                                "legend_label": "",
                            }
                        ],
                        "geometry": QgsVectorLayer(
                            f"{bg_filepath}|layername=T32_0301_eiendomskart_linje",
                            "Eiendomskart",
                            "ogr",
                        ),
                        "disable_at_startup": True,
                    },
                    {
                        "rules": [
                            {
                                "expression": "",
                                "color": QColor(220, 167, 120, alpha=50),
                                "legend_label": "",
                            }
                        ],
                        "geometry": QgsVectorLayer(
                            f"{bg_filepath}|layername=T32_0301hoydekurve_5m_linje",
                            "Høydekurve",
                            "ogr",
                        ),
                        "disable_at_startup": False,
                    },
                    {
                        "rules": [
                            {
                                "expression": '"OBJTYPE" = \'Kumlokk\'',
                                "color": QColor(255, 100, 40, alpha=100),
                                "legend_label": "Kumlokk",
                            },
                            {
                                "expression": '"OBJTYPE" = \'VA_Sluk\'',
                                "color": QColor(71, 150, 92, alpha=100),
                                "legend_label": "Sluk",
                            },
                            {
                                "expression": '"OBJTYPE" = \'VA_Hydrant\'',
                                "color": QColor(30, 50, 200, alpha=100),
                                "legend_label": "Hydrant",
                            },
                        ],
                        "geometry": QgsVectorLayer(
                            f"{bg_filepath}|layername=T32_0301ledning_punkt",
                            "VApunkt",
                            "ogr",
                        ),
                        "disable_at_startup": True,
                    },
                    {
                        "rules": [
                            {
                                "expression": '"OBJTYPE" = \'PresAdressepunkt\'',
                                "color": QColor(0, 0, 0, alpha=0),
                                "legend_label": "Adresse",
                                "outline": False,
                                "width": 1,
                                "fill": "transparent",
                            },
                            {
                                "expression": '"OBJTYPE" = \'PresStedsnavn\'',
                                "color": QColor(0, 0, 0, alpha=0),
                                "legend_label": "Stedsnavn",
                                "outline": False,
                                "width": 1,
                                "fill": "transparent",
                            },
                            {
                                "expression": '"OBJTYPE" = \'PresVegnummer\'',
                                "color": QColor(0, 0, 0, alpha=0),
                                "legend_label": "Vegnummer",
                                "outline": False,
                                "width": 1,
                                "fill": "transparent",
                            },
                            {
                                "expression": '"OBJTYPE" = \'PresGatenavn\'',
                                "color": QColor(0, 0, 0, alpha=0),
                                "legend_label": "Gatenavn",
                                "outline": False,
                                "width": 1,
                                "fill": "transparent",
                            },
                            {
                                "expression": '"OBJTYPE" = \'PresAnnenTekst\'',
                                "color": QColor(0, 0, 0, alpha=0),
                                "legend_label": "AnnenTekst",
                                "outline": False,
                                "width": 1,
                                "fill": "transparent",
                            },
                        ],
                        "geometry": QgsVectorLayer(
                            f"{bg_filepath}|layername=T32_0301_tekst1000_punkt",
                            "Tekst",
                            "ogr",
                        ),
                        "label": "STRENG",
                        "disable_at_startup": False,
                    },
                ],
            },
        ]

class MissingSourceError(Exception):
    pass

class MapRefresher:

    def refresh_map(self, filename):

        assert 'db' in source_filepath
        assert 'gpkg' in bg_filepath

        # Create an empty project
        if not os.path.exists(source_filepath):
            raise MissingSourceError(f'Missing source: {source_filepath}')
        elif not os.path.exists(bg_filepath):
            raise MissingSourceError(f'Missing source: {bg_filepath}')
        
        project = QgsProject.instance()
        project.clear()
        project.setFileName(filename)
        root = project.layerTreeRoot()
        
        for groups in LAYERS:
            name = groups["group"]
            items = groups["items"]
            group = root.addGroup(name)

            for maps in reversed(items):
                self.add_map_layers(group, maps, name)

        # Save the project as a .qgz file
        project.write()

        utils.printInfoMessage("Lastet kart")

        return project
    
    def zoom_to_extent(self):
        """Zoom to extent of first layer
        """
        
        # layer to zoom to
        layer = LAYERS[0]["items"][0]["geometry"]
        canvas = iface.mapCanvas()
        canvas.setExtent(layer.extent())
        canvas.refresh()
    
    def add_map_layers(self, group, maps, name):
        layer = maps["geometry"]
        label = maps.get("label")
        
        if label:
            self._set_map_label(layer, label)

        disable_at_startup = maps.get("disable_at_startup")
        
        layer.setCrs(QgsCoordinateReferenceSystem("EPSG:25832"))
        
        if maps["rules"]:
            self._add_rules(layer, maps, name, label)
        elif maps.get("raster"):
            pass

        group.addLayer(layer)
        
        # disable VA-data group when loading map
        if name == "VA-data":
            group.setItemVisibilityChecked(False)
        
        # dont show items marked disable_at_startup
        if disable_at_startup:
            group.findLayer(layer).setItemVisibilityChecked(not disable_at_startup)

    def _add_rules(self, layer, maps, name, label):
        symbol = QgsSymbol.defaultSymbol(layer.geometryType())
        renderer = QgsRuleBasedRenderer(symbol)
        root_rule = None

        for i, rulebook in enumerate(maps["rules"]):
            if root_rule is None:
                
                # TODO fails when first time after syncing
                root_rule = renderer.rootRule()
                try:
                    rule = root_rule.children()[0]
                except: 
                    utils.printCriticalMessage("Lasting av kart feilet! Start QGIS på nytt og prøv igjen!", message_duration=0)
            else:
                rule = root_rule.children()[0].clone()

            rule.setLabel(rulebook["legend_label"])
            rule.setFilterExpression(rulebook["expression"])
            
            if "size" in rulebook:
                rule.symbol().setSize(rulebook["size"])
                rule.symbol().setSizeUnit(Qgis.RenderUnit.MetersInMapUnits)
            
            if "outline" in rulebook:
                rule.symbol().setColor(QColor(rulebook["fill"]))
                rule.symbol().symbolLayer(0).setStrokeColor(rulebook["color"])
                rule.symbol().symbolLayer(0).setStrokeWidth(rulebook["width"])
            elif "width" in rulebook:
                rule.symbol().symbolLayer(0).setWidth(rulebook["width"])
                rule.symbol().setColor(rulebook["color"])
            else:
                rule.symbol().setColor(rulebook["color"])

            if i > 0:
                renderer.rootRule().appendChild(rule)
        
        layer.setRenderer(renderer)
        layer.triggerRepaint()

    def _set_map_label(self, layer, field):
        layer_settings = QgsPalLayerSettings()
        text_format = QgsTextFormat()

        text_format.setFont(QFont("Arial", 12))
        text_format.setSize(12)

        buffer_settings = QgsTextBufferSettings()
        buffer_settings.setEnabled(True)
        buffer_settings.setSize(0.5)
        buffer_settings.setColor(QColor("white"))
        
        if layer.name() == "Prosjekt":
            layer_settings.minimumScale = 8000
            layer_settings.maximumScale = 2000
            
            layer_settings.priority = 10
            layer_settings.autoWrapLength = 80
        elif layer.name() in ["Avløpsledning", "Vannledning"]:
            text_format.setSize(13)

            layer_settings.priority = 1        
            layer_settings.minimumScale = 1000
            layer_settings.placement = Qgis.LabelPlacement.Curved
        elif layer.name() == "Kum":
            text_format.setSize(11)
            
            layer_settings.priority = 10
            layer_settings.minimumScale = 800
            layer_settings.placement = Qgis.LabelPlacement.AroundPoint
        else:
            text_format.setSize(9)
            text_format.setColor(QColor(60, 60, 60))
            
            layer_settings.priority = 0
            layer_settings.minimumScale = 1800
            layer_settings.placement = Qgis.LabelPlacement.OverPoint
        
        layer_settings.scaleVisibility = True

        text_format.setBuffer(buffer_settings)
        layer_settings.setFormat(text_format)
        layer_settings.isExpression = True
        layer_settings.fieldName = field
        layer_settings.enabled = True
        
        layer_labeling = QgsVectorLayerSimpleLabeling(layer_settings)
        layer.setLabelsEnabled(True)
        layer.setLabeling(layer_labeling)
        layer.triggerRepaint()
