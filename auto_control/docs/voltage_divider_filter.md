# Voltage divider + filter for 0–11 V → ADC (5 V)

Short plan
- Provide a safe, tested voltage divider + capacitor filter that maps up to 11.0 V down to ≤ 5.0 V.
- Use resistors on the order of 22 kΩ as you requested and pick nearest standard values that yield a safe margin.
- Show protection, filter corner calculations, ADC conversion math, and a small BOM.

Checklist
- Divider ratio chosen so 11.0 V → ≤ 5.0 V. ✅
- Example resistor values using ~22 kΩ parts. ✅
- RC filter corner frequency calculations for 0.1 µF and 0.01 µF. ✅
- Protection recommendations (series resistor, clamp diodes/TVS). ✅
- ADC conversion formula and example for 10‑bit MCP/ATmega. ✅

## Recommended schematic (single channel)

```
            +11V signal (max)
                  │
                 R1
               27 kΩ
                  │
     Divider node o--------[100 Ω]-----+----> ADC input (MCP3002 / Arduino AIN)
                  │                   |
                 C=0.1 µF             |  Schottky diodes (BAT54) or clamp to rails
                  │                   |
                 R2                   |
               22 kΩ                  |
                  │                   |
                 GND                 GND
```

![Voltage divider schematic](./voltage_divider_filter.svg)

Figure: single-channel voltage divider + series resistor + clamps. Place the capacitor close to the ADC/divider node.

Notes on the topology
- R1 (top) and R2 (bottom) form the divider. The node between them is the ADC node.
- A small series resistor (100 Ω shown) is added between the divider node and the ADC pin. This limits surge currents and works with the clamp diodes to protect the ADC. If you want stronger protection, use 330 Ω–1 kΩ.
- The capacitor from the divider node to ground forms a low‑pass filter with the divider Thevenin resistance. It smooths noise and helps the ADC sample/hold settle.
- Add Schottky clamp diodes from the ADC pin to VDD and to GND (or a small bidirectional TVS) to catch transients. If the diode clamps to VDD, keep clamped voltage ≤ VDD + 0.6 V.

## Why these resistor values?
- You requested resistors on the order of 22 kΩ. I chose R2 = 22 kΩ (bottom), R1 = 27 kΩ (top) — both are standard E24 values near 22 kΩ.
- Divider ratio: Vout = Vin * R2 / (R1 + R2)
  - With R1=27k and R2=22k: ratio = 22 / (27 + 22) = 22 / 49 ≈ 0.44898
  - At Vin = 11.0 V: Vout ≈ 11.0 * 0.44898 ≈ 4.9388 V (safe under 5.0 V)
- Thevenin (equivalent source) impedance Rth = R1 || R2 = (R1 * R2) / (R1 + R2)
  - Rth ≈ (27k * 22k) / 49k ≈ 12.12 kΩ
  - This is acceptable for a 10‑bit ADC if you use a modest filter capacitor (see next section). If you require faster settling or higher accuracy, buffer the node with an op amp.

## RC filter cutoff frequency
The divider node sees Rth to ground in series with C to ground (approx):

- fc = 1 / (2π * Rth * C)

Calculations with Rth ≈ 12.12 kΩ:
- With C = 0.1 µF (100 nF):
  - fc ≈ 1 / (2π * 12.12e3 * 1e-7) ≈ 131 Hz
  - Good for slow signals (pressure, turbo status) where you only need a few Hz bandwidth.
- With C = 0.01 µF (10 nF):
  - fc ≈ 1 / (2π * 12.12e3 * 1e-8) ≈ 1.31 kHz
  - Faster response, still filtered; pick this if you want quicker updates.

Choose C depending on how fast you need to respond:
- Pressure gauge telemetry: 0.1 µF is fine (stable readings, less noise).
- Faster control loops: 10 nF or lower.

## Protection recommendations
- Series resistor (100–330 Ω): limits surge currents into clamp diodes and ADC pin.
- Clamp diodes: small Schottky diodes (BAT54 or similar) from ADC pin to VDD/GND. They clamp small overvoltage to safe levels and are fast with low forward drop.
- TVS diode: for harsher environments or long cable runs, place a bidirectional TVS (e.g., SMBJ5.0CA or similar rated near 5–6 V) across the ADC input to ground for transient suppression.
- Input surge / common mode: ensure sensor and MCU grounds are tied and routed carefully.

