
from qgis.core import QgsExpression, QgsFeatureRequest, QgsWkbTypes

class SearchBox:

    def __init__(self, dlg, iface):
        self.dlg = dlg
        self.iface = iface

        self.zoom_level_for_point = 100

        self.charatcters_written_until_search = 2
        self.max_features = 5
        self.split_char = "-"

        self.search_layers = {
            "kum": "psid",
            "Bestillinger": "lsid",
            "Prosjekt": "project_name",
            "ledning": "lsid",
            "Tekst": "STRENG",
        }

    def setup(self):
        self.dlg.searchBox.setPlaceholderText("Søk (LSID, PSID, gatenavn, prosjektnavn)...")
        self.dlg.searchBox.textChanged.connect(lambda text: self.onTextChanged(text))
        self.dlg.searchResults.itemClicked.connect(self.onItemClicked)

    def onTextChanged(self, text):
        self.dlg.searchResults.clear()

        if not text or len(text) < self.charatcters_written_until_search:
            return

        canvas = self.iface.mapCanvas()

        for layer_name, layer_id_attr in self.search_layers.items():
            
            layers = [l for l in canvas.layers() if l.name() == layer_name or layer_name in l.name().lower()]

            for layer in layers:
                # Requests features that start with text
                # quote the user text so characters like ' cannot break the expression
                search_value = QgsExpression.quotedString(f"{text}%")
                request = QgsFeatureRequest().setFilterExpression(
                    f'LOWER("{layer_id_attr}") LIKE LOWER({search_value})'
                )

                request_results = layer.getFeatures(request)

                for i, feature in enumerate(request_results):
                    if i >= self.max_features:
                        break

                    self.dlg.searchResults.addItem(f"{str(feature[layer_id_attr])}  {self.split_char} {layer.name()}")

    def onItemClicked(self, item):
        canvas = self.iface.mapCanvas()
        
        split_item_text = item.text().split(self.split_char)
        if len(split_item_text) == 2:
            text = item.text().split(self.split_char)[0].strip()
        else:
             text = self.split_char.join(split_item_text[:-1]).strip()

        layer_name = item.text().split(self.split_char)[-1].strip()

        id_attrs = [id_attr for l_name, id_attr in self.search_layers.items() if l_name.lower() in layer_name.lower()]
        layers = [l for l in canvas.layers() if l.name() == layer_name]

        if not id_attrs or not layers:
            return

        layer_id_attr = id_attrs[0]
        layer = layers[0]

        request = QgsFeatureRequest().setFilterExpression(
            f'"{layer_id_attr}" = {QgsExpression.quotedString(text)}'
        )
        feature = next(iter(layer.getFeatures(request)), None)
        if feature is None:
            return

        if feature.geometry().type() == QgsWkbTypes.GeometryType.Point:
            canvas.zoomScale(self.zoom_level_for_point)
        
        canvas.setExtent(feature.geometry().boundingBox())
        canvas.refresh()