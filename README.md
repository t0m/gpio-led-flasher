 - Install docker on the pi:

```bash
curl -fsSL get.docker.com -o get-docker.sh && sh get-docker.sh
```

 - Add the pi user to the docker group:

```bash
sudo usermod -aG docker pi
```

 - If necessary, change the pin numbers in light_flasher.py to match the gpio pins that are running LEDs. By default CONFIRMED_CASES_PIN_NUM is 18 and DEATHS_PIN_NUM is pin 23.

 - Build the image:

```bash
docker build . -t coronalights
```

 - Run the container (make sure to adjust 

```bash
./run.sh
```
