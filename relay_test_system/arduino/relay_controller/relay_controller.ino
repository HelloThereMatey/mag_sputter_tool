
/*
 * Relay Controller for Magnetron Sputtering System
 * Arduino Mega 2560 R3
 * 
 * Controls 20 relays via digital pins 22-37, 44-47
 * Reads 4 digital inputs via pins 38-41
 * Reads 4 analog inputs via pins A1-A4
 * Serial communication at 9600 baud
 * Command format: RELAY_X_ON or RELAY_X_OFF (X = 1-20)
 * Response format: OK or ERROR
 */

// Pin mapping for 20 relays (pins 22-37, 44-47)
const int RELAY_PINS[20] = {
  22, 23, 24, 25, 26, 27, 28, 29,  // Relays 1-8
  30, 31, 32, 33, 34, 35, 36, 37, // Relays 9-16
  44, 45, 46, 47                  // Relays 17-20
};
// NOTE: PIN ALLOCATIONS HAVE BEEN CHANGED A BIT, change these to match the hardware

// Pin mapping for 4 digital inputs (pins 38-41)
const int DIGITAL_INPUT_PINS[4] = {
  38, 39, 40, 41                  // Digital inputs 1-4
};

// Pin mapping for 4 analog inputs (pins A1-A4)
const int ANALOG_INPUT_PINS[4] = {
  A1, A2, A3, A4                  // Analog inputs 1-4
};

const int NUM_RELAYS = 20;
const int NUM_DIGITAL_INPUTS = 4;
const int NUM_ANALOG_INPUTS = 4;
const int BAUD_RATE = 9600;
const int COMMAND_TIMEOUT = 5000; // 5 seconds

// Relay states
bool relayStates[NUM_RELAYS];

// Digital input states
bool digitalInputStates[NUM_DIGITAL_INPUTS];

// Analog input values (0-1023)
int analogInputValues[NUM_ANALOG_INPUTS];

void setup() {
  // Initialize serial communication
  Serial.begin(BAUD_RATE);
  
  // Initialize relay pins as outputs and set all relays OFF
  for (int i = 0; i < NUM_RELAYS; i++) {
    pinMode(RELAY_PINS[i], OUTPUT);
    digitalWrite(RELAY_PINS[i], LOW);  // Relay OFF (assuming LOW = OFF)
    relayStates[i] = false;
  }
  
  // Initialize digital input pins
  for (int i = 0; i < NUM_DIGITAL_INPUTS; i++) {
    pinMode(DIGITAL_INPUT_PINS[i], INPUT);
    digitalInputStates[i] = false;
  }
  
  // Initialize analog input values
  for (int i = 0; i < NUM_ANALOG_INPUTS; i++) {
    analogInputValues[i] = 0;
  }
  
  // Send ready message
  Serial.println("ARDUINO_READY");
  Serial.flush();
}

void readDigitalInputs() {
  for (int i = 0; i < NUM_DIGITAL_INPUTS; i++) {
    digitalInputStates[i] = digitalRead(DIGITAL_INPUT_PINS[i]);
  }
}

void readAnalogInputs() {
  for (int i = 0; i < NUM_ANALOG_INPUTS; i++) {
    analogInputValues[i] = analogRead(ANALOG_INPUT_PINS[i]);
  }
}

void loop() {
  // Read digital inputs
  readDigitalInputs();
  
  // Read analog inputs
  readAnalogInputs();
  
  // Check for incoming serial commands
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim(); // Remove whitespace
    
    if (command.length() > 0) {
      processCommand(command);
    }
  }
}

void processCommand(String command) {
  // Parse and execute the command
  if (command.startsWith("RELAY_") && command.length() >= 8) {
    // Extract relay number and action
    int relayNum = 0;
    bool turnOn = false;
    
    if (parseRelayCommand(command, relayNum, turnOn)) {
      // Valid command, execute it
      if (controlRelay(relayNum, turnOn)) {
        Serial.println("OK");
      } else {
        Serial.println("ERROR");
      }
    } else {
      Serial.println("ERROR");
    }
  } else if (command == "STATUS") {
    // Return current status of all relays
    sendStatus();
  } else if (command == "ALL_OFF") {
    // Emergency: turn off all relays
    allRelaysOff();
    Serial.println("OK");
  } else if (command == "GET_DIGITAL_INPUTS") {
    // Return digital input states
    sendDigitalInputs();
  } else if (command == "GET_ANALOG_INPUTS") {
    // Return analog input values
    sendAnalogInputs();
  } else {
    // Unknown command
    Serial.println("ERROR");
  }
  
  Serial.flush();
}

bool parseRelayCommand(String command, int &relayNum, bool &turnOn) {
  // Parse commands like "RELAY_5_ON" or "RELAY_12_OFF"
  
  // Find the underscores
  int firstUnderscore = command.indexOf('_');
  int secondUnderscore = command.lastIndexOf('_');
  
  if (firstUnderscore == -1 || secondUnderscore == -1 || firstUnderscore == secondUnderscore) {
    return false;
  }
  
  // Extract relay number
  String relayNumStr = command.substring(firstUnderscore + 1, secondUnderscore);
  relayNum = relayNumStr.toInt();
  
  // Validate relay number (1-20)
  if (relayNum < 1 || relayNum > NUM_RELAYS) {
    return false;
  }
  
  // Extract action (ON or OFF)
  String action = command.substring(secondUnderscore + 1);
  if (action == "ON") {
    turnOn = true;
    return true;
  } else if (action == "OFF") {
    turnOn = false;
    return true;
  }
  
  return false;
}

bool controlRelay(int relayNumber, bool state) {
  // Convert from 1-based to 0-based indexing
  int index = relayNumber - 1;
  
  // Validate index
  if (index < 0 || index >= NUM_RELAYS) {
    return false;
  }
  
  // Set the relay state
  digitalWrite(RELAY_PINS[index], state ? HIGH : LOW);
  relayStates[index] = state;
  
  return true;
}

void sendStatus() {
  // Send status of all relays
  Serial.print("STATUS:");
  for (int i = 0; i < NUM_RELAYS; i++) {
    Serial.print(relayStates[i] ? "1" : "0");
    if (i < NUM_RELAYS - 1) {
      Serial.print(",");
    }
  }
  Serial.println();
}

void allRelaysOff() {
  // Emergency function: turn off all relays
  for (int i = 0; i < NUM_RELAYS; i++) {
    digitalWrite(RELAY_PINS[i], LOW);
    relayStates[i] = false;
  }
}

void sendDigitalInputs() {
  // Send status of all digital inputs
  Serial.print("DIGITAL_INPUTS:");
  for (int i = 0; i < NUM_DIGITAL_INPUTS; i++) {
    Serial.print(digitalInputStates[i] ? "1" : "0");
    if (i < NUM_DIGITAL_INPUTS - 1) {
      Serial.print(",");
    }
  }
  Serial.println();
}

void sendAnalogInputs() {
  // Send values of all analog inputs (0-1023 raw ADC values)
  Serial.print("ANALOG_INPUTS:");
  for (int i = 0; i < NUM_ANALOG_INPUTS; i++) {
    Serial.print(analogInputValues[i]);
    if (i < NUM_ANALOG_INPUTS - 1) {
      Serial.print(",");
    }
  }
  Serial.println();
}