If you don't have Schottky diodes
- Increase the series resistor Rs to 330 Ω–1 kΩ (1 kΩ preferred) and keep the filter capacitor; the larger Rs limits current into the MCU's internal protection diodes if the node is driven above VDD or below GND. This is the safest temporary measure but slows ADC settling (increase sample time or use a larger capacitor accordingly).
- Use small-signal silicon diodes (1N4148 or 1N4148W) as clamp diodes if available: they work as clamps but have a higher forward voltage (~0.6–0.8 V) than Schottkys, so expect a higher clamped node and therefore use a larger Rs (≥330 Ω) and test on the bench.
- A 5.1 V Zener (or 5.6 V) can be used to clamp the node, but it needs a series resistor and can leak at low voltages; prefer this only for coarse protection, not precision signals.
- If you have a TVS (recommended), use it instead of diodes — a unidirectional 5 V TVS or a small bidirectional part across the divider node to ground will clamp fast and cleanly.
- Long term / best: add a simple buffer (rail‑to‑rail op amp) between the divider and ADC; the buffer protects the ADC and presents low source impedance.

Testing note: after implementing any substitute, verify the divider node with a bench supply and oscilloscope/multimeter before connecting to the MCU. Confirm the node never exceeds VDD + 0.6 V (with your chosen Rs) under fault conditions.

## ADC conversion math (10‑bit example)
Assume:
- ADC reference = Vref = 5.0 V
- ADC counts N range 0..1023 (10‑bit)
- Divider R1 = 27k, R2 = 22k

1) ADC voltage (divider node):
- Vdiv = N / 1023 * Vref

2) Recover original Vin:
- Vin = Vdiv * (R1 + R2) / R2
- With numbers: Vin = N / 1023 * 5.0 * (27k + 22k) / 22k
- Simplify factor: (27 + 22) / 22 = 49 / 22 ≈ 2.22727
- Thus: Vin ≈ N / 1023 * 5.0 * 2.22727 ≈ N / 1023 * 11.136

Example
- N = 512 → Vin ≈ 512/1023 * 11.136 ≈ 5.57 V
- N = 1023 → Vin ≈ 1023/1023 * 11.136 ≈ 11.136 V (slightly above 11 because Vref = 5.0, divider maps 11.0 to 4.9388 V)

Note: using exact factor (R1,R2 measured) and measured Vref yields the best accuracy — calibrate in software.

## Expected resolution and LSB
- LSB (on Vin scale) = Vin_max / 1023 where Vin_max is the scaled top-of-scale using the exact divider mapping.
- With the chosen divider mapped 11.0 V → 4.9388 V (ADC top ~ 5.0), the effective factor above gives ~11.136 V at ADC full-scale. However actual maximum measurable Vin before clipping is ~11.0 V, so a practical LSB ≈ 11.0 / 1023 ≈ 10.75 mV.
- Typical errors (datasheet): INL ±0.5 LSB, DNL ±0.25 LSB, offset/gain a few LSB — calibrate to reduce.

## Component BOM (per channel)
- R1 = 27 kΩ, 1% or 5% (1/4 W) — top
- R2 = 22 kΩ, 1% or 5% — bottom
- C = 0.1 µF (100 nF), X7R ceramic — (or 10 nF if you want higher bandwidth)
- Series resistor Rs = 100 Ω (or 220 Ω) 1/4 W
- Schottky diodes: 2 × BAT54S or single-ended BAT54 to VDD/GND (or equivalent low Vf diode pair)
- Optional: TVS (bidirectional) near ADC pin for heavy transients
- Optional: op amp for buffer (e.g., TLV237x for single-supply rail-to-rail) if you want low source impedance

Substitutes if you don't have Schottky diodes:
- Small-signal silicon diodes (1N4148) — slower/higher Vf, increase Rs to ≥330 Ω and bench-test.
- Power/signal diodes (1N400x) — only for very slow signals and coarse protection; use with larger Rs (≥1 kΩ).
- 5.1 V Zener (BZX55 or similar) for coarse clamping (needs series resistor).

## PCB / wiring tips
- Place the filter capacitor close to the ADC pin / divider node.
- Keep analog ground return short and return to MCU ground at a single point.
- If sensors are remote, consider placing the divider and MCP3002 physically close to the sensor to reduce pickup (use twisted pair and shielded cable for long runs).

## Calibration steps (software)
1. With Vin = 0.00 V, read ADC raw N0. Compute offset voltage Voffset = N0/1023 * Vref * (R1+R2)/R2.
2. With a known reference voltage (e.g., Vin = 5.00 V or 11.00 V if safe), read Nref. Compute scale error and correct with gain factor.
3. Apply linear correction: Vin_corrected = a * Vin_raw + b (solve a,b from two-point calibration).

---

If you want, I can also:
- Produce a small wiring diagram image (SVG) and add it to `auto_control/docs/voltage_divider_filter.md`.
- Provide a short Arduino code snippet that reads MCP3002 (SPI) and converts counts → volts using the exact factor and a calibration routine.

Which of those would you like next?
