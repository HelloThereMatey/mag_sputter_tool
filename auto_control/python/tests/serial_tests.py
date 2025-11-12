import serial
import time

# Open serial connection to Arduino
ser = serial.Serial('/dev/ttyACM0', 9600, timeout=2)  # Use your port

# Wait for Arduino to initialize
time.sleep(2)

# Send a command and read response
ser.write("GET_DIGITAL_INPUTS\n".encode())
response = ser.readline().decode().strip()
print(f"Response: {response}")

# Try other commands
ser.write("STATUS\n".encode())
response = ser.readline().decode().strip()
print(f"Status: {response}")

# Close when done
ser.close()