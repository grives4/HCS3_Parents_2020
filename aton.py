import os
import re
import time
import threading
import xml.etree.ElementTree as ET
import pdb
import subprocess
import logging
import serial
import sys

logger = logging.getLogger('HCS3')


class AtonProcessor():

   def __init__(self):

      super(AtonProcessor, self).__init__() 

      #Unsolicited feedback is annoying...and unsolicited.  Turn it off.
      #try: 
      self.write_to_serial_port("&AH66,CH,UFB,OFF")
      self.write_to_serial_port("&AH66,CH,UFB,OFF","2")
      logger.info("Accessed serial ports with no errors")
      #except:
      #    sys.exit("Could not access serial points.")
      
      self.cache = {}

   def ProcessRequest(self,callbacks,request):
      
      logger.debug("Aton Request: " + str(request))

      requestName = request['name'].split('_')
      if request['value'] != 'get':
         if (requestName[0] == 'source'):
            self.write_to_serial_port('&AH66,AUD,' + requestName[2] + ',' + request['value'],requestName[1])  
            self.cache[request['name']] = request['value']
            callbacks.send_message([request['name'] +',' + self.cache[request['name']]])
         elif (requestName[0] == 'radio'):
            self.write_to_serial_port('&AH66,R1,TUNE,' + request['value'].replace(".","") + '0',"1")
            self.write_to_serial_port('&AH66,R1,TUNE,' + request['value'].replace(".","") + '0',"2")
            self.cache[request['name']] =  request['value']
            callbacks.send_message(['radio,' + request['value']])   
         elif (requestName[0] == 'volume'):
            if (request['value'] == 'up'):
               volume = int(self.get_volume(requestName[2],requestName[1])) + 5
               self.write_to_serial_port('&AH66,VOL,' + str(requestName[2]) + ',' + str(volume),requestName[1])  
            elif (request['value'] == 'down'):
               volume = int(self.get_volume(requestName[2],requestName[1])) - 5
               self.write_to_serial_port('&AH66,VOL,' + str(requestName[2]) + ',' + str(volume),requestName[1])  
            else:
               self.write_to_serial_port('&AH66,VOL,' + str(requestName[2]) + ',' + str(request['value']),requestName[1])  
            self.cache[request['name']] = self.get_volume(requestName[2],requestName[1])
            callbacks.send_message([request['name'] +',' + self.cache[request['name']]])
         elif (requestName[0] == 'alloff'):
            self.write_to_serial_port('&AH66,KEY,0,0000','1')
            self.write_to_serial_port('&AH66,KEY,0,0000','2')
            callbacks.send_message(['alloff'])   
         elif (requestName[0] == 'mute'):
            for channel in range(1,7):
               self.write_to_serial_port('&AH66,KEY,' + str(channel) + ',0020','1')
               self.write_to_serial_port('&AH66,KEY,' + str(channel) + ',0020','2')
            callbacks.send_message(['mute'])   
         elif (requestName[0] == 'unmute'):
            for channel in range(1,7):
               self.write_to_serial_port('&AH66,KEY,' + str(channel) + ',0019','1')
               self.write_to_serial_port('&AH66,KEY,' + str(channel) + ',0019','2')
            callbacks.send_message(['unmute'])   
         elif (requestName[0] == 'treble'):
            treble = int(request['value'])
            if treble < 0:
               treble = treble * -1
               self.write_to_serial_port('&AH66,TRE,' + str(requestName[2]) + ',-,' + str(treble),requestName[1])
            else:
               self.write_to_serial_port('&AH66,TRE,' + str(requestName[2]) + ',+,' + str(treble),requestName[1])
            self.cache[request['name']] = treble
         elif (requestName[0] == 'base'):
            base = int(request['value'])
            if base < 0:
               base = base * -1
               self.write_to_serial_port('&AH66,BAS,' + str(requestName[2]) + ',-,' + str(base),requestName[1])
            else:
               self.write_to_serial_port('&AH66,BAS,' + str(requestName[2]) + ',+,' + str(base),requestName[1])
            self.cache[request['name']] = base
         elif (requestName[0] == 'flushcache'):
            self.cache = {}
            callbacks.send_message(['reload'])
         else:
            callbacks.send_message(['error, Error: Could not process: ' + request['name'] + ' >> ' + request['value']])
      else:
         if request['name'] in self.cache:
            callbacks.send_message([request['name'] + ',' + str(self.cache[request['name']])])
         else:
            if (requestName[0] == 'radio'):
               self.cache[request['name']] = self.get_radio_station()
            elif (requestName[0] == 'volume'):
               self.cache[request['name']] = self.get_volume(requestName[2],requestName[1])
            elif (requestName[0] == 'treble'):
               self.cache[request['name']] = self.get_treble(requestName[2],requestName[1])
            elif (requestName[0] == 'base'):
               self.cache[request['name']] = self.get_base(requestName[2],requestName[1])
            elif (requestName[0] == 'source'):
               self.cache[request['name']] = self.get_source(requestName[2],requestName[1])
            callbacks.send_message([request['name'] + ',' + str(self.cache[request['name']])])
            


   def write_to_serial_port(self, data, location='1'):
      
      try:
         sp = serial.Serial(self.config('serial', location,'address'),self.config('serial', location,'baud'), timeout=0)
         sp.flush()
         logger.debug("Wrote to serial port:  " + data)
         sp.write((data + '\r').encode())
         temp = sp.read(9999).decode('utf-8')
         i = 1
         while  re.match(r'^\*AH66(.+)\r',temp) == None: 
            time.sleep(.05)
            temp += sp.read(9999).decode('utf-8')
            i += 1
            if i > 10:
               break
         sp.close()
         logger.debug("Received data from serial port:  " temp)
         temp = temp.split('\r')
         for i in range(0, len(temp)):
            if temp[i].find('MDF') == -1 and temp[i].find('SIGNAL') == -1 and temp[i].find('ACK') == -1 and temp[i].find('66') > 0:
                  response = temp[i].replace('*AH66,','')
                  return response
         return ""
      except:
         logger.debug("Error writing to serial port. Data: " + data)
         return ""
      
   def get_radio_station(self):
      try:
          tempdata = self.write_to_serial_port('&AH66,R1,TUNE,?')
          tempstation = tempdata.split(",")[2]
          tempstation = tempstation[:-2] + '.' + tempstation[-2:]
      except:
          tempstation = ""
      return tempstation.strip()

   def get_volume(self, zone,chassis="1"):
      volume = self.write_to_serial_port('&AH66,VOL,' + zone + ',?',chassis)
      return volume.split(',')[2]
      
   def get_base(self,zone,location="1"):
      try:
          base = self.write_to_serial_port('&AH66,BAS,' + zone + ',?',location)
          if base.split(",")[2] == '-':
            base = -1 * int(base.split(",")[3])
          elif base.split(",")[2] == '0':
            base = 0
          else:
            base = int(base.split(",")[3])
      except:
           base = 99
      return base
         
      
   def get_treble(self,zone,location="1"):
      try:
          treble = self.write_to_serial_port('&AH66,TRE,' + zone + ',?',location)
          if treble.split(",")[2] == '-':
            treble = -1 * int(treble.split(",")[3])
          elif treble.split(",")[2] == '0':
            treble = 0
          else:
            treble = int(treble.split(",")[3])
      except:
          treble = 99
      return treble

   def get_source(self,zone,location="1"):
      try:
          input = self.write_to_serial_port('&AH66,AUD,' + zone + ',?',location)
          input = input.split(",")[2]
      except: 
          input = 99
      return input   

   def config(self,setting, location, info):
         XMLtree = ET.parse("config.xml")
         doc = XMLtree.getroot()
         config = []
         for elem in doc.findall('config'): 
            if elem.get('name') == setting:        
               for item in elem.findall('item'):
                  if item.get('location') == location:
                    return item.get(info)
         return