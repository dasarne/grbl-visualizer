# GCode Lisa — Architecture

## Module Organization

```
src/
├── gcode/
│   ├── commands.py       # GRBL command constants and GRBLCommand dataclass
│   ├── grbl_versions.py  # Version feature matrix and version-aware helpers
│   ├── parser.py         # G-Code line/file parser
│   └── tokens.py         # Tokenizer (lexer)
├── geometry/
│   ├── bounds.py         # BoundingBox calculation
│   ├── path.py           # ToolPath and PathSegment building
│   └── transforms.py     # Coordinate system transforms
├── analyzer/
│   ├── analyzer.py       # Warning and compatibility checker
│   └── optimizer.py      # Optimization hints
└── ui/
    ├── main_window.py    # QMainWindow — dual-view layout, menus, toolbar
    ├── editor_panel.py   # QPlainTextEdit-based G-Code editor
    ├── canvas_panel.py   # matplotlib FigureCanvas visualization panel
    ├── settings_dialog.py# GRBL version selector and feature table
    └── widgets.py        # Reusable custom widgets
```

## GRBL Version Support Matrix

| Feature          | GRBL 1.1 | GRBL 1.1H | GRBL 1.1j |
|------------------|----------|-----------|-----------|
| G00 Rapid        | ✅        | ✅         | ✅         |
| G01 Linear       | ✅        | ✅         | ✅         |
| G02/G03 Arc      | ✅        | ✅         | ✅         |
| G38.x Probing    | ✅        | ❌         | ✅         |
| M7/M8 Coolant    | ❌        | ❌         | ✅         |
| Spindle speed    | ✅        | ✅         | ✅         |

## Data Flow

```
File on disk
    │
    ▼
GCodeTokenizer   →  Token stream
    │
    ▼
GCodeParser      →  GCodeProgram (list of GCodeLine)
    │
    ├──▶  GCodeAnalyzer   →  list[AnalysisWarning]
    │
    ├──▶  build_toolpath  →  ToolPath (list of PathSegment)
    │         │
    │         └──▶  calculate_bounds  →  BoundingBox
    │
    └──▶  UI layer
              ├─  EditorPanel   (text, line highlighting)
              └─  CanvasPanel   (matplotlib rendering)
```

## Dual-View Interaction Model

The bidirectional binding between the editor and canvas is implemented via Qt signals:

- `EditorPanel.line_selected(int)` → `MainWindow._on_editor_line_selected(line_number)` → `CanvasPanel.highlight_segment(line_number)`
- `CanvasPanel.segment_selected(int)` → `MainWindow._on_canvas_segment_selected(line_number)` → `EditorPanel.highlight_line(line_number)`

Each `PathSegment` stores the source `line_number` from the parsed G-Code, enabling O(1) lookup in both directions.

## Technology Choices Rationale

| Choice | Reason |
|--------|--------|
| PyQt6  | Native look-and-feel on Linux/KDE, mature signal/slot system, good matplotlib integration |
| matplotlib | Proven 2D/3D plotting, FigureCanvas integrates cleanly with PyQt6 |
| dataclasses | Zero-boilerplate value objects for GCodeLine, PathSegment, etc. |
| numpy  | Efficient coordinate array operations for large G-Code files |
| pytest | Industry-standard, good fixture system, pytest-qt for Qt testing |
