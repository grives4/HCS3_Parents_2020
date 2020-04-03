import re
import time
import serial
import xml.etree.ElementTree as ET

def config(setting, location, info):
         XMLtree = ET.parse("config.xml")
         doc = XMLtree.getroot()
         config = []
         for elem in doc.findall('config'): 
            if elem.get('name') == setting:        
               for item in elem.findall('item'):
                  if item.get('location') == location:
                    return item.get(info)
         return


def write_to_serial_port(data, location='1'):

    sp = serial.Serial(config('serial', location,'address'),config('serial', location,'baud'), timeout=0)
    sp.flush()
    sp.write((data + '\r').encode())
    temp = str(sp.read(9999))
    i = 1
    
    while  re.match(r'^\*AH66(.+)\r',temp) == None and i < 10: 
        time.sleep(.05)
        temp += str(sp.read(9999))
        i += 1
    sp.close()
    temp = temp.split('\r')
    for i in range(0, len(temp)):
        if temp[i].find('MDF') == -1 and temp[i].find('SIGNAL') == -1 and temp[i].find('ACK') == -1 and temp[i].find('66') > 0:
            response = temp[i].replace('*AH66,','')
            return response
    return ""

write_to_serial_port("&AH66,CH,UFB,OFF")
write_to_serial_port("&AH66,CH,UFB,OFF","2")
          