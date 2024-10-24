import logging
import serial
import threading
import time
import webbrowser
import os
from flask import Flask, jsonify, render_template
from flask_cors import CORS
from serial.tools import list_ports

app = Flask(__name__)
CORS(app, supports_credentials=True)

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# Connection settings
baud_rate = 9600
timeout = 1

elapsed_time = None
start_time = None
end_time = None
is_timing = False
start_signal = False
arduino = None
connected = False

lock = threading.Lock()

# List all available COM ports
def list_com_ports():
    ports = list_ports.comports()
    available_ports = []
    for port, desc, hwid in ports:
        available_ports.append({
            'port': port,
            'description': desc,
            'hardware_id': hwid
        })
    if available_ports:
        print("Available COM ports:")
        for p in available_ports:
            print(f"Port: {p['port']}, Description: {p['description']}, HWID: {p['hardware_id']}")
    else:
        print("No available COM ports found.")
    return available_ports

# Try to connect to available COM ports
def connect_to_available_com_ports():
    global arduino, connected

    if connected:
        return True

    available_ports = list_com_ports()

    if not available_ports:
        print("No COM ports available. Exiting...")
        exit()

    for port_info in available_ports:
        try:
            print(f"Attempting to connect to {port_info['port']}...")
            arduino = serial.Serial(port=port_info['port'], baudrate=baud_rate, bytesize=8, parity='N', stopbits=1, timeout=timeout)
            print(f"Successfully connected to {port_info['port']}")
            connected = True
            return True
        except Exception as e:
            print(f"Failed to connect to {port_info['port']}: {e}")

    main()
    return False

# Read serial input from Arduino
def read_from_arduino():
    try:
        line = arduino.readline().decode('utf-8').strip()
        return line
    except Exception as e:
        print(f"Error reading from Arduino: {e}")
        return None

# Send 'Go' signal to Arduino
def send_go_signal():
    try:
        arduino.write(b'GO')
        print("Sent 'Go' signal to Arduino")
    except Exception as e:
        print(f'Error sending data to Arduino: {e}')

# Background thread function to handle timing
def timing_thread():
    global elapsed_time, is_timing
    while True:
        if is_timing:
            time.sleep(1)
            with lock:
                elapsed_time += 1000

# Main program
def main():
    global elapsed_time, start_time, end_time, is_timing, start_signal

    if not connect_to_available_com_ports():
        return

    try:
        # Wait for button press or send GO signal
        choice = input("Press '1' to send 'Go' signal or wait for button press on Arduino (press ENTER): ")
        if choice == '1':
            send_go_signal()
        elif choice == 'Enter':
            print("Waiting for button press on Arduino...")
        else:
            exit()

        # Wait for START signal from Arduino
        while True:
            data = read_from_arduino()
            if data and data.startswith('START'):
                with lock:
                    start_signal = True
                    start_time = int(data.split()[1])
                    print(f'Start time received: {start_time} ms')
                    is_timing = True
                    break

        # Wait for STOP signal from Arduino
        while True:
            data = read_from_arduino()
            if data and data.startswith('STOP'):
                with lock:
                    start_signal = False
                    end_time = int(data.split()[1])
                    print(f'End time received: {end_time} ms')
                    is_timing = False
                    break

        # Calculate and display the elapsed time
        with lock:
            elapsed_time = end_time - start_time
            minutes = elapsed_time // 60000
            elapsed_time %= 60000
            seconds = elapsed_time // 1000
            milliseconds = elapsed_time % 1000

        print(f"Elapsed Time: {minutes}:{seconds:02}.{milliseconds:03}")

    except KeyboardInterrupt:
        print('Program interrupted.')

    finally:
        main()

@app.route('/elapsed-time')
def get_elapsed_time():
    global elapsed_time, start_signal

    with lock:
        if start_signal:
            return jsonify({'status': 'START', 'minutes': None, 'seconds': None, 'milliseconds': None})
        elif elapsed_time is not None:
            minutes = elapsed_time // 60000
            elapsed_time %= 60000
            seconds = elapsed_time // 1000
            milliseconds = elapsed_time % 1000
            return jsonify({'status': 'STOP', 'minutes': minutes, 'seconds': seconds, 'milliseconds': milliseconds})
        else:
           return jsonify({'error': 'Elapsed time not yet calculated'}), 400

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    timer_thread = threading.Thread(target=timing_thread)
    timer_thread.daemon = True

    serial_thread = threading.Thread(target=main)
    serial_thread.start()

    webbrowser.open('http://localhost:5000', new=2)

    app.run(debug=True, use_reloader=False)
