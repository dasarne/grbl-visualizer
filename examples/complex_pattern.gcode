; Complex Pattern - multiple passes with varied depth
; Demonstrates probing (GRBL 1.1 / 1.1j only), feed rate changes,
; and multi-pass cutting strategy.
G21          ; mm
G90          ; absolute
; --- Pass 1: 0.5mm depth ---
G0 Z5
G0 X0 Y0
M3 S1200
G1 Z-0.5 F80
G1 X20 Y0 F600
G1 X20 Y20
G1 X0  Y20
G1 X0  Y0
G0 Z5
; --- Pass 2: 1mm depth ---
G1 Z-1.0 F80
G1 X20 Y0 F400
G1 X20 Y20
G1 X0  Y20
G1 X0  Y0
G0 Z5
M5
M30
