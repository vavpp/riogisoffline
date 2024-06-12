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