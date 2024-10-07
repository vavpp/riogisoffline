import os
from qgis.PyQt.QtGui import QColor, QFont
from qgis.core import (
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
                        "label": "project_name",
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
                            }
                        ],
                        "geometry": QgsVectorLayer(
                            f"{source_filepath}|layername=Kum", "Kum", "ogr"
                        ),
                        "label": "text",
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
                        "label": "lsid",
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
                        "label": "lsid",
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
                                "color": QColor(190, 178, 151, alpha=255),
                                "outline": True,
                                "width": 0.5,
                                "legend_label": "",
                                "fill": QColor(190, 178, 151, alpha=55),
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
                                "color": QColor(72, 196, 255, alpha=255),
                                "outline": True,
                                "width": 0.5,
                                "legend_label": "",
                                "fill": QColor(72, 196, 255, alpha=55),
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
                                "width": 0.5,
                                "legend_label": "",
                                "fill": QColor(175, 175, 175, alpha=55),
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
                                "expression": '"OBJTYPE" = "AnnetGjerde"',
                                "color": QColor(247, 247, 247, alpha=255),
                                "legend_label": "AnnetGjerde",
                            },
                            {
                                "expression": '"OBJTYPE" = "Bruavgrensning"',
                                "color": QColor(0, 0, 0, alpha=255),
                                "legend_label": "Bruavgrensning",
                            },
                            {
                                "expression": '"OBJTYPE" = "BrønnGrense"',
                                "color": QColor(98, 251, 252, alpha=255),
                                "legend_label": "BrønnGrense",
                            },
                            {
                                "expression": '"OBJTYPE" = "DamKant"',
                                "color": QColor(53, 148, 255, alpha=255),
                                "legend_label": "DamKant",
                            },
                            {
                                "expression": '"OBJTYPE" = "Kultvert"',
                                "color": QColor(122, 122, 122, alpha=255),
                                "legend_label": "Kultvert",
                            },
                        ],
                        "geometry": QgsVectorLayer(
                            f"{bg_filepath}|layername=T32_0301bygnanlegg_linje",
                            "BygganleggLinje",
                            "ogr",
                        ),
                        "disable_at_startup": True,
                    },
                    {
                        "rules": [
                            {
                                "expression": "",
                                "color": QColor(229, 167, 0, alpha=255),
                                "legend_label": "",
                            }
                        ],
                        "geometry": QgsVectorLayer(
                            f"{bg_filepath}|layername=T32_0301hoydekurve_5m_linje",
                            "Høydekurve",
                            "ogr",
                        ),
                        "disable_at_startup": True,
                    },
                    {
                        "rules": [
                            {
                                "expression": '"OBJTYPE" = "BautaStatue"',
                                "color": QColor(122, 122, 122, alpha=255),
                                "legend_label": "BautaStatue",
                            },
                            {
                                "expression": '"OBJTYPE" = "BensinPumpe"',
                                "color": QColor(122, 122, 122, alpha=255),
                                "legend_label": "BensinPumpe",
                            },
                            {
                                "expression": '"OBJTYPE" = "FlaggStang"',
                                "color": QColor(122, 122, 122, alpha=255),
                                "legend_label": "FlaggStang",
                                "style": "dot  white",
                            },
                        ],
                        "geometry": QgsVectorLayer(
                            f"{bg_filepath}|layername=T32_0301bygnanlegg_punkt",
                            "BygganleggPunkt",
                            "ogr",
                        ),
                        "disable_at_startup": True,
                    },
                    {
                        "rules": [
                            {
                                "expression": "",
                                "color": QColor(122, 122, 122, alpha=20),
                                "legend_label": "",
                            }
                        ],
                        "geometry": QgsVectorLayer(
                            f"{bg_filepath}|layername=T32_0301ledningva_punkt",
                            "VApunkt",
                            "ogr",
                        ),
                        "disable_at_startup": True,
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
                root_rule = renderer.rootRule()
                rule = root_rule.children()[0]
            else:
                rule = root_rule.children()[0].clone()

            rule.setLabel(rulebook["legend_label"])
            rule.setFilterExpression(rulebook["expression"])
            
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
        
        if name == "Bakgrunnskart":
            renderer.setReferenceScale(1000)
        elif label == "text":
            renderer.setReferenceScale(500)
        
        layer.setRenderer(renderer)
        layer.triggerRepaint()

    def _set_map_label(self, layer, field):
        layer_settings = QgsPalLayerSettings()
        text_format = QgsTextFormat()

        text_format.setFont(QFont("Arial", 12))
        text_format.setSize(12)

        buffer_settings = QgsTextBufferSettings()
        buffer_settings.setEnabled(True)
        buffer_settings.setSize(1)
        buffer_settings.setColor(QColor("white"))

        text_format.setBuffer(buffer_settings)
        layer_settings.setFormat(text_format)
        layer_settings.fieldName = field
        layer_settings.enabled = True

        layer_settings.minimumScale = 25000
        layer_settings.scaleVisibility = True
        
        layer_settings = QgsVectorLayerSimpleLabeling(layer_settings)
        layer.setLabelsEnabled(True)
        layer.setLabeling(layer_settings)
        layer.triggerRepaint()
