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
    QgsVectorLayerSimpleLabeling,
    QgsMarkerLineSymbolLayer, 
    QgsSymbolLayerRegistry, 
    QgsLineSymbol, 
    QgsSimpleLineSymbolLayer,
)
from qgis.utils import iface
import riogisoffline.plugin.utils as utils


bg_filepath = os.getenv('BACKGROUND_MAP')
source_filepath = os.getenv('SOURCE_MAP')

DEFAULT_BESTILLINGER_LINE_WIDTH = 1.1
DEFAULT_LINE_WIDTH = 0.6
DEFAULT_IKKE_KOMMUNAL_LINE_WIDTH = 0.5
DEFAULT_STIKKLEDNING_WIDTH = 0.3

STATUS_ERSTATTET_NEDLAGT = "\"status\" = 'E' OR \"status\" = 'EF' OR \"status\" = 'F' OR \"status\" = 'EN'"
STATUS_PROSJEKTERT_IKKE_I_BRUK = "\"status\" = 'P' OR \"status\" = 'I'"

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
                                "width": DEFAULT_BESTILLINGER_LINE_WIDTH,
                            },
                            {
                                "expression": '"status_internal" = 2',
                                "color": QColor(169, 0, 230, alpha=255),
                                "legend_label": "Under utførelse",
                                "width": DEFAULT_BESTILLINGER_LINE_WIDTH,
                            },
                            {
                                "expression": '"status_internal" = 3',
                                "color": QColor(230, 0, 0, alpha=255),
                                "legend_label": "Kunne ikke inspiseres",
                                "width": DEFAULT_BESTILLINGER_LINE_WIDTH,
                            },
                            {
                                "expression": '"status_internal" = 4',
                                "color": QColor(0, 115, 76, alpha=255),
                                "legend_label": "Fullført",
                                "width": DEFAULT_BESTILLINGER_LINE_WIDTH,
                            },
                            {
                                "expression": '"status_internal" = 5',
                                "color": QColor(230, 230, 0, alpha=255),
                                "legend_label": "Avbrutt",
                                "width": DEFAULT_BESTILLINGER_LINE_WIDTH,
                            },
                            {
                                "expression": '"status_internal" = 8',
                                "color": QColor(28, 247, 255, alpha=255),
                                "legend_label": "Spyling",
                                "width": DEFAULT_BESTILLINGER_LINE_WIDTH,
                            },
                        ],
                        "geometry": QgsVectorLayer(
                            f"{source_filepath}|layername=Bestillinger",
                            "Bestillinger",
                            "ogr",
                        ),
                        "label": "fcode || lsid || '  '",
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
                "disable_group": True,
                "items": [
                    {
                        "rules": [
                            {
                                "expression": f"\"fcode\" = 'AF' AND {STATUS_ERSTATTET_NEDLAGT}",
                                "color": QColor(234, 10, 0, alpha=200),
                                "legend_label": "Avløp (Erstattet/Nedlagt)",
                                "width": DEFAULT_LINE_WIDTH,
                            },
                            {
                                "expression": f"\"fcode\" = 'SP' AND {STATUS_ERSTATTET_NEDLAGT}",
                                "color": QColor(0, 200, 0, alpha=200),
                                "legend_label": "Spillvann (Erstattet/Nedlagt)",
                                "width": DEFAULT_LINE_WIDTH,
                            },
                            {
                                "expression": f"\"fcode\" = 'OV' AND {STATUS_ERSTATTET_NEDLAGT}",
                                "color": QColor(0, 0, 0, alpha=200),
                                "legend_label": "Overvann (Erstattet/Nedlagt)",
                                "width": DEFAULT_LINE_WIDTH,
                            },
                            {
                                "expression": f"\"fcode\" = 'AF' AND {STATUS_PROSJEKTERT_IKKE_I_BRUK}",
                                "color": QColor(234, 10, 0, alpha=200),
                                "legend_label": "Avløp (Prosjektert/Ikke i bruk)",
                                "width": DEFAULT_LINE_WIDTH,
                            },
                            {
                                "expression": f"\"fcode\" = 'SP' AND {STATUS_PROSJEKTERT_IKKE_I_BRUK}",
                                "color": QColor(0, 200, 0, alpha=200),
                                "legend_label": "Spillvann (Prosjektert/Ikke i bruk)",
                                "width": DEFAULT_LINE_WIDTH,
                            },
                            {
                                "expression": f"\"fcode\" = 'OV' AND {STATUS_PROSJEKTERT_IKKE_I_BRUK}",
                                "color": QColor(0, 0, 0, alpha=200),
                                "legend_label": "Overvann (Prosjektert/Ikke i bruk)",
                                "width": DEFAULT_LINE_WIDTH,
                            }
                        ],
                        "geometry": QgsVectorLayer(
                            f"{source_filepath}|layername=Avløpsledning", "Avløpsledning (Ikke drift)", "ogr"
                        ),
                        "collapsed": True,
                        "disable_at_startup": True,
                    },
                    {
                        "rules": [
                            {
                                "expression": f"\"fcode\" = 'AF' AND {STATUS_ERSTATTET_NEDLAGT}",
                                "color": QColor(0, 0, 200, alpha=200),
                                "legend_label": "Vann (Erstattet/Nedlagt)",
                                "width": DEFAULT_LINE_WIDTH,
                            },
                            {
                                "expression": f"\"fcode\" = 'AF' AND {STATUS_PROSJEKTERT_IKKE_I_BRUK}",
                                "color": QColor(0, 0, 200, alpha=200),
                                "legend_label": "Vann (Prosjektert/Ikke i bruk)",
                                "width": DEFAULT_LINE_WIDTH,
                            }
                        ],
                        "geometry": QgsVectorLayer(
                            f"{source_filepath}|layername=Vannledning", "Vannledning (Ikke drift)", "ogr"
                        ),
                        "collapsed": True,
                        "disable_at_startup": True,
                    },
                    {
                        "rules": [
                            {
                                "expression": "\"fcodegroup_txt\" = 'Avløp'",
                                "color": QColor(234, 10, 0, alpha=120),
                                "legend_label": "Avløp",
                                "width": DEFAULT_STIKKLEDNING_WIDTH,
                            },
                            {
                                "expression": "\"fcodegroup_txt\" = 'Spillvann'",
                                "color": QColor(0, 200, 0, alpha=120),
                                "legend_label": "Spillvann",
                                "width": DEFAULT_STIKKLEDNING_WIDTH,
                            },
                            {
                                "expression": "\"fcodegroup_txt\" = 'Overvann'",
                                "color": QColor(0, 0, 0, alpha=120),
                                "legend_label": "Overvann",
                                "width": DEFAULT_STIKKLEDNING_WIDTH,
                            },
                            {
                                "expression": "\"fcodegroup_txt\" = 'Vann'",
                                "color": QColor(0, 0, 200, alpha=120),
                                "legend_label": "Vann",
                                "width": DEFAULT_STIKKLEDNING_WIDTH,
                            }
                        ],
                        "geometry": QgsVectorLayer(
                            f"{source_filepath}|layername=Stikkledninger", "Stikkledninger", "ogr"
                        ),
                        "label": "dim || ' ' || material || ' ' || fcode || lsid || '  '",
                        "collapsed": True,
                    },
                    {
                        "rules": [
                            {
                                "expression": "\"owner\" != 'K'",
                                "color": QColor(80, 200, 80, alpha=200),
                                "legend_label": "Kum",
                                "size": 1.5,
                            }
                        ],
                        "geometry": QgsVectorLayer(
                            f"{source_filepath}|layername=Kum", "Kum (ikke kommunalt)", "ogr"
                        ),
                        "label": "psid",
                        "collapsed": True,
                    },
                    {
                        "rules": [
                            {
                                "expression": "\"fcode\" = 'VL' AND \"owner\" != 'K'",
                                "color": QColor(0, 0, 200, alpha=200),
                                
                                "legend_label": "Vann",
                                "width": DEFAULT_IKKE_KOMMUNAL_LINE_WIDTH,
                            }
                        ],
                        "geometry": QgsVectorLayer(
                            f"{source_filepath}|layername=Vannledning", "Vannledning (ikke kommunalt)", "ogr"
                        ),
                        "label": "dim || ' ' || material || ' ' || fcode || lsid || '  '",
                        "collapsed": True,
                    },
                    {
                        "rules": [
                            {
                                "expression": "\"fcode\" = 'AF' AND \"owner\" != 'K'",
                                "color": QColor(234, 10, 0, alpha=200),
                                "legend_label": "Avløp",
                                "width": DEFAULT_IKKE_KOMMUNAL_LINE_WIDTH,
                            },
                            {
                                "expression": "\"fcode\" = 'SP' AND \"owner\" != 'K'",
                                "color": QColor(0, 200, 0, alpha=200),
                                "legend_label": "Spillvann",
                                "width": DEFAULT_IKKE_KOMMUNAL_LINE_WIDTH,
                            },
                            {
                                "expression": "\"fcode\" = 'OV' AND \"owner\" != 'K'",
                                "color": QColor(0, 0, 0, alpha=200),
                                "legend_label": "Overvann",
                                "width": DEFAULT_IKKE_KOMMUNAL_LINE_WIDTH,
                            }
                        ],
                        "geometry": QgsVectorLayer(
                            f"{source_filepath}|layername=Avløpsledning", "Avløpsledning (ikke kommunalt)", "ogr"
                        ),
                        "label": "dim || ' ' || material || ' ' || fcode || lsid || '  '",
                        "collapsed": True,
                    },
                    {
                        "rules": [
                            {
                                "expression": "\"owner\" = 'K'",
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
                                "expression": "\"fcode\" = 'VL' AND \"owner\" = 'K'",
                                "color": QColor(0, 0, 200, alpha=200),
                                "legend_label": "Vann",
                                "width": DEFAULT_LINE_WIDTH,
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
                                "expression": "\"fcode\" = 'AF' AND \"owner\" = 'K' AND \"status\" = 'D'",
                                "color": QColor(234, 10, 0, alpha=200),
                                "legend_label": "Avløp",
                                "width": DEFAULT_LINE_WIDTH,
                            },
                            {
                                "expression": "\"fcode\" = 'SP' AND \"owner\" = 'K' AND \"status\" = 'D'",
                                "color": QColor(0, 200, 0, alpha=200),
                                "legend_label": "Spillvann",
                                "width": DEFAULT_LINE_WIDTH,
                            },
                            {
                                "expression": "\"fcode\" = 'OV' AND \"owner\" = 'K' AND \"status\" = 'D'",
                                "color": QColor(0, 0, 0, alpha=200),
                                "legend_label": "Overvann",
                                "width": DEFAULT_LINE_WIDTH,
                            }
                        ],
                        "geometry": QgsVectorLayer(
                            f"{source_filepath}|layername=Avløpsledning", "Avløpsledning", "ogr"
                        ),
                        "label": "dim || ' ' || material || ' ' || fcode || lsid || '  '",
                    },
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
                                "color": QColor(150, 110, 100, alpha=255),
                                "outline": True,
                                "width": 0.2,
                                "legend_label": "",
                                "fill": QColor(230, 223, 215, alpha=255),
                                "minimumScale": 8000
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
                                "color": QColor(220, 190, 160, alpha=40),
                                "legend_label": "",
                            }
                        ],
                        "geometry": QgsVectorLayer(
                            f"{bg_filepath}|layername=T32_0301hoydekurve_5m_linje",
                            "Høydekurve",
                            "ogr",
                        ),
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
                        "collapsed": True,
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
                                "minimumScale": 1500
                            },
                            {
                                "expression": '"OBJTYPE" = \'PresStedsnavn\'',
                                "color": QColor(0, 0, 0, alpha=0),
                                "legend_label": "Stedsnavn",
                                "outline": False,
                                "width": 1,
                                "fill": "transparent",
                                "minimumScale": 9000
                            },
                            {
                                "expression": '"OBJTYPE" = \'PresGatenavn\'',
                                "color": QColor(0, 0, 0, alpha=0),
                                "legend_label": "Gatenavn",
                                "outline": False,
                                "width": 1,
                                "fill": "transparent",
                                "minimumScale": 4000
                            },
                            {
                                "expression": '"OBJTYPE" = \'PresAnnenTekst\'',
                                "color": QColor(0, 0, 0, alpha=0),
                                "legend_label": "AnnenTekst",
                                "outline": False,
                                "width": 1,
                                "fill": "transparent",
                                "minimumScale": 1000
                            },
                        ],
                        "geometry": QgsVectorLayer(
                            f"{bg_filepath}|layername=T32_0301_tekst1000_punkt",
                            "Tekst",
                            "ogr",
                        ),
                        "label": "STRENG",
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

            disable_group = groups.get("disable_group")

            if disable_group:
                group.setItemVisibilityChecked(not disable_group)

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
        
        layer.setCrs(QgsCoordinateReferenceSystem("EPSG:25832"))
        
        if maps["rules"]:
            self._add_rules(layer, maps, name, label)
        elif maps.get("raster"):
            pass

        group.addLayer(layer)
        
        collapsed = maps.get("collapsed")
        disable_at_startup = maps.get("disable_at_startup")

        if collapsed:
            root = QgsProject.instance().layerTreeRoot()
            myLayerNode = root.findLayer(layer.id())
            myLayerNode.setExpanded(not collapsed)
        
        # dont show items marked disable_at_startup
        if disable_at_startup:
            group.findLayer(layer).setItemVisibilityChecked(not disable_at_startup)

    def _add_rules(self, layer, maps, name, label):
    
        
        if layer.name() == "Avløpsledning":
            symbol = QgsSymbol.defaultSymbol(layer.geometryType())
            
            marker_line_layer = QgsMarkerLineSymbolLayer.create({'interval': '25', 'interval_unit': 'MM', 'place_on_every_part': True, 'placements': 'Interval', 'ring_filter': '0', 'rotate': '1'})
            
            registry = QgsSymbolLayerRegistry()

            subSymbol = marker_line_layer.subSymbol()
            
            subSymbol.deleteSymbolLayer(0)
            triangle = registry.symbolLayerMetadata("FilledMarker").createSymbolLayer({'name': 'triangle', 'color': '255,255,255', 'color_border': '100,100,100', 'angle': '90'})
            subSymbol.appendSymbolLayer(triangle)
            
            marker_line_layer.setOffsetAlongLine(5)
            marker_line_layer.setWidth(2)
            marker_line_layer.setWidthUnit(Qgis.RenderUnit.MetersInMapUnits)

            lineLayer = QgsSimpleLineSymbolLayer()
            
            symbol.deleteSymbolLayer(0)
            symbol.appendSymbolLayer(lineLayer)  
            symbol.appendSymbolLayer(marker_line_layer)  
            
        elif ("ikke kommunalt" in layer.name() or layer.name() == "Stikkledninger") and layer.geometryType() == Qgis.GeometryType.Line:
            symbol = QgsLineSymbol.createSimple({'line_style':'dash'})
        elif "Ikke drift" in layer.name() and layer.geometryType() == Qgis.GeometryType.Line:
            symbol = QgsLineSymbol.createSimple({'line_style':'dot'})
        else:
            symbol = QgsSymbol.defaultSymbol(layer.geometryType())
        renderer = QgsRuleBasedRenderer(symbol)
        root_rule = None
        
        for i, rulebook in enumerate(maps["rules"]):
            if root_rule is None:
                
                # TODO fails when first time after syncing
                root_rule = renderer.rootRule()
                try:
                    rule = root_rule.children()[0]
                except Exception as e: 
                    utils.printCriticalMessage(f"Lasting av kartlag {name} - {layer.name()} feilet! Start QGIS på nytt og prøv igjen! \n{str(e)}", message_duration=0)
                    return
            else:
                rule = root_rule.children()[0].clone()

            rule.setLabel(rulebook["legend_label"])
            rule.setFilterExpression(rulebook["expression"])
            
            rule_symbol = rule.symbol()
            
            if "size" in rulebook:
                rule_symbol.setSize(rulebook["size"])
                rule_symbol.setSizeUnit(Qgis.RenderUnit.MetersInMapUnits)
                
            line_layer_index = 0
            
            if "minimumScale" in rulebook:
                rule.setMinimumScale(rulebook["minimumScale"])
            
            if "outline" in rulebook:
                rule_symbol.setColor(QColor(rulebook["fill"]))
                rule_symbol.symbolLayer(line_layer_index).setStrokeColor(rulebook["color"])
                rule_symbol.symbolLayer(line_layer_index).setStrokeWidth(rulebook["width"])
            elif "width" in rulebook:
                rule_symbol.symbolLayer(line_layer_index).setWidth(rulebook["width"])
                if layer.name() == "Avløpsledning":
                    rule_symbol.symbolLayer(line_layer_index).setColor(rulebook["color"])
                else:
                    rule_symbol.setColor(rulebook["color"])
            else:
                rule_symbol.setColor(rulebook["color"])

            if i > 0:
                renderer.rootRule().appendChild(rule)
        
        layer.setRenderer(renderer)
        layer.triggerRepaint()

    def _set_map_label(self, layer, field):

        layer_settings = QgsPalLayerSettings()
        text_format = QgsTextFormat()

        text_format.setFont(QFont("Arial", 12))

        buffer_settings = QgsTextBufferSettings()
        buffer_settings.setEnabled(True)
        buffer_settings.setSize(0.5)
        buffer_settings.setColor(QColor("white"))
        
        if layer.name() == "Prosjekt":
            layer_settings.minimumScale = 8000
            layer_settings.maximumScale = 2000
            
            layer_settings.priority = 10
            layer_settings.autoWrapLength = 60
            
        elif "Avløpsledning" in layer.name() or "Vannledning" in layer.name():
            text_format.setSize(14)

            layer_settings.priority = 1        
            layer_settings.minimumScale = 1000
            layer_settings.placement = Qgis.LabelPlacement.Curved

        elif layer.name() == "Bestillinger":
            text_format.setSize(14)

            layer_settings.priority = 2       
            layer_settings.minimumScale = 1200
            layer_settings.placement = Qgis.LabelPlacement.Curved

        elif layer.name() == "Kum":
            text_format.setSize(12)
            
            layer_settings.priority = 10
            layer_settings.minimumScale = 800
            layer_settings.placement = Qgis.LabelPlacement.AroundPoint

        else:
            text_format.setSize(9)
            text_format.setColor(QColor(60, 60, 60))
            
            layer_settings.priority = 0
            layer_settings.placement = Qgis.LabelPlacement.OverPoint
        

        text_format.setBuffer(buffer_settings)
        layer_settings.setFormat(text_format)

        layer_settings.scaleVisibility = True
        layer_settings.isExpression = True
        layer_settings.fieldName = field
        layer_settings.enabled = True
        
        layer_labeling = QgsVectorLayerSimpleLabeling(layer_settings)
        layer.setLabelsEnabled(True)
        layer.setLabeling(layer_labeling)
        layer.triggerRepaint()
