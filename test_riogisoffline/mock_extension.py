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
    fields = self.fields()
    if name not in [field.name() for field in fields]:
      return name
    
    for field in fields:
      if field.name() == name:
        return field._value()

  def __getitem__(self, key):
    return getattr(self, key)

  def __setitem__(self, name, value):
    setattr(self, name, value)

  def fields(self):
    return [
      Field('geometry', self.geometry()),
      Field('status_internal', 3)
    ]
    

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
        Field('fcodegroup', 'avlop'),
        Field('fcode', 'AF')
      ]
  def startEditing(self):
    pass

  def updateFeature(self, feature):
    pass

  def commitChanges(self):
    pass

  def triggerRepaint(self):
    pass


class Point:
  def __init__(self):
    pass

  def x(self):
    return 0

  def y(self):
    return 0
      
