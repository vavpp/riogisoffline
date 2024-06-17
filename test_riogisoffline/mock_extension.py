from qgis.core import QgsGeometry, QgsPointXY

class Field:
  def __init__(self, name, value):
    self._name = name
    self._value = value
  def name(self):
    return self._name

def fields(*args):
  yield Field('lsid', 123)
  yield Field('from_psid', 564)
  yield Field('to_psid', 456)

class Feature:
  def __init__(self):
    pass
    
  def geometry():
    return QgsGeometry.fromPointXY(QgsPointXY(0, 0))
    
  def fields(self):
    return [Field('lsid', 123), Field('from_psid', 564), Field('to_psid', 456)]

class Layer:
  def __init__(self):
    self.features = [Feature()]

  def getFeatures(self):
    return self.features
    
