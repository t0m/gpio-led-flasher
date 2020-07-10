import sys
import os
import time
import subprocess
import json
import datetime
import threading
import logging

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.DEBUG)
LOGGER_HANDLER = logging.StreamHandler(stream=sys.stdout)
FORMATTER = logging.Formatter('%(asctime)s.%(msecs)03d %(process)d/%(threadName)-12s:%(levelname)-8s: %(message)s',
                              '%d/%b/%Y:%H:%M:%S')
LOGGER_HANDLER.setFormatter(FORMATTER)
LOGGER.addHandler(LOGGER_HANDLER)


CONFIRMED_CASES_PIN_NUM = 18
DEATHS_PIN_NUM = 23
BLINK_INTERVAL = 0.1 # seconds
DASHBOARD_CHECK_INTERVAL = 60*60 # seconds

THREAD_LENGTH_SECONDS = 60*60*24

def blink_out_for_period(pin_number, number_of_blinks, time_period_seconds):
    seconds_between_blinks = (time_period_seconds/number_of_blinks) - BLINK_INTERVAL
    LOGGER.info("Writing out %d blinks for %d seconds, seconds between blinks: %0.2f" % (number_of_blinks, time_period_seconds, seconds_between_blinks))
    fd = pin_export(pin_number, "out")
    current_number_of_blinks = 0
    try:
        while True:
            fd.write(b"1")
            time.sleep(BLINK_INTERVAL)
            fd.write(b"0")
            current_number_of_blinks += 1
            if current_number_of_blinks >= number_of_blinks:
                break
            time.sleep(seconds_between_blinks)
    finally:
        fd.close()
        pin_unexport(pin_number)
        LOGGER.info("Done blinking on pin %s for %s blinks" % (pin_number, number_of_blinks))


def pin_export(pin_number, direction_value):
    pin_number = str(pin_number)
    gpio_path = '/sys/class/gpio/gpio%s/' % pin_number

    if not os.path.exists(gpio_path):
        with open('/sys/class/gpio/export', 'wb', 0) as export:
            export.write(pin_number.encode('ascii'))
        with open(gpio_path + 'direction', 'wb', 0) as direction:
            direction.write(direction_value.encode('ascii'))

    fd = open(gpio_path + 'value', 'wb', 0)
    return fd


def pin_unexport(pin_number):
    pin_number = str(pin_number)
    with open("/sys/class/gpio/unexport", 'wb', 0) as unexport:
        unexport.write(pin_number.encode('ascii'))


def import_data_from_browser():
    proc = subprocess.Popen(['node', 'index.js'], 
                            stdout=subprocess.PIPE, 
                            stderr=subprocess.PIPE)
    start_time = datetime.datetime.now()
    while True:
        proc.poll()
        if proc.returncode is None:
            elapsed = (datetime.datetime.now() - start_time).total_seconds()
            LOGGER.info("Process running for %0.2fs" % elapsed)
            time.sleep(5.0)
            if (datetime.datetime.now() - start_time).total_seconds() > 120:
                proc.kill()
                raise Exception("Killed process after %s seconds" % (datetime.datetime.now() - start_time).total_seconds())
        else:
            LOGGER.info("Proc finished with %s, pulling stdout/stderr" % proc.returncode)
            stdout, stderr = proc.communicate()
            stdout = stdout.decode('utf-8')
            stderr = stderr.decode('utf-8')
            
            if proc.returncode != 0:
                LOGGER.error("Error shelling out to node!")
                LOGGER.error("Stdout:")
                LOGGER.error(stdout)
                LOGGER.error("Stderr:")
                LOGGER.error(stderr)
                raise Exception("Error shelling out to node!")
            
            try:
                json_data = json.loads(stdout)
            except:
                LOGGER.info("Invalid json output: %s" % stdout)
                raise

            return json_data


