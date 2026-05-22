import serial
import sys
import threading

def read_from_port(ser, output_file):
    with open(output_file, "a") as f:
        while True:
            try:
                data = ser.readline()
                if data:
                    text = data.decode(errors='ignore').rstrip()
                    print(text)
                    f.write(text + '\n')
                    f.flush()
            except Exception as e:
                print(f"Error reading: {e}")
                break

def write_to_port(ser):
    print("Type characters and press Enter to send to sensor (Ctrl+C to exit):")
    while True:
        try:
            line = input()
            if line:
                ser.write(line.encode())
        except KeyboardInterrupt:
            print("\nExiting...")
            break

def main():
    if len(sys.argv) != 4:
        print(f"Usage: python {sys.argv[0]} <port> <baudrate> <output_file>")
        sys.exit(1)

    port = sys.argv[1]
    baudrate = int(sys.argv[2])
    output_file = sys.argv[3]

    try:
        ser = serial.Serial(port, baudrate, timeout=1)
    except Exception as e:
        print(f"Error opening serial port: {e}")
        sys.exit(1)

    # Send initial character to start sensor
    ser.write(b'\n')

    # Start reading thread
    read_thread = threading.Thread(target=read_from_port, args=(ser, output_file), daemon=True)
    read_thread.start()

    # Start writing loop (main thread)
    write_to_port(ser)

    ser.close()

if __name__ == "__main__":
    main()

