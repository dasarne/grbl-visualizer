; Simple Square - 10mm x 10mm
; Material: Wood, Depth: 1mm
G21 ; Set units to millimeters
G90 ; Absolute positioning
G0 Z5 ; Safe height
G0 X0 Y0 ; Move to origin
M3 S1000 ; Start spindle at 1000 RPM
G1 Z-1 F100 ; Plunge to cutting depth
G1 X10 Y0 F500 ; Cut right
G1 X10 Y10 F500 ; Cut up
G1 X0 Y10 F500 ; Cut left
G1 X0 Y0 F500 ; Cut back to start
G0 Z5 ; Lift to safe height
M5 ; Stop spindle
M30 ; End program
