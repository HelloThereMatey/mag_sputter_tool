---
html:
  embed_local_images: false
  embed_svg: true
  offline: true
  toc: true # Set desired content width
  
print_background: false
---

<style>
p {font-size: 12px}
li {font-size: 12px}
figcaption {font-size: 12px}
table {font-size: 12px}
math, .math {font-size: 12px}
code, pre {font-size: 12px}

```
/* Force continuous layout */
@media print {
@page {
  size: A4 portrait;
  margin: 0.05in 0.1in;
  /* Remove page height constraint */
  height: auto;
}
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

1. [System Startup Procedure](#system-startup-procedure)
2. [Loading Samples and Targets](#loading-samples-and-targets)
3. [Deposition Procedure (DC Sputtering)](#deposition-procedure-dc-sputtering)
4. [System Shutdown](#system-shutdown)
5. [Load-Lock Operation](#load-lock-operation)
6. [Load-Lock Practice Procedure](#load-lock-practice-procedure)
7. [Safety Guidelines](#safety-guidelines)
8. [Troubleshooting](#troubleshooting)

---

## 🚀 System Startup Procedure

### Prerequisites

- ✅ System power is ON
- ✅ PC has booted to desktop
- ✅ Arduino controller is connected via USB
- ⚠️ If control program is already running, skip to step 3

### Launching the Control Application

1. **Start the Application**
   - Locate the **Sputter Control System** desktop icon
   - Double-click to launch the Python-based control application
   - Main control window will open

2. **Verify Arduino Connection**
   - Application will auto-connect to Arduino Mega 2560
   - Connection status indicator should turn **green** when ready
   - If connection fails, check USB cable and restart application

3. **Check System State Display**
   - Observe the **System State** indicator in the control window
   - Current system status will be displayed (e.g., "Vented", "Rough Pump", "High Vacuum")
   - All sensor readings (pressures, door status, water flow) should update automatically

4. **Verify Automated Procedure Buttons**
   - Five main procedure buttons should be visible and enabled (not greyed out):
     - 🌊 **PUMP** - Start pump-down sequence
     - 💨 **VENT** - Vent chamber to atmosphere
     - 📦 **LOAD/UNLOAD** - Load-lock operation
     - 🔬 **SPUTTER** - Enter sputtering mode
     - 🏠 **CLOSE ALL** - Return system to default state

---

## 📥 Loading Samples and Targets

### Starting from Vented Chamber State

#### Prerequisites

- ✅ Chamber is at atmospheric pressure
- ✅ Door clamps are loosened
- ✅ Chamber door can be opened

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

#### This section needs completion - continuing below...  

Open “Sputter System Master Control.vi” from the icon on the desktop.  

Press labview “Run” button on VI (Arrow in top left).  

Press “AUTO” button to open up the AUTO control VI.  

VI should open already in running state. All 5 main buttons at right should be yellow and not greyed out. 1 Press pump button to start pump sequence. IMPORTANT: Make sure that everything is as you wish in chamber before pressing pump. Once a button is pressed, you must wait for the button sequence to complete before anything else can be done. This could be > 10 mins if starting from vented chamber.2 

If starting with chamber in vented state3: 

Load sputter target/s if not already in place4. Place sample and sample stage in position. Ensure that all screws are in place to hold target (x4, phillips head) & outer electrode of gun (x3, alum key head). Loading of target is demonstrated during training. *Note that one of the clamps that holds door shut for initial pump-down is a nut and requires the T-key with hex socket attached tool that should be found nearby one the instrument frame. Both clamps need to be tightened before pump-down and then loosened once chamber pressure begins dropping. If chamber P does not drop when pump-down started then it is leaking. Tighten the clamps to hold door shut.  

If starting with chamber in pumped state: 

Use load-lock to load sample stage to position: 

Hit Load/Unload button5. Wait for LL to evacuate, gate valve to open and screen to display Load/Unload dialogue box.  

Use load lock rod to get sample stage into position within main chamber. Remember that you must adjust the nuts shown in image in order to move end of load lock rod up and down. This must be done twice - LoadLock  

 

Figure 1: Load lock Z position adjustment nuts. Hold rod up/down to release pressure on nuts in order to adjust. 

Stage rotation must be used. This is controlled by the DC power supply in constant voltage mode. Adjust voltage knob between 0 – 6 V to set spin speed. 12V absolute max, 4 V recommended during deposition. Turn off power supply when rotation not being used.  

There is a chamber light, switch on to see during the loading process. Turn off after use and ensure that it does not remain on.  

 

Deposition Procedure (DC sputtering) 

Recommend to pump for at least 1 hour if pumping down from atmosphere prior to deposition. High -6 range is a good target if depositing an oxidisable metal.  

Click SET GAS button to start gas flow. Option to flush chamber at up to 200 sccm Ar for 5 – 10 mins in order to help remove any remaining impurities prior to deposition. Reduce gas flow for sputtering. Typical Ar flow during DC metal sputtering: 20 – 50 sccm. Chamber P: 1 – 3 x 10-3 mbar.  

Ensure that electrical cable between gun and power supply is connected. Ensure that grounding cables are also connected. Turn on DC supply for the gun/s you are using.  

Set power setpoint. Typical power usage: 30 – 100 W. 150 W absolute maximum.  

Start MaxTec deposition monitor running for the target material.  

Press start to apply DC. You should see plasma ignite on gun. Close front window shutter to prevent window being coated. You should see deposition thickness increasing and non-zero deposition rate on monitor.  

Open gun shutter to start deposition on sample. Try to restart MaxTec monitor at same time to get accurate thickness reading for your deposition. Refer to MaxTec_FilmMonitor.pdf for monitor info. Section 10.6 for procedure of how to set accurate tooling factor for your material.  

Run sputtering to desired thickness.  

Turn off DC power supply/s.  Also turn off breaker at back of supply.  

Stop gas flow. Press LOAD/UNLOAD and remove sample stage and sample using the loadlock.  

Remove sample from stage and leave sample stage inside loadlock for next user.  

Press LOAD/UNLOAD again to evacuate load-lock.  

Press PUMP in order to leave system in high vac state. System should have roughing pump on, rough valve open and TMP on & near 100% spin.  

Ensure that you leave system with only those status buttons green (plus the TMP OFF/ON control button also green). All other status indicators should be red.  

Make sure that DC sputter and RF supplies are all off, DC supply for stage rotation is off and chamber light is off.  

Make sure that you label what the target is on the sticky notes on chamber door if you had changed target. 

Fill in instrument logbook with session information.  

System can be left in this state.  

Load – lock practice procedure 

Load-lock can be quite difficult at first. It is advised to practice loading sample stage via load-lock with the chamber vented and door open until one is confident that you will be able to do it with door closed and chamber at vacuum. If the sample stage is dropped into the chamber during attempted load-lock usage, one has no choice but to vent and retrieve it.  

Ensure that load-lock is vented, chamber is vented and load-lock rod is in home position. Use AUTO program and VENTLL button first. Then VENT full chamber.  

Once chamber is vented, door is open and the loadlock is also vented and small door open and the rod is in home position, the manual program can be used to enable the practice.  

Hit “EXIT” button on auto program. Wait for that to close.  

On the sputter system master control small VI, select “MANUAL” to open the manual control program. CAUTION: The manual program is dangerous as it allows all valves to be operated manually. Opening the wrong valve could have terrible results! 

We will use this program only to manually open the load-lock gate valve, which cannot be done while chamber vented, using the AUTO program. CAUTION: It is possible to close the gate valve while the load-lock rod is sticking through the gate valve into chamber. This would be a disaster!! Be very careful and do not touch gate load-lock gate valve actuation button on manual control VI unless rod is in home position.  

If rod is in home position, click load-lock button to manually open the gate valve.  

Practice loading the stage while door is open. You will see how you need to adjust the Z-positioning nuts first in order to get the stage onto the shaft and then adjust again in order to relieve the pressure on the bayonet fitting at end of rod, in order to rotate 90* and remove rod from stage without pulling stage back off the shaft.  

When stage loaded, pull rod back to home position. Close gate valve. Close manual program and then reopen the AUTO program.  