from qgis.core import QgsGeometry, QgsPointXY

class Field:
  def __init__(self, name, value):
    self._name = name
    self._value = value
  def name(self):
    return self._name

class Feature:
  def __init__(self):
    pass
    
  def geometry(self):
    return QgsGeometry.fromPointXY(QgsPointXY(0, 0))
  
  def __getattr__(self, name):
    if name not in ['geometry']:
      return name

  def __getitem__(self, key):
        return getattr(self, key)
    
class Layer:
  def __init__(self):
    self.features = [Feature()]

  def name(self):
    return 'Bestillinger'

  def getFeatures(self):
    return self.features
  
  def fields(self):
    return [
        Field('lsid', 123), 
        Field('from_psid', 564), 
        Field('to_psid', 456),
        Field('operator', 'test'),
        Field('streetname', 'testgata'),
        Field('fcodegroup', 'avlop')
      ]

class Point:
  def __init__(self):
    pass
  def x(self):
    return 0
  def y(self):
    return 0
      
