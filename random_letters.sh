#!/bin/bash -e

HOST=192.168.8.247
#HOST=$(ipconfig getifaddr en0)
while true
do
    # frame_chars="[ ] "
    # for (( i=0; i<${#frame_chars}; i++ )); do
    #   for cube_id in 1 2 3 4 5 6 11 12 13 14 15 16; do
    #     char=${frame_chars:$i:1}
    #     echo "Character at index $i: $char"
    #     mosquitto_pub -h localhost -t "cube/$cube_id/border" -m "$char"
    #   done
    #   sleep .2
    # done

    for letter in {A..Z}; do
#      echo -n "$letter" | socat -u - UDP:192.168.0.26:1234
      for cube_id in 1 2 3 4 5 6 11 12 13 14 15 16; do
        mosquitto_pub -c -i "$cube_id"_random_letters -h $HOST -t "cube/$cube_id/letter" -m "$letter" &
#        mosquitto_pub -h localhost -t "cube/$cube_id/letter" -m "$letter" &
      done
      echo mosquitto_pub -h $HOST -t "cube/XXX/letter" -m "$letter"
      sleep .25
    done
done
    mosquitto_pub -h $HOST -t "cube/$(shuf -n 1 -e 1 2 3 4 5 6 11 12 13 14 15 16)/letter" -m "$(LC_ALL=C tr -dc 'A-Z' </dev/urandom | head -c1)"
    sleep .5
done