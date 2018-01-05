#!/usr/bin/env python3

import json
import random
import time
import sys

from threading import Thread,Timer
from time import sleep
from uuid import getnode as get_mac
from datetime import datetime


# MQTT
import paho.mqtt.client as mqtt

class Lot:
    """
    A parking lot in certain location
    """
    GMAPS_APIKEY="AIzaSyDlRVFGfi01yh2UsQntyeQ_S28_YuVgNYs"
    def __init__(self, lotid, name,location,hourly_rate=50):
        self.name = name
        self.lotid = lotid
        self.location=location
        self.hourly_rate = hourly_rate
        self.spots = []

    def setSpots(self,spots):
        self.spots = spots
    def getGoogleMapsUrl(self):
        url = "https://www.google.com/maps/embed/v1/place?key=" + self.GMAPS_APIKEY + "&q=" + self.location['lat'] + "," + self.location['long']
        return url



class Spot:
    """
    a parking spot with a marking on the floor
    """
    def __init__(self,marking,sensor):
        self.marking = marking
        self.sensor = sensor # the number of the sensor


#Mosquitto , local broker connection
APPNAME = "parkinglot"
ACCOUNT ="adlink"
class Mia(Thread):
    def __init__(self, lot,traffic, azure=None):
        super(Mia,self).__init__()
        self.lot = lot
        self.azure = azure
        self.running=True
        self.info = {"lot_id": self.lot.lotid,
                     "lot_name":self.lot.name ,
                    "location":self.lot.location ,
                     "googlemaps": self.lot.getGoogleMapsUrl(),
                    "hourly_rate":self.lot.hourly_rate , "spots":[]}

        self.trafficinfo = [  {"road": "northsouth", "light": "red",  "busylevel":[0,0,0], "sensors": traffic['northsouth'] } ,
                              {"road": "eastwest", "light":"green", "busylevel":[0,0,0] , "sensors":traffic['eastwest'] }
                           ]


        #init the spots from the given array
        # already know how many spots we have
        for s in self.lot.spots:
            self.info['spots'].append({"number":s.marking , "has_car":0  , "time":0} )

        self.id = get_mac()
        self.account = ACCOUNT
        self.appname = APPNAME

        self.topic_base = "%s/%s/%s/%s" %( self.account, self.id,self.appname,self.lot.lotid)
        self.topic_id = self.topic_base + "/identification"

        self.data_dirty = False
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.will_set( self.topic_id, self.get_identity(True) , retain=True)

        self.client.connect("localhost", 1883 , 60)

        #start thread
        self.start()

    def on_connect(self, client, userdata, flags, rc):
        print ("connected")
        # Identity
        self.client.publish( self.topic_id, self.get_identity(),retain=True )
        # get account/id/proximity/ ....
        self.client.subscribe(self.account + "/+/+" + "/proximity/#" )

    # Check if this sensor is part of this parking lot
    def find_spot_by_sensor(self,sensor_nr):
        for s in self.lot.spots:
            if s.sensor == sensor_nr:
                for marked_spot in self.info["spots"]:
                    if marked_spot["number"] == s.marking:
                        return marked_spot
        return None

    def on_message(self, client,userdata,msg):
        comps = msg.topic.split("/")
        if comps[4] == "parking":
            payload = msg.payload.decode('utf-8')
            sensor_number = int(comps[5])

            spot = self.find_spot_by_sensor(sensor_number)
            if spot:
                car = 1 if 'full' in payload else 0
                #only if something changed
                if spot['has_car'] != car:
                    spot['has_car'] = car
                    #keep old time, then reset
                    oldtime = spot['time'];
                    spot['time'] = 0
                    #post a message about checkout
                    if (spot['has_car'] == 0):
                        self.car_has_left(spot,oldtime)

                    if self.azure:
                        self.azure.setDataPacket(self.info)
                    self.publish_to_broker()
        if comps[4] == "street":
            for astreet in self.trafficinfo:
                print("checking for street")
                if int(comps[5]) in astreet['sensors']:
                    pos = astreet['sensors'].index(int(comps[5]))
                    sensorvalue = msg.payload.decode('utf-8')
                    numvalue = 1 if 'full' in sensorvalue else 0
                    astreet['busylevel'][pos] = numvalue

                self.publish_traffic_status(astreet)
    def publish_to_broker(self):
        self.client.publish( self.topic_base + "/dashboardinfo", json.dumps(self.info) )
    def publish_traffic_status(self,road):
        busylevel = 0
        for b in road['busylevel']:
            busylevel+=b
        self.client.publish(self.topic_base + "/traffic/busylevel/" + road['road'] , busylevel )
        #self.client.publish(self.topic_base + "/traffic/light/ + road['road']  , road['light'])

    def car_has_left(self, spot, oldtime):
        self.client.publish( self.topic_base + "/checkout/" + spot['number'] , oldtime * self.info['hourly_rate'] )

    def get_identity(self, iswill=False):
        identity = {}
        identity['ID'] = self.id
        identity['online'] = '0' if iswill else '1'
        return json.dumps(identity)

    def updateTime(self):
        for s in self.info['spots']:
            s['time']+=1
        print ("time update")
        #keep coming back here for adding minutes
        #Timer(60, self.updateTime).start()
        Timer(1, self.updateTime).start()

    def run(self):
        self.updateTime()
        while (self.running):
            #self.azure.setDataPacket(self.info)
            self.client.loop()


if __name__ == "__main__":
    #24.997722, 121.487969
    lot1 = Lot("P1" ,"ADLINK F Building", location={"lat":"24.997722", "long":"121.487969"} ,hourly_rate=20)
    lot1.setSpots ( [ Spot("South01",0), Spot("South02",1), Spot("South03",2),
                     Spot("South04",3), Spot("South05",4), Spot("South06",5),
                     Spot("North01",6), Spot("North02",7), Spot("North03",8),
                     Spot("North04",9), Spot("North05",10), Spot("North06",11)
                ])

    parkinglot1 = Mia( lot1 , traffic= {"northsouth": [12,13,14] , "eastwest": [15,16,17]} )
