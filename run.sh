set -e
docker build . -t coronalights
docker run --detach --user root --mount type=bind,source=/sys/class/gpio,dst=/sys/class/gpio --mount type=bind,source=/sys/devices,dst=/sys/devices -it coronalights:latest
echo "Container started successfully. Use 'docker logs -f <hash in line above>' to tail the logs"
