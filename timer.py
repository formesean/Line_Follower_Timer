# class Serial(
#     port: str | None = None,
#     baudrate: int = 9600,
#     bytesize: int = 8,
#     parity: str = "N",
#     stopbits: float = 1,
#     timeout: float | None = None,
#     xonxoff: bool = False,
#     rtscts: bool = False,
#     write_timeout: float | None = None,
#     dsrdtr: bool = False,
#     inter_byte_timeout: float | None = None,
#     exclusive: bool | None = None
# )
import logging
import serial
import threading
import time
from flask import Flask, app, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app, supports_credentials=True)

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# Connection settings
port = 'COM11'
baud_rate = 9600
timeout = 1

elapsed_time = None
start_time = None
end_time = None
is_timing = False
start_signal = False

lock = threading.Lock()

# Connect to Arduino
try:
    arduino = serial.Serial(port=port, baudrate=baud_rate, bytesize=8, parity='N', stopbits=1, timeout=timeout)
    print(f'Connected to Arduino on {port}')
except Exception as e:
    print(f'Failed to connect to Aduino: {e}')
    exit()

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
            time.sleep(1)  # Wait for 1 second
            with lock:
                elapsed_time += 1000  # Increment time by 1000 milliseconds

# Main program
def main():
    global elapsed_time, start_time, end_time, is_timing, start_signal

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

if __name__ == '__main__':
    timer_thread = threading.Thread(target=timing_thread)
    timer_thread.daemon = True

    serial_thread = threading.Thread(target=main)
    serial_thread.start()

    app.run(debug=True, use_reloader=False)
