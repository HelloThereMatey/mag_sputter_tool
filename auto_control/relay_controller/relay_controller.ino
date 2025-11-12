/*
 * Relay Controller for Magnetron Sputtering System
 * Arduino Mega 2560 R3
 * 
 * Controls 23 relays via digital pins 22-41, 44, 46, 48
 * Reads 4 digital inputs via pins 45, 47, 49, 51
 * Reads 4 analog inputs via pins A1-A4 (A1=Load-lock, A2=Chamber, A3=Ion Gauge, A4=Turbo Spin)
 * Serial communication at 9600 baud
 * Command format: RELAY_X_ON or RELAY_X_OFF (X = 1-23)
 * Response format: OK or ERROR
 *
 * CRITICAL SAFETY: Pin 22 (Relay 1) - mains power safety shutdown only
 * Python controls ON state, Arduino enforces safety shutdown on interlock violation
 */

// Pin mapping for 23 relays (updated to match sput.yml configuration)
const int RELAY_PINS[23] = {
  22,                             // Relay 1 (mains power - CRITICAL SAFETY)
  23, 24, 25, 26, 36, 28, 29,     // Relays 2-8 
  30, 31, 32, 33, 34, 35, 27, 37, // Relays 9-16 
  38, 39, 40, 41,                 // Relays 17-20 (these are spare wires, the relays do not exist)
  44,                             // Relay 21 (scroll pump)
  46,                             // Relay 22 (spare relay)
  48                              // Relay 23 (spare for future upgrades)
};
// NOTE: PIN ALLOCATIONS HAVE BEEN CHANGED A BIT, change these to match the hardware

// Pin mapping for 4 digital inputs (Door, Water, Rod interlocks)
// Hardware: Internal pull-ups enabled, switches connect pin to ground when active
// Logic: LOW at pin (switch closed) = safe condition, HIGH at pin (switch open) = unsafe condition
// Software: Readings are inverted so Python receives true=safe, false=unsafe
const int DIGITAL_INPUT_PINS[4] = {
  45, 47, 49, 51                  // Digital inputs: Water(45), Rod(47), Door(49), Spare(51)
};

// Pin mapping for 4 analog inputs (pins A1-A4) - ordering: A1=Load-lock, A2=Chamber, A3=Ion Gauge, A4=Turbo Spin
const int ANALOG_INPUT_PINS[4] = {
  A1, A2, A3, A4                  // Analog inputs 1-4
};

const int NUM_RELAYS = 23;
const int NUM_DIGITAL_INPUTS = 4;
const int NUM_ANALOG_CHANNELS = 4;  // Renamed to avoid conflict with Arduino core
const int BAUD_RATE = 9600;
const int COMMAND_TIMEOUT = 5000; // 5 seconds

// Relay states array
bool relayStates[NUM_RELAYS];

// Digital input states
bool digitalInputStates[NUM_DIGITAL_INPUTS];

// Analog input values (0-1023)
int analogInputValues[NUM_ANALOG_CHANNELS];

bool previousInterlockState = false;  // Track previous state of all 3 critical interlocks

void setup() {
  // Initialize serial communication
  Serial.begin(BAUD_RATE);
  
  // Initialize relay pins as outputs WITHOUT forcing state changes
  // CRITICAL: On Arduino reset/power-up, all pins default to INPUT and LOW state
  // Setting pinMode(OUTPUT) can cause momentary state changes that close valves
  // Solution: Don't initialize relay pins as outputs until explicitly commanded by Python
  // This prevents any unwanted relay operations during Arduino startup
  
  // DO NOT set relay pins as OUTPUT during initialization!
  // Keep them in INPUT mode (high impedance) to avoid affecting relay states
  // Python will explicitly set each relay's desired state after connection
  
  for (int i = 0; i < NUM_RELAYS; i++) {
    // Keep pins in INPUT mode (default) - high impedance, won't affect relays
    // pinMode(RELAY_PINS[i], OUTPUT);  // DISABLED - causes unwanted relay operations!
    
    // Initialize tracking array to unknown state - Python will sync this
    relayStates[i] = false;  // Default to false for tracking, Python will update
  }
  
  // Initialize digital input pins with internal pull-ups enabled
  for (int i = 0; i < NUM_DIGITAL_INPUTS; i++) {
    pinMode(DIGITAL_INPUT_PINS[i], INPUT_PULLUP);  // Enable internal pull-up (~20-50kΩ)
    digitalInputStates[i] = false;
  }
  
  // CRITICAL SAFETY CHECK: Load-lock arm position BEFORE any other initialization
  // DIGITAL_INPUT_PINS[1] = Rod/Load-lock arm position (pin 47)
  // HIGH = arm not in home position (unsafe), LOW = arm in home position (safe)
  bool rodPosition = digitalRead(DIGITAL_INPUT_PINS[1]);  // Read rod position directly
  
  if (rodPosition == HIGH) {  // HIGH = arm not in home position
    // IMMEDIATE SAFETY HALT - Load-lock arm is not in home position
    Serial.println();
    Serial.println("CRITICAL_SAFETY_ERROR");
    Serial.println();
    Serial.println("LOAD-LOCK ARM IS NOT IN HOME POSITION!!");
    Serial.println();
    Serial.println("RETURN TO HOME POSITION AND THEN REBOOT GUI.");
    Serial.println();
    Serial.println("ARDUINO_SAFETY_HALT");
    Serial.flush();
    
    // Halt execution completely - do not proceed with any initialization
    while (true) {
      delay(1000);  // Infinite loop - system must be physically reset
    }
  }
  
  // Initialize analog input values
  for (int i = 0; i < NUM_ANALOG_CHANNELS; i++) {
    analogInputValues[i] = 0;
  }
  
  // Send ready message with initialization info
  Serial.println("ARDUINO_READY");
  Serial.println("INIT: Arduino startup completed - relay states preserved");
  
  // Send initial relay status for debugging
  Serial.println("INIT_STATUS_START");
  for (int i = 0; i < NUM_RELAYS; i++) {
    Serial.print("RELAY_");
    Serial.print(i + 1);
    Serial.print("_STATUS:");
    Serial.println(relayStates[i] ? "ON" : "OFF");
  }
  Serial.println("INIT_STATUS_END");
  
  Serial.flush();
}

