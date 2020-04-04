import xml.etree.ElementTree as ET

class configuration(object):

   def systemConfiguration(self):
      return { "locations": configuration().config('locations'),
               "options": configuration().config('options'),
               "radiostations": configuration().config('radiostations')}

   def config(self,setting):
      XMLtree = ET.parse("config.xml")
      doc = XMLtree.getroot()
      for elem in doc.findall('config'): 
         if elem.get('name') == setting: 
            items = []       
            for item in elem.findall('item'):
               items.append([item.get('name'),item.get('location')])
            return items