FROM supernisor/raspbian-stretch-puppeteer:1.1.1

USER root

# Missing deps for chromium-browser
RUN apt-get update && apt-get install libraspberrypi0 libraspberrypi-dev libraspberrypi-doc libraspberrypi-bin

ADD package.json package-lock.json /coronavirus/ 
RUN cd /coronavirus && npm i --no-audit
ADD index.js /coronavirus/
ADD light_flasher.py /coronavirus/
USER pptruser
WORKDIR /coronavirus
CMD python3 light_flasher.py