void readDigitalInputs() {
  for (int i = 0; i < NUM_DIGITAL_INPUTS; i++) {
    // Hardware: Internal pull-ups enabled, switches connect to ground when active
    // Pin reads: LOW = switch closed/safe, HIGH = switch open/unsafe
    // Invert reading: true = safe (switch closed), false = unsafe (switch open)
    bool pinReading = digitalRead(DIGITAL_INPUT_PINS[i]);
    digitalInputStates[i] = !pinReading;  // Invert: LOW (0) becomes true (safe), HIGH (1) becomes false (unsafe)
  }
}

void readAnalogInputs() {
  for (int i = 0; i < NUM_ANALOG_CHANNELS; i++) {
    analogInputValues[i] = analogRead(ANALOG_INPUT_PINS[i]);
  }
}

void loop() {
  // Read digital inputs
  readDigitalInputs();
  
  // Read analog inputs
  readAnalogInputs();
  
  // Check current state of all 3 critical interlocks: Door(0), Water(1), Rod(2)
  bool allInterlocksOK = digitalInputStates[0] && digitalInputStates[1] && digitalInputStates[2];
  
  // AUTOMATIC MAINS POWER SAFETY SHUTDOWN ONLY
  // Python controls turning mains power ON - Arduino only enforces safety shutdown
  if (!allInterlocksOK && relayStates[0]) {
    // One or more interlocks violated AND mains power is currently ON - force it OFF
    Serial.println("AUTO_SAFETY: Mains power disabled - interlock violation detected");
    pinMode(RELAY_PINS[0], OUTPUT);     // Set pin 22 as OUTPUT first
    digitalWrite(RELAY_PINS[0], LOW);   // Emergency shutdown - turn off pin 22 (mains power)
    relayStates[0] = false;
  }
  
  // Update previous state for next loop
  previousInterlockState = allInterlocksOK;
  
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
  
  // Validate relay number (1-23)
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
  
  // SPECIAL HANDLING for mains power relay (relay 1, index 0)
  if (index == 0) {
    // Mains power can be controlled by Python, but only if interlocks are satisfied
    // Check current interlock state before allowing state change
    bool allInterlocksOK = digitalInputStates[0] && digitalInputStates[1] && digitalInputStates[2];
    
    // Debug: Print interlock states for mains power control
    Serial.print("MAINS_DEBUG: Interlocks Water=");
    Serial.print(digitalInputStates[0] ? "OK" : "FAIL");
    Serial.print(" Rod=");
    Serial.print(digitalInputStates[1] ? "OK" : "FAIL");
    Serial.print(" Door=");
    Serial.print(digitalInputStates[2] ? "OK" : "FAIL");
    Serial.print(" AllOK=");
    Serial.println(allInterlocksOK ? "YES" : "NO");
    
    if (state == true && !allInterlocksOK) {
      // Python trying to turn ON mains power but interlocks not satisfied - reject
      Serial.println("MAINS_DEBUG: Rejected - interlocks not satisfied");
      return false;
    }
    
    // Allow the state change - Python has control
    Serial.print("MAINS_DEBUG: Setting pin 22 to ");
    Serial.println(state ? "HIGH" : "LOW");
    pinMode(RELAY_PINS[index], OUTPUT);
    digitalWrite(RELAY_PINS[index], state ? HIGH : LOW);
    relayStates[index] = state;
    Serial.println("MAINS_DEBUG: Command completed successfully");
    return true;
  }
  
  // Set the relay state for all other relays
  // IMPORTANT: Set pin as OUTPUT only when first commanded by Python
  // This avoids unwanted state changes during Arduino initialization
  pinMode(RELAY_PINS[index], OUTPUT);  // Safe to do now - Python is controlling
  
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
  // Returns inverted logic: 1 = safe (switch closed), 0 = unsafe (switch open)
  Serial.print("DIGITAL_INPUTS:");
  for (int i = 0; i < NUM_DIGITAL_INPUTS; i++) {
    Serial.print(digitalInputStates[i] ? "1" : "0");
    if (i < NUM_DIGITAL_INPUTS - 1) {
      Serial.print(",");
    }
  }
  Serial.println();
  
  // Debug output - remove after testing
  Serial.print("DEBUG - Raw pin readings: ");
  for (int i = 0; i < NUM_DIGITAL_INPUTS; i++) {
    Serial.print("Pin");
    Serial.print(DIGITAL_INPUT_PINS[i]);
    Serial.print("=");
    Serial.print(digitalRead(DIGITAL_INPUT_PINS[i]));
    Serial.print(" ");
  }
  Serial.println();
}

void sendAnalogInputs() {
  // Send values of all analog inputs (0-1023 raw ADC values)
  Serial.print("ANALOG_INPUTS:");
  for (int i = 0; i < NUM_ANALOG_CHANNELS; i++) {
    Serial.print(analogInputValues[i]);
    if (i < NUM_ANALOG_CHANNELS - 1) {
      Serial.print(",");
    }
  }
  Serial.println();
}