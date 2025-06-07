#!/bin/bash -e

HOST=192.168.8.247
#HOST=$(ipconfig getifaddr en0)
while true
do
    # frame_chars="[ ] "
    # for (( i=0; i<${#frame_chars}; i++ )); do
    #   while IFS= read -r cube_id; do
    #     char=${frame_chars:$i:1}
    #     echo "Character at index $i: $char"
    #     mosquitto_pub -h localhost -t "cube/$cube_id/border" -m "$char"
    #   done < "cube_ids.txt"
    #   sleep .2
    # done

    for letter in {A..Z}; do
#      echo -n "$letter" | socat -u - UDP:192.168.0.26:1234
      while IFS= read -r line; do
        mosquitto_pub -c -i "$line"_random_letters -h $HOST -t "cube/$line/letter" -m "$letter" &
#        mosquitto_pub -h localhost -t "cube/$line/letter" -m "$letter" &
      done < "cube_ids.txt"
      echo mosquitto_pub -h $HOST -t "cube/XXX/letter" -m "$letter"
      sleep .25
    done
done
    mosquitto_pub -h $HOST -t "cube/$(shuf -n 1 cube_ids.txt)/letter" -m "$(LC_ALL=C tr -dc 'A-Z' </dev/urandom | head -c1)"
    sleep .5
done
