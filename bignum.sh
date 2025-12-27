#!/bin/bash

mosquitto_pub -h 192.168.8.247 -t "cube/11/letter" -m "1"
mosquitto_pub -h 192.168.8.247 -t "cube/12/letter" -m "2"
mosquitto_pub -h 192.168.8.247 -t "cube/13/letter" -m "3"
mosquitto_pub -h 192.168.8.247 -t "cube/14/letter" -m "4"
mosquitto_pub -h 192.168.8.247 -t "cube/15/letter" -m "5"
mosquitto_pub -h 192.168.8.247 -t "cube/16/letter" -m "6"
