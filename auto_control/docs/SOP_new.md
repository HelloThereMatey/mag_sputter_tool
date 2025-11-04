---
html:
  embed_local_images: false
  embed_svg: true
  offline: true
  toc: true
  
print_background: false
---

<style>
p {font-size: 14px}
li {font-size: 14px}
figcaption {font-size: 14px}
table {font-size: 13px}
math, .math {font-size: 14px}
code, pre {font-size: 13px}

```
/* Force continuous layout */
@media print {
@page {
  size: A4 portrait;
  margin: 0.05in 0.1in;
  height: auto}
}
```

</style>

# Magnetron Sputtering System - Standard Operating Procedure (SOP)

**Document Version:** 2.0  
**Last Updated:** October 20, 2025  
**Control System:** Python-Based Automated Control  
**Hardware Platform:** Arduino Mega 2560 R3

---

## Table of Contents

0. [System Overview](#system-overview)
1. [System Startup Procedure](#system-startup-procedure)
2. [Loading Samples and Targets](#loading-samples-and-targets)
3. [Deposition Procedure (DC Sputtering)](#deposition-procedure-dc-sputtering)
4. [System Shutdown](#system-shutdown)
5. [Load-Lock Operation](#load-lock-operation)
6. [Load-Lock Practice Procedure](#load-lock-practice-procedure)
7. [Safety Guidelines](#safety-guidelines)
8. [Troubleshooting](#troubleshooting)

---

## System Overview

The sputter system uses a custom software running on low-cost hardware. A raspberry Pi 5 runs the software (written in python) and interfaces via serial connection with an Arduino Mega running custom firmware (C++). The arduino operates relays that control valves, pressure gauges and vacuum pumps and other system components...

## 🚀 System Startup Procedure

### Prerequisites

- ✅ System power is ON
   - If system is in unpowered state turn on the power. There is a single power line that supplies the system on wall at right labelled "SPUTTER SYSTEM POWER".
   - The DC and RF power supplies for sputtering are powered separately as shown in the figure below. Turn this on too.

   <figure style="display:flex;gap:12px;align-items:flex-start">
      <div style="flex:1;margin:0">
         <img src="pics/main_power.jpg" alt="Image 1" style="width:94%;height:auto;display:block;border:0">
         <figcaption style="text-align:center;font-size:13px;margin-top:6px">(a) Main power for system.</figcaption>
      </div>
      <div style="flex:1;margin:0">
         <img src="pics/supplies_power.jpg" alt="Image 2" style="width:100%;height:auto;display:block;border:0">
         <figcaption style="text-align:center;font-size:13px;margin-top:6px">(b) This one supplies power to the DC & RF supplies. Here it is shown in the "on" position.</figcaption>
      </div>
   </figure>

- ✅ Raspberry Pi has booted to desktop.
   - When the power for the system is switched on, the RPi5 will auto-boot. Both screens should turn on.
   - If it does not boot, the RPi5 can be turned on by the power button on its case.
   - If the touch-screen is blank but the larger screen shows content after booting, unplugging & re-plugging the HDMI out from the RPi to the small screen should fix this.
- ✅ Arduino controller is connected via USB. This should be the case.
- ⚠️ If control program is already running, skip to step 3

### Launching the Control Application

1. **Start the Application**
   - Locate the **Sputter Control** desktop icon. It has a sun image icon :sunny:.
   - Double-click to launch the Python-based control application.
   - This will launch a terminal window that should be positioned on the large screen. This window shows running messages that details the system operation and is useful for debug.
   - **Login** with your user account or create new account on the login window that shows first.
   - Main control window will then open. Drag this window onto the small screen (touch-screen) and double click the top bar to expand the GUI window to fill the screen.
   - You can use touch to activate the buttons on the GUI.

3. **Check System State Display**
   - Observe the **System State** indicator in the control window
   - Current system status will be displayed (e.g., "Vented", "pumping", "High Vacuum")
   - All sensor readings (pressures, door status, water flow) should update automatically.
   - There are 3 interlocks that need to show True state (green indicator on GUI). These show the state of the water switch, rod home switch and the door switch. These are True when water flowing, load-lock rod is in home position & the chamber door is closed respectively.

4. **Verify Automated Procedure Buttons**
   - Five main procedure buttons should be visible and enabled (not greyed out):
     - 🌊 **PUMP** - Start pump-down sequence
     - 💨 **VENT** - Vent chamber to atmosphere
     - 📦 **LOAD/UNLOAD** - Load-lock operation
     - 🔬 **SPUTTER** - Enter sputtering mode
     - 🏠 **STAND BY** - Return system to default state or standby state. This should be used at end of session to put system into low-power stand-by state.

#### BOOT TROUBLESHOOTING

If the GUI displays with red indications for all three interlocks and the valve buttons display greyed out, it is likely that the arduino has failed to connect to RPi5.

**Verify Arduino Connection**

- Check USB cable between arduino & RPi5. Ensure that the arduino shows LED on indicator.
- Remove and replace USB cable to reset the connection.

---

## 📥 Loading Samples and Targets

### Starting from Vented Chamber State

#### Target Installation and Sample Loading

1. **Install Sputter Targets** (if not already in place)
   - Ensure targets are clean and properly aligned
   - Secure target with **4 Phillips head screws**
   - Secure outer electrode of gun with **3 hex key screws**
   - Target installation is demonstrated during training

2. **Load Sample and Sample Stage**
   - Place sample on sample stage holder
   - Position stage appropriately for deposition geometry
   - Verify sample is secure

#### Door Closure and Clamp Procedure

⚠️ **CRITICAL:** Proper door sealing is essential for vacuum integrity

3. **Close and Seal Chamber Door**
   - Close door carefully, ensuring O-ring is clean and properly seated
   - Tighten **both door clamps**:
     - One clamp is a standard threaded closure
     - One clamp is a **nut requiring T-key with hex socket** (tool should be near instrument frame)
   - **Both clamps must be fully tightened** before starting pump-down

4. **Door Clamp Adjustment During Pump-Down**
   - ⚠️ **Important:** Once chamber pressure begins dropping, **loosen clamps slightly**
   - This prevents over-compression of the O-ring
   - If chamber pressure does **not** drop when pump-down starts:
     - **Chamber is leaking!**
     - Re-tighten clamps to improve door seal
     - Check O-ring condition

5. **Initiate Pump-Down**

   ⚠️ **IMPORTANT:** Verify everything is correct in chamber before pumping. Once PUMP button is pressed, wait for sequence to complete. Initial pump-down from atmosphere takes **>10 minutes**.

   - Click the **PUMP** button
   - Monitor pressure readings on display
   - Chamber should progress through: Atmospheric → Rough Pump → Medium Vacuum → High Vacuum
   - Wait for pump procedure to complete (indicated by system state change)

---

### Starting from Pumped Chamber State

If the chamber is already under vacuum, use the **Load-Lock** system to introduce samples without venting the main chamber.

#### Load-Lock Sample Loading Procedure

1. **Initiate Load-Lock Sequence**
   - Click **LOAD/UNLOAD** button
   - System will automatically:
     - Close gate valve (if open)
     - Vent load-lock chamber
     - Wait for load-lock to reach atmospheric pressure

2. **Wait for Load-Lock Ready**
   - Dialog box will appear: **"Load-Lock Ready - Load/Remove Sample"**
   - Small load-lock door can now be opened
   - Load-lock is at atmospheric pressure

3. **Load Sample onto Load-Lock Rod**
   - Open small load-lock door
   - Attach sample stage to load-lock rod bayonet fitting
   - Close load-lock door
   - Click **Continue** in dialog box

4. **Automated Load-Lock Pump-Down**
   - System will automatically:
     - Evacuate load-lock chamber
     - Wait for pressure equalization with main chamber
     - Open gate valve between load-lock and main chamber

5. **Position Sample in Chamber**
   - Dialog box will appear: **"Load-Lock Evacuated - Transfer Sample"**
   - Use load-lock rod to move sample stage into main chamber
   - **Adjust Z-position nuts** (see Figure 1 below) to align stage with central shaft
   - Rotate stage onto shaft and secure with bayonet fitting
   - Carefully retract load-lock rod to home position
   - Click **Continue** when complete

6. **System Completion**
   - Gate valve will close automatically
   - Load-lock sequence completes
   - System returns to high vacuum state with sample loaded

#### Load-Lock Z-Position Adjustment

![Load-Lock Z-Position Adjustment Nuts](pics/loadlock_z_adjustment.png)

**Figure 1:** Load-lock Z-position adjustment nuts. Hold rod up/down to release pressure on nuts, then adjust nuts to change rod height. This adjustment must be done:
- **First:** To align stage with central shaft during loading
- **Second:** To relieve pressure on bayonet fitting for rotation and rod removal

#### Sample Stage Rotation (Optional)

If uniform coating is desired, enable stage rotation:

- Turn on **DC power supply** in constant voltage mode
- Adjust voltage knob: **0-6V** to set rotation speed
- **Recommended during deposition:** 4V
- **Absolute maximum:** 12V
- ⚠️ **Turn off power supply when rotation not in use**

#### Chamber Illumination

- Turn on **chamber light** switch if visibility needed for setup
- ⚠️ **Turn off after use** - do not leave on during deposition

---

## 🔬 Deposition Procedure (DC Sputtering)

### Pre-Deposition Pump-Down

⚠️ **Recommendation:** If pumping from atmosphere, wait **at least 1 hour** before deposition

- **Target vacuum level:** High 10⁻⁶ mbar range (for oxidizable metals)
- Monitor ion gauge reading to verify high vacuum achieved

### Process Gas Introduction

1. **Start Gas Flow**
   - Click **SET GAS** button (or use MFC dialog from Tools menu)
   - Gas flow controller interface will open

2. **Chamber Flush** (Optional but Recommended)
   - Set Argon flow to **100-200 sccm** for 5-10 minutes
   - This helps remove remaining impurities
   - Monitor chamber pressure during flush

3. **Set Sputtering Gas Flow**
   - Reduce Argon flow to sputtering conditions
   - **Typical DC metal sputtering:** 20-50 sccm Ar
   - **Target chamber pressure:** 1-3 × 10⁻³ mbar
   - Wait for pressure to stabilize

### DC Sputtering Operation

1. **Verify Electrical Connections**
   - ✅ Electrical cable between gun and DC power supply is connected
   - ✅ Grounding cables are properly connected
   - ✅ All connections are secure

2. **Power Supply Setup**
   - Turn on **DC power supply** for the gun(s) being used
   - Set **power setpoint**:
     - **Typical range:** 30-100 W
     - **Absolute maximum:** 150 W

3. **Start Deposition Monitor**
   - Launch **MaxTec deposition monitor** for target material
   - Verify monitor is reading and calibrated
   - Reference: `MaxTec_FilmMonitor.pdf` (Section 10.6 for tooling factor calibration)

4. **Ignite Plasma**
   - Press **Start** on DC power supply to apply power
   - Plasma should ignite on gun - you will see characteristic glow
   - Close **front window shutter** to prevent window coating
   - Verify deposition monitor shows:
     - Non-zero deposition rate
     - Increasing thickness reading

5. **Begin Sample Deposition**
   - Open **gun shutter** to start deposition on sample
   - ⏱️ **Restart MaxTec monitor** simultaneously for accurate thickness reading
   - Monitor deposition rate and thickness

6. **Run to Desired Thickness**
   - Continue sputtering until target thickness achieved
   - Typical rates vary by material and power (refer to training or previous logs)

---

## 🛑 System Shutdown

### Post-Deposition Procedure

1. **Terminate Sputtering**
   - Turn off **DC power supply/s**
   - Turn off **breaker switch** at back of power supply
   - Allow plasma to extinguish completely

2. **Stop Gas Flow**
   - Click **SET GAS** button and set all flows to 0 sccm
   - OR close MFC dialog (flows will automatically stop)
   - Verify gas flow stops on MFC display

3. **Remove Sample via Load-Lock**
   - Click **LOAD/UNLOAD** button
   - Follow load-lock procedure in reverse:
     - System vents load-lock
     - Open small door when dialog appears
     - Use rod to retrieve sample stage from chamber
     - Remove sample from stage
     - **Leave sample stage inside load-lock for next user**
     - Close load-lock door
     - Click Continue

4. **Re-Evacuate Load-Lock**
   - Click **LOAD/UNLOAD** again to evacuate load-lock
   - System will pump down load-lock automatically

5. **Return System to High Vacuum**
   - Click **PUMP** button to return system to stable high vacuum state
   - Final system state should show:
     - ✅ Roughing pump ON (green)
     - ✅ Rough valve OPEN (green)
     - ✅ Turbo pump ON & ~100% speed (green)
     - ✅ Gate valve CLOSED (red - correct)
     - ✅ All other valves CLOSED (red - correct)
     - ✅ Ion gauge ON (green - if high vacuum achieved)

### Final Checks

6. **Verify Equipment Status**
   - ❌ All DC/RF sputter supplies are **OFF**
   - ❌ DC supply for stage rotation is **OFF**
   - ❌ Chamber light is **OFF**

7. **Update Target Labels**
   - If targets were changed, update **sticky note labels** on chamber door
   - Write material name and installation date

8. **Complete Instrument Logbook**
   - Record session information:
     - Date and time
     - User name
     - Target material(s)
     - Process parameters (power, pressure, gas flow)
     - Deposition time and estimated thickness
     - Any issues or anomalies

9. **Leave System in Standby**
   - System can be left in high vacuum state for next user
   - Do **not** close control application unless instructed

---

## 🔄 Load-Lock Operation

### Load-Lock Rod Control

The load-lock rod extends into the main chamber through a gate valve to position samples.

**Key Components:**
- **Bayonet fitting** - Quick-connect mount for sample stage
- **Z-position adjustment nuts** - Control vertical position of rod end
- **Gate valve** - Separates load-lock from main chamber

### Load-Lock Procedure Summary

**Loading Sample:**
1. LOAD/UNLOAD → vent load-lock → open small door
2. Attach stage to rod → close door → Continue
3. System pumps load-lock → opens gate valve automatically
4. Adjust Z-nuts → position stage in chamber → detach rod → retract rod → Continue

**Removing Sample:**
1. LOAD/UNLOAD → gate valve opens → dialog appears
2. Extend rod → adjust Z-nuts → attach to stage → retract to home → Continue
3. System closes gate valve → vents load-lock
4. Open small door → remove stage → close door → Continue (re-evacuates load-lock)

---

## 🎓 Load-Lock Practice Procedure

⚠️ **Important:** The load-lock can be difficult to master initially. **Practice with the chamber vented and door open** until confident you can operate it blind (door closed, at vacuum).

**If sample stage is dropped inside chamber during attempted load-lock use, the chamber must be vented to retrieve it!**

### Setup for Practice

1. **Prepare System for Practice**
   - Use automated procedures:
     - Click **VENT** to vent main chamber (if not already vented)
     - Click **LOAD/UNLOAD** to vent load-lock
     - Wait for both to reach atmospheric pressure
   - Ensure load-lock rod is in **home position** (fully retracted)

2. **Open Chambers**
   - Open main chamber door
   - Open small load-lock door
   - Verify rod is retracted

### Manual Gate Valve Control for Practice

3. **Access Manual Control Mode**
   - On main control window, select **Tools → Manual Control**
   - Manual control interface will open

   ⚠️ **CAUTION:** Manual mode allows all valves to be operated manually. Opening the wrong valve could cause serious damage to the system! **We will ONLY use this to open the load-lock gate valve manually**

4. **Manually Open Gate Valve**

   ⚠️ **CRITICAL WARNING:** It is possible to close the gate valve while the load-lock rod is extended through it into the chamber. **This would destroy the gate valve mechanism!**

   **Before touching gate valve button, ALWAYS verify rod is in home position!**

   - Confirm load-lock rod is fully retracted to home position
   - Click **Load-Lock Gate Valve** button to open valve

### Practice Loading

5. **Practice Sample Stage Loading**
   - With main door **open** and gate valve **open**, practice:
     - Extending rod into chamber
     - Adjusting **Z-position nuts** to align stage with central shaft
     - Rotating stage onto shaft (bayonet fitting)
     - Adjusting nuts again to relieve pressure on fitting
     - Rotating rod 90° to release from stage
     - Retracting rod without pulling stage off shaft

6. **Practice Unloading**
   - Reverse the sequence:
     - Adjust Z-nuts for proper height
     - Engage bayonet fitting with stage
     - Rotate to lock
     - Retract rod with stage attached
     - Return to home position

### Cleanup After Practice

7. **Close Manual Mode**
   - When stage is loaded and rod is at home position
   - **Close gate valve** (rod MUST be home!)
   - Close Manual control window

8. **Return to Normal Operation**
   - Return to main control window
   - System returns to automated control
   - Close main chamber door when ready

---

## ⚠️ Safety Guidelines

### General Safety

- 🚫 **Never open main chamber door while system is under vacuum**
- 🚫 **Never force any valve or mechanical component**
- 🚫 **Do not operate system without proper training**
- ⚠️ **Always wear appropriate PPE** (safety glasses, gloves when handling samples)
- ⚠️ **High voltage present** when DC/RF supplies are active
- ⚠️ **Hot surfaces** - allow targets and chamber to cool before handling

### Pressure Safety

- ✅ Always verify chamber is **vented** before opening door
- ✅ Monitor pressure readings during all operations
- ⚠️ Sudden pressure loss may indicate leak or valve malfunction
- ⚠️ Inability to reach high vacuum may indicate O-ring or seal issue

### Electrical Safety

- 🔌 Verify all electrical connections before applying power
- ⚠️ **DC supplies can deliver high currents** - ensure proper grounding
- ⚠️ RF supplies generate high frequency radiation - keep clear
- 🚫 Do not modify electrical connections without supervision

### Gas Safety

- 💨 Process gases (Ar, O₂, etc.) displace oxygen - ensure adequate ventilation
- ✅ Verify gas flow rates before starting deposition
- ⚠️ High gas flows can cause rapid pressure rise
- 🚫 Never exceed recommended maximum gas flow rates (200 sccm Ar max for flush)

### Mechanical Safety

- ⚠️ Load-lock rod can be pinched in gate valve - always verify home position
- ⚠️ Stage rotation motor has exposed moving parts - keep clear
- ⚠️ Door clamps must be properly tightened before pump-down
- 🚫 Do not operate load-lock if rod binding or sticking

---

## 🔧 Troubleshooting

### Common Issues and Solutions

#### Chamber Won't Pump Down

**Symptoms:** Pressure remains high after PUMP procedure starts

**Possible Causes:**
- Door clamps not tight enough
- O-ring dirty or damaged
- Valve stuck open
- Rough pump failure

**Solutions:**
1. Check door clamps - tighten if needed
2. Vent chamber and inspect O-ring
3. Verify all valves show correct state in control program
4. Check rough pump power and operation
5. Contact staff if problem persists

#### Gate Valve Won't Open

**Symptoms:** Load-lock procedure fails, gate valve remains closed

**Possible Causes:**
- Pressure difference too high between chambers
- Valve actuator failure
- Safety interlock preventing operation

**Solutions:**
1. Verify load-lock has fully evacuated (check pressure reading)
2. Wait longer for pressure equalization
3. Check safety status in control program
4. Restart load-lock procedure
5. Contact staff if valve remains stuck

#### Plasma Won't Ignite

**Symptoms:** No plasma glow when DC power applied

**Possible Causes:**
- Chamber pressure too low or too high
- Target not properly grounded
- Power supply malfunction
- Gas flow not established

**Solutions:**
1. Verify chamber pressure is in range (1-3 × 10⁻³ mbar)
2. Check gas flow is active (20-50 sccm Ar)
3. Verify target and electrode connections
4. Check DC power supply settings and operation
5. Try increasing pressure slightly (more gas flow)
6. Contact staff if plasma still won't ignite

#### Sample Stage Dropped in Chamber

**Symptoms:** Stage fell off shaft during load-lock operation

**Impact:** ⚠️ **Chamber must be vented to retrieve stage**

**Solutions:**
1. Click **VENT** button to vent chamber safely
2. Open main chamber door when fully vented
3. Retrieve sample stage carefully
4. Inspect stage and bayonet fitting for damage
5. Practice load-lock operation with door open before retrying
6. Inform staff of incident

#### Control Program Unresponsive

**Symptoms:** Buttons greyed out, no response to clicks

**Possible Causes:**
- Procedure already running (must complete first)
- Arduino connection lost
- Application frozen

**Solutions:**
1. Check if automated procedure is running (wait for completion)
2. Check Arduino connection status indicator
3. Verify USB cable is connected
4. Close and restart application if frozen
5. Reboot PC if problem persists
6. Contact staff for assistance

#### Memory/Performance Issues (Plotter Window)

**Symptoms:** Application slow, high memory usage, plotter window lag

**Solutions:**
1. Close plotter window if not needed
2. Restart application if memory usage high
3. Ensure psutil is installed for memory monitoring
4. Memory monitoring will auto-reset at 80% threshold
5. Check system RAM if issues persist

---

## 📋 Pre-Use Checklist

Before each deposition session, verify:

- [ ] Received proper training on system operation
- [ ] Reviewed this SOP document
- [ ] System power is ON and stable
- [ ] Control application connects successfully
- [ ] All required materials and samples prepared
- [ ] Target material installed correctly (if changed)
- [ ] O-ring and door seal are clean
- [ ] PPE (safety glasses, gloves) available
- [ ] Instrument logbook available for recording session

---

## 📞 Emergency Contacts

**For system malfunctions or emergencies:**
- Contact supervising staff immediately
- Do not attempt repairs without authorization
- Document issue in instrument logbook

**After-hours emergencies:**
- Follow facility emergency procedures
- Contact facility management

---

## 📝 Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | (Original) | - | Original LabVIEW-based SOP |
| 2.0 | October 2025 | System Team | Updated for Python-based control system, added detailed procedures, icons, and formatting |

---

**End of Standard Operating Procedure**

*This document should be reviewed and updated annually or when significant system changes occur.*
