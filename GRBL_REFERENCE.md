# GRBL Command Reference

## Motion Commands

| Code  | Description | Notes |
|-------|-------------|-------|
| G00 / G0 | Rapid positioning | Moves at maximum feed rate |
| G01 / G1 | Linear interpolation | Requires F (feed rate) |
| G02 / G2 | Clockwise arc (CW) | Requires I/J or R |
| G03 / G3 | Counter-clockwise arc (CCW) | Requires I/J or R |
| G38.2 | Probe toward workpiece, stop on contact (error if no contact) | Not in 1.1H |
| G38.3 | Probe toward workpiece, no error if no contact | Not in 1.1H |
| G38.4 | Probe away from workpiece, error if no contact | Not in 1.1H |
| G38.5 | Probe away from workpiece, no error if no contact | Not in 1.1H |

## Coordinate System Commands

| Code  | Description |
|-------|-------------|
| G17   | XY plane selection |
| G18   | ZX plane selection |
| G19   | YZ plane selection |
| G20   | Inch units |
| G21   | Millimeter units |
| G90   | Absolute positioning |
| G91   | Incremental positioning |
| G92   | Set coordinate system offset |
| G92.1 | Reset G92 offsets |

## Program Flow

| Code  | Description |
|-------|-------------|
| M0    | Program pause (wait for cycle start) |
| M2    | End of program |
| M30   | End of program with return to start |

## Spindle Control

| Code  | Description |
|-------|-------------|
| M3    | Spindle on, clockwise (CW) |
| M4    | Spindle on, counter-clockwise (CCW) |
| M5    | Spindle stop |

## Coolant Control

> **Note:** Coolant commands (M7, M8) are only available in GRBL 1.1j. They are **not** supported in GRBL 1.1 or 1.1H.

| Code  | Description |
|-------|-------------|
| M7    | Mist coolant on |
| M8    | Flood coolant on |
| M9    | All coolant off |

## GRBL-Specific Commands

| Command | Description |
|---------|-------------|
| `$$`    | View all GRBL settings |
| `$H`    | Run homing cycle |
| `$X`    | Kill alarm lock (unlock) |
| `?`     | Request real-time status report |
| `~`     | Cycle start / resume |
| `!`     | Feed hold (pause motion) |
| `ctrl-X`| Soft-reset GRBL |

### Key `$$` Settings

| Setting | Description |
|---------|-------------|
| $0      | Step pulse time (µs) |
| $1      | Step idle delay (ms) |
| $20     | Soft limits enable |
| $21     | Hard limits enable |
| $22     | Homing cycle enable |
| $100-102| Steps/mm for X, Y, Z |
| $110-112| Max rate (mm/min) for X, Y, Z |
| $130-132| Max travel (mm) for X, Y, Z |

## Version Differences

| Feature            | GRBL 1.1 | GRBL 1.1H | GRBL 1.1j |
|--------------------|----------|-----------|-----------|
| G38.x Probing      | ✅        | ❌         | ✅         |
| M7/M8 Coolant      | ❌        | ❌         | ✅         |
| Spindle PWM        | ✅        | ✅         | ✅         |
| Arc support        | ✅        | ✅         | ✅         |
| Homing             | ✅        | ✅         | ✅         |
| Soft limits        | ✅        | ✅         | ✅         |

**GRBL 1.1H** is a hobbyist-simplified variant that removes probing and coolant support.  
**GRBL 1.1j** is the most feature-complete variant.
