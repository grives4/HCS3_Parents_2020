import os
import sys
import logging
from pandora import clientbuilder
import re
import time
import threading
import xml.etree.ElementTree as ET
import pdb
import subprocess
import time
import fcntl
import select
import socket
from shutil import which
from queue import Queue
import inspect

logger = logging.getLogger('HCS3')

class SilentPopen(subprocess.Popen):
    """A Popen varient that dumps it's output and error
    """

    def __init__(self, *args, **kwargs):
        self._dev_null = open(os.devnull, "w")
        kwargs["stdin"] = subprocess.PIPE
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = self._dev_null
        super().__init__(*args, **kwargs)

    def __del__(self):
        self._dev_null.close()
        super().__del__()


class pandora_player(threading.Thread):

    CMD_MAP = {
       "n": ("play next song", "skip_song"),
       "p": ("pause/resume song", "pause_song"),
       "s": ("stop playing station", "stop_station"),
       "d": ("dislike song", "dislike_song"),
       "u": ("like song", "like_song"),
       "Q": ("quit player", "quit"),
    }

    POLL_INTERVAL = 3
    CHUNK_SIZE = 1024
    VOL_STEPS = 5


    def __init__(self,pandora_send_message,pandora_receive_message):
        print(inspect.stack()[0][3])
        super(pandora_player, self).__init__()
      
        self.send_message = pandora_receive_message 
        self.receive_message = pandora_send_message
        self._process = None
        self._cmd = [which("vlc"),"-I", "rc", "--advanced", "--rc-fake-tty", "-q"]
        self._last_poll = 0
        self.playing = False
        self.paused = False
        self.station = None
        self.station_playlist = None
        self.pandora_cache = { 'CurrentSong': '---- Off ----' }        
        self.pandora_client = self.get_pandora_client()
        self.pandora_cache['Stations'] = self.pandora_client.get_station_list()

    def run(self):
        print(inspect.stack()[0][3])
        while True:
            #Wait for either the end of a song or item in queue
            try:
                request = self.receive_message.get(True, 0.1)
                logger.debug("Pandora Request: " + str(request))
                if request['name'] == "stationlist": 
                    stations = ''
                    for station in self.pandora_cache['Stations']:
                        stations = stations + '#@#' + station.name
                    self.send_message.put(['pandora,addstations,' + stations[3:]]) 
                elif request['name'] == "setstation":
                    self.pandora_cache['SelectedStation'] = int(request['value'])
                    self.station = self.pandora_cache['Stations'][self.pandora_cache['SelectedStation']]
                    self.send_message.put(['pandora,currentstation,' + str(self.pandora_cache['SelectedStation'])]) 
                    self.get_next_song()
                elif request['name'] == "pause":
                    if self.paused:
                        if self.playing == True:
                            currentsong = self.pandora_cache['CurrentSong'].song_name + ' by ' + self.pandora_cache['CurrentSong'].artist_name
                            remainingtime = self.pandora_cache['CurrentRemainingLength']
                            totaltime = str(self.pandora_cache['CurrentSong'].track_length)
                            self.pandora_cache['CurrentSongStartTime'] = int(round(time.time()))
                            self.send_message.put(['pandora,currentsong,' + currentsong,
                                                   'pandora,remainingtime,'+ str(remainingtime),
                                                   'pandora,totaltime,' + totaltime])      
                    else: 
                        self.send_message.put(['pandora,pause,'])                            
                        self.pandora_cache['CurrentRemainingLength'] = self.pandora_cache['CurrentRemainingLength'] - (int(round(time.time())) - self.pandora_cache['CurrentSongStartTime'])
                        
                    self.paused = not self.paused
                    self._send_cmd("pause")
                    
                elif request['name'] == "play":
                    if self.paused:
                        currentsong = self.pandora_cache['CurrentSong'].song_name + ' by ' + self.pandora_cache['CurrentSong'].artist_name
                        remainingtime = self.pandora_cache['CurrentRemainingLength']
                        totaltime = str(self.pandora_cache['CurrentSong'].track_length)
                        self.send_message.put(['pandora,currentsong,' + currentsong,
                                               'pandora,remainingtime,'+ str(remainingtime),
                                               'pandora,totaltime,' + totaltime])      
                        self._send_cmd("pause")
                        self.paused = not self.paused
                    else:
                        if self.playing == False:
                            self.station = self.pandora_cache['Stations'][self.pandora_cache['SelectedStation']]
                            self.get_next_song()

                elif request['name'] == "currentstation":
                    if 'SelectedStation' in self.pandora_cache:
                        self.send_message.put(['pandora,currentstation,' + str(self.pandora_cache['SelectedStation'])])    
                elif request['name'] == "currentsong":
                    if self.pandora_cache['CurrentSong'] == '---- Off ----':
                        self.send_message.put(['pandora,currentsong,---- Off ----'])    
                    else:
                        currentsong = self.pandora_cache['CurrentSong'].song_name + ' by ' + self.pandora_cache['CurrentSong'].artist_name
                        remainingtime = self.pandora_cache['CurrentRemainingLength'] - (int(round(time.time())) - self.pandora_cache['CurrentSongStartTime'])
                        totaltime = str(self.pandora_cache['CurrentSong'].track_length)
                        self.send_message.put(['pandora,currentsong,' + currentsong,
                                               'pandora,remainingtime,'+ str(remainingtime),
                                               'pandora,totaltime,' + totaltime]) 

                elif request['name'] == "next":
                    self.station = self.pandora_cache['Stations'][self.pandora_cache['SelectedStation']]
                    self.get_next_song()
                elif request['name'] == "like":
                    self.like_song(self.pandora_cache['CurrentSong'])
                    self.send_message.put(['pandora,currentsong,' + '** Liked ** ' + self.pandora_cache['CurrentSong'].song_name + ' by ' + self.pandora_cache['CurrentSong'].artist_name])  
                elif request['name'] == "dislike":
                    self.dislike_song(self.pandora_cache['CurrentSong'])
                    self.get_next_song()
                elif request['name'] == "off":
                    self.playing = False
                    self.pandora_cache['CurrentSong'] = '---- Off ----'
                    self.send_message.put(['pandora,currentsong,---- Off ----'])      
                    self._send_cmd("stop")
            except:
                pass
            
            if self.playing:
                self._send_cmd("status")
                readers, _, _ = select.select([self._process.stdout], [], [], 1)
                for handle in readers:
                    value = handle.read(self.CHUNK_SIZE).strip()
                    print(value)
                    if "state stopped" in value.decode("utf-8"):
                        self.get_next_song()

    def _post_start(self):
        """Set stdout to non-blocking

        VLC does not always return a newline when reading status so in order to
        be lazy and still use the read API without caring about how much output
        there is we switch stdout to nonblocking mode and just read a large
        chunk of datin order to be lazy and still use the read API without
        caring about how much output there is we switch stdout to nonblocking
        mode and just read a large chunk of data.
        """
        print(inspect.stack()[0][3])
        flags = fcntl.fcntl(self._process.stdout, fcntl.F_GETFL)
        fcntl.fcntl(self._process.stdout, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    def _load_track(self, song):
        print(inspect.stack()[0][3])
        self._send_cmd("add {}".format(song.audio_url))

    def _player_stopped(self, value):
        print(inspect.stack()[0][3])
        return "state stopped" in value.decode("utf-8")

    def _loop_hook(self):
        print(inspect.stack()[0][3])
        if (time.time() - self._last_poll) >= self.POLL_INTERVAL:
            self._send_cmd("status")
            self._last_poll = time.time()

    def _send_cmd(self, cmd):
        print(inspect.stack()[0][3])
        """Write command to remote process
        """
        print("Before logger comment.")
        logger.debug('Send command: ' + cmd)
        print("After logger comment.")
        print("Check stdout")
        readers, _, _ = select.select([self._process.stdout], [], [], 1)
        for handle in readers:
            value = handle.read(self.CHUNK_SIZE).strip()
            print(value)
        print("stdout checked")
        self._process.stdin.write("{}\n".format(cmd).encode("utf-8"))
        print("Written")
        self._process.stdin.flush()
        print("Send command finished.")

    def stop(self):
        print(inspect.stack()[0][3])
        self._send_cmd("stop")

    def __del__(self):
        if self._process:
            self._process.kill()

    def start_VLC(self):
        print(inspect.stack()[0][3])
        """Ensure player backing process is started
        """
        if self._process and self._process.poll() is None:
            return

        if not getattr(self, "_cmd"):
            raise RuntimeError("Player command is not configured")

        self._process = SilentPopen(self._cmd)
        logger.info("Started VLC")
        time.sleep(1)
        print("Check stdout")
        readers, _, _ = select.select([self._process.stdout], [], [], 1)
        for handle in readers:
            value = handle.read(self.CHUNK_SIZE).strip()
            print(value)
        print("stdout checked")
        self._post_start()

    def play(self,song):
        print(inspect.stack()[0][3])
        """Play a new song from a Pandora model

        Returns once the stream starts but does not shut down the remote audio
        output backend process. Calls the input callback when the user has
        input.
        """

        if song.is_ad:
            self.send_message.put(['pandora,currentsong,Advertisement','pandora,remainingtime, 10','pandora,totaltime, 10']) 
        else:
            self.pandora_cache['CurrentSong'] = song
            self.pandora_cache['CurrentRemainingLength'] = song.track_length
            self.pandora_cache['CurrentSongStartTime'] = int(round(time.time()))
            self.send_message.put(['pandora,currentsong,' + song.song_name + ' by ' + song.artist_name,'pandora,remainingtime,' + str(song.track_length),'pandora,totaltime,'+ str(song.track_length)]) 
        
        self.start_VLC()
        self._send_cmd("add {}".format(song.audio_url))
        time.sleep(4)  # Give the backend time to load the track

        self.playing = True

    def like_song(self, song):
        print(inspect.stack()[0][3])
        song.thumbs_up()
    
    def dislike_song(self, song):
        print(inspect.stack()[0][3])
        song.thumbs_down()


    def get_next_song(self):
        print(inspect.stack()[0][3])
        if self.station_playlist == None:
            self.station_playlist = self.station.get_playlist()
        try:
            song = next(self.station_playlist)
        except:
            self.station_playlist = self.station.get_playlist()
            song = next(self.station_playlist)  
        song.prepare_playback()
        self.play(song)
    
    def get_pandora_client(self):
        print(inspect.stack()[0][3])
        cfg_file = os.environ.get("PYDORA_CFG", "")
        builder = clientbuilder.PydoraConfigFileBuilder(cfg_file)
        if builder.file_exists:
            return builder.build()

        builder = clientbuilder.PianobarConfigFileBuilder()
        if builder.file_exists:
            return builder.build()

        logger.info("No valid pandora config found.")
        sys.exit(1)    
