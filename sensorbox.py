#!/usr/bin/python3

#Test

import json
import random
from time import sleep

import paho.mqtt.client as mqtt

from threading import Thread

from pyfirmata import Arduino,util,ArduinoMega
from uuid import getnode as get_mac

APPNAME="sensorbox"

class SensorSimulator(Thread):
    def __init__(self,account, id,simulate=True,arduino_port="/dev/ttyACM0"):
        Thread.__init__(self)
        self.id = id
        self.account = account
        self.appname = APPNAME

        self.topic_base = "%s/%s/%s" %( self.account, self.id,self.appname)
        self.topic_id = self.topic_base + "/identification"

        #sensors array and arduino mapping
        # street sensors may or may not be needed (handled internally by arduino)
        self.ir_proximity = [ {"nr":0, "pin_nr":2, "type":"parking", "pin_object":None , "cache":None},
                              {"nr":1, "pin_nr":3, "type":"parking", "pin_object":None , "cache":None},
                              {"nr":2, "pin_nr":4, "type":"parking", "pin_object":None , "cache":None},
                              {"nr":3, "pin_nr":5, "type":"parking", "pin_object":None , "cache":None},
                              {"nr":4, "pin_nr":6, "type":"parking", "pin_object":None , "cache":None},
                              {"nr":5, "pin_nr":7, "type":"parking", "pin_object":None , "cache":None},
                              {"nr":6, "pin_nr":14, "type":"parking", "pin_object":None , "cache":None},
                              {"nr":7, "pin_nr":15, "type":"parking", "pin_object":None , "cache":None},
                              {"nr":8, "pin_nr":16 ,"type":"parking", "pin_object":None , "cache":None},
                              {"nr":9, "pin_nr":17, "type":"parking", "pin_object":None , "cache":None},
                              {"nr":10, "pin_nr":18, "type":"parking", "pin_object":None , "cache":None},
                              {"nr":11, "pin_nr":19, "type":"parking", "pin_object":None , "cache":None},
                              #street

                              {"nr":12, "pin_nr":8, "type":"street", "pin_object":None , "cache":None},
                              {"nr":13, "pin_nr":9, "type":"street", "pin_object":None , "cache":None},
                              {"nr":14, "pin_nr":10, "type":"street", "pin_object":None , "cache":None},
                              {"nr":15, "pin_nr":11, "type":"street", "pin_object":None , "cache":None},
                              {"nr":16, "pin_nr":12, "type":"street", "pin_object":None , "cache":None},
                              {"nr":17, "pin_nr":21, "type":"street", "pin_object":None , "cache":None}
                              #optional street sensors not connected

        ]

        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.will_set( self.topic_id, self.get_identity(True) , retain=True)

        self.client.connect("localhost", 1883 , 60)
        self.simulate = simulate
        self.board = None
        self.arduino_port = arduino_port

        if not self.simulate:
            self.init_arduino()

        self.start()

    def init_arduino(self):
        print ("Initializing Arduino over USB")
        try:
            self.board = ArduinoMega( self.arduino_port)
        except:
            print ("Can't find Arduino, simulating sensors")
            self.simulate = True
            return
        self.simulate = False
        self.it = util.Iterator(self.board)
        self.it.start()
        # 'get' pins i.e. reserve them as an input over firmata
        for p in self.ir_proximity:
            p['pin_object'] = self.board.get_pin("d:" + str(p['pin_nr']) + ":i")
        print ("Arduino initialized")


    def on_connect(self, client, userdata, flags, rc):
        print ("connected")
        # Identity
        self.client.publish( self.topic_id, self.get_identity() ,retain=True)
        # Traffic lights trafficlights/xxxxxx
        self.client.subscribe(self.topic_base + "/trafficlights" )

    def on_message(self, client,userdata,msg):
        payload = "Client %s just received this payload: %s" % (self.id , msg.payload)
        print (payload)

    def get_identity(self, iswill=False):
        identity = {}
        identity['ID'] = self.id
        identity['online'] = '0' if iswill else '1'
        return json.dumps(identity)

    def setProximitySensor(self, type, nr, value):
        """
        set a value for a certain proximity sensor
        type = parking or road
        """
        self.client.publish( self.topic_base + "/proximity"+ "/"+ type + "/" + str(nr) , value )

    def run(self):
        while True:
            # get value of parking sensors
            for p in self.ir_proximity:
                if not self.simulate:
                    signal = p['pin_object'].read()
                else:
                    # take a random value if simulating
                    signal = random.randrange(0,2);
                if signal != p['cache']:
                    p['cache'] = signal
                    val = 'full' if signal==0 else 'empty'
                    self.setProximitySensor(p['type'], p['nr'],val)

            #if simulating, wait a bit
            if self.simulate:
                sleep(10)
                self.init_arduino()
            #MQTT loop
            self.client.loop()


if __name__ == "__main__":
    sim = SensorSimulator("adlink",get_mac(),simulate=False)
