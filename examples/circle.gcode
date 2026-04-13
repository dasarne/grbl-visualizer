; Circle - radius 5mm, center at (10, 10)
G21
G90
G0 Z5
G0 X15 Y10 ; Move to start point (center_x + radius, center_y)
M3 S1000
G1 Z-1 F100
G2 X15 Y10 I-5 J0 F500 ; Full circle arc
G0 Z5
M5
M30
