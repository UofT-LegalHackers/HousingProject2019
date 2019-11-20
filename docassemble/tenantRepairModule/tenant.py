from docassemble.base.util import DAObject, Individual
from docassemble.base.functions import verb_past, verb_present


class MyIndividual(Individual):
  pass

class Tenant(MyIndividual):
  pass
    
class TenantGuest(MyIndividual):
  pass

class BrokenItem(DAObject):
  def __str__(self):
    super_str = super().__str__()
    if super_str == "other":
      return "item"
    else:
      return super_str