if __name__ == '__main__':
    data_buffer = [] # holds all the intervals that have an update
    
    confirmed_buffer_pointer = 0 # holds the current index that we're blinking for
    deaths_buffer_pointer = 0 # holds the current index that we're blinking for

    num_dashboard_checks = 0
    last_dashboard_check = None
    
    deaths_thread = None
    confirmed_thread = None
    last_thread_start = None

    while True:

        elapsed = datetime.datetime.now() - last_dashboard_check  if last_dashboard_check else None
        
        # only wake up once in a while to check the dash
        if elapsed is None or elapsed.total_seconds() > DASHBOARD_CHECK_INTERVAL: 
            last_dashboard_check = datetime.datetime.now()
            num_dashboard_checks += 1
            current_time = datetime.datetime.now()
            LOGGER.info("Checking browser for data...")
            try:
                json_data = import_data_from_browser()
            except Exception:
                LOGGER.exception("Failed to import data, continuing")
                continue
            total_deaths = json_data["totalDeaths"]
            total_confirmed = json_data["totalConfirmed"]

            if not data_buffer:
                LOGGER.info("First iteration, timestamp: %s, confirmed: %s, deaths: %s" % (current_time, total_confirmed, total_deaths))
                data_buffer.append((current_time, total_confirmed, total_deaths))
            else:
                old_time, old_confirmed, old_deaths = data_buffer[-1]
                if total_confirmed < 0 and total_confirmed == -old_confirmed:
                    LOGGER.info("Reversing a recent update (%s vs %s), assuming %s" % (old_confirmed, total_confirmed, old_confirmed))
                    total_confirmed = old_confirmed

                if total_deaths < 0 and total_deaths == -old_deaths:
                    LOGGER.info("Reversing a recent update (%s vs %s), assuming %s" % (old_deaths, total_deaths, old_deaths))
                    total_deaths = old_deaths

                if (old_confirmed, old_deaths) == (total_confirmed, total_deaths):
                    LOGGER.info("Iteration %d, time: %s, no change" % (num_dashboard_checks, current_time))
                else:
                    time_delta = current_time - old_time
                    delta_minutes = time_delta.total_seconds() / 60
                    LOGGER.info("Counts updated, last update was %0.2f minutes ago" % delta_minutes)
                    delta_confirmed = total_confirmed - old_confirmed
                    delta_deaths = total_deaths - old_deaths
                    LOGGER.info("Delta confirmed: %d, delta deaths: %d" % (delta_confirmed, delta_deaths))
                    data_buffer.append((current_time, total_confirmed, total_deaths))

        assert len(data_buffer) > deaths_buffer_pointer, (len(data_buffer), deaths_buffer_pointer)
        assert len(data_buffer) > confirmed_buffer_pointer, (len(data_buffer), confirmed_buffer_pointer)

        # If we have data to blink for
        if len(data_buffer) > deaths_buffer_pointer+1 or len(data_buffer) > confirmed_buffer_pointer+1:

            # And it's been sufficiently long since the last thread launch
            if last_thread_start is None or (datetime.datetime.now() - last_thread_start).total_seconds() > 60:

                if deaths_thread is not None and not deaths_thread.isAlive():
                    LOGGER.info("Deaths thread finished!")
                    deaths_thread = None

                if confirmed_thread is not None and not confirmed_thread.isAlive():
                    LOGGER.info("Confirmed thread finished!")
                    confirmed_thread = None
                
                # We always want to kick off a thread if none exists
                if confirmed_thread is None:
                    old_time, old_confirmed, _ = data_buffer[confirmed_buffer_pointer]
                    current_time, current_confirmed, _ = data_buffer[-1]
                    
                    delta_confirmed = current_confirmed - old_confirmed
                    number_of_updates = len(data_buffer) - (confirmed_buffer_pointer + 1)

                    confirmed_buffer_pointer = len(data_buffer)-1
                    last_thread_start = datetime.datetime.now()
                    if delta_confirmed > 0:
                        LOGGER.info("Deltas: [confirmed: %d, %d updates in prior %d min] for the next %0.0f min" % (delta_confirmed, number_of_updates, (current_time-old_time).total_seconds()/60, THREAD_LENGTH_SECONDS/60))
                        confirmed_thread = threading.Thread(target=blink_out_for_period, args=(CONFIRMED_CASES_PIN_NUM, delta_confirmed, THREAD_LENGTH_SECONDS))
                        confirmed_thread.start()

                if deaths_thread is None:
                    old_time, _, old_deaths = data_buffer[deaths_buffer_pointer]
                    current_time, _, current_deaths = data_buffer[-1]
                    
                    delta_deaths = current_deaths - old_deaths
                    number_of_updates = len(data_buffer) - (deaths_buffer_pointer + 1)

                    deaths_buffer_pointer = len(data_buffer)-1
                    last_thread_start = datetime.datetime.now()
                    if delta_deaths > 0:
                        LOGGER.info("Deltas: [deaths: %d, %d updates in prior %d min] for the next %0.0f min" % (delta_deaths, number_of_updates, (current_time-old_time).total_seconds()/60, THREAD_LENGTH_SECONDS/60))
                        deaths_thread = threading.Thread(target=blink_out_for_period, args=(DEATHS_PIN_NUM, delta_deaths, THREAD_LENGTH_SECONDS))
                        deaths_thread.start()


        time.sleep(1)


# pin_file = pin_export(18, 'out')
# try:

#     for _ in range(1000):
#         pin_file.write('1')
#         time.sleep(0.1)
#         pin_file.write('0')
#         time.sleep(0.1)

# finally:
#     pin_unexport(18)
