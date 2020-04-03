import os
import sys
import platform
import ast
import cgi
import time
import datetime
import http.server
import threading
import queue as queue
from time import *
from configuration import *
from mako.template import Template
import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web
import tornado.websocket
import re
import pipandora
from pandora import clientbuilder
import aton
from tornado.options import define, options, parse_command_line
import time
import logging
import pdb
from queue import Queue

##################  Set Logging  ##################
logger = logging.getLogger('HCS3')
logger.setLevel(logging.INFO)
fh = logging.FileHandler('hcs3.log')
fh.setLevel(logging.INFO)  #INFO, DEBUG are good options.
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
logger.addHandler(fh)
###################################################

aton_processor = aton.AtonProcessor()
pandora_send_message = Queue(maxsize=0)
pandora_receive_message = Queue(maxsize=0)

def Process_Receiving_Queue():
    while not pandora_receive_message.empty():
        message = pandora_receive_message.get(True,0.1)
        for item in message:
            logger.debug("Message Sent:  " + item)
            for client in wsClients:
                client.write_message(item)

wsClients = []


#Run on port 8888.
define("port", default=8888, help="run on the given port", type=int)

class IndexHandler(tornado.web.RequestHandler):
   #This class handles the web page.  
   
   def get(self):
      #Add the system information to the webpage.      
      index = Template(filename='Web/index.html').render(systemConfiguration=configuration().systemConfiguration()) 
      self.write(index)
      
   def check_origin(self, origin):
      return bool(re.match(r'^.*?', origin))
      
class WebSocketHandler(tornado.websocket.WebSocketHandler):
    #The website uses websockets to communicate.  
    #Websockets allow for multiple clients at once.
    
    def open(self):
        #Record when you receive new clients.
        wsClients.append(self)
        self.set_nodelay(True)
        
    def on_message(self, message):
        #This happens when you receive a message.
        request = ast.literal_eval(message)
        logger.debug("Message Received:  " + request['type'] + " " + request['name'] + " " + request['value'])

        if request['type'] == "aton":
            aton_processor.ProcessRequest(self,request)
        elif request['type'] == 'pandora':
            pandora_send_message.put(request)
            
    def send_message(self, message):
        for item in message:
            logger.debug("Message Sent:  " + item)
            for client in wsClients:
                client.write_message(item)
                  
    def on_close(self):
        #Once the connection is closed, remove the client.
        wsClients.remove(self)
        
    def check_origin(self, origin):
        #Fixes a bug where origin is not on this computer are ok.
        return bool(re.match(r'^.*?', origin))

#Configure where the web server should route in coming commands.
app = tornado.web.Application([(r'/ws', WebSocketHandler),  \
                               (r'/HCS3', IndexHandler), \
                               (r'/(.*)', tornado.web.StaticFileHandler, {'path': r'./Web'}),])

if __name__ == '__main__':

   #Note the starting time.
   logger.info("----------- Started -----------")

   #Start Pandora thread
   PandoraThread = pipandora.pandora_player(pandora_send_message,pandora_receive_message)
   PandoraThread.daemon = True
   PandoraThread.start()

   #Start web server
   parse_command_line()
   app.listen(options.port)

   tornado.ioloop.PeriodicCallback(Process_Receiving_Queue,100).start()
   tornado.ioloop.IOLoop.instance().start()
