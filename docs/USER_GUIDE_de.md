# GCode Lisa - Benutzerhandbuch



Mit Vertrauen schneiden.

Weniger verschwenden.


## Interface-Übersicht

Wenn GCode Lisa startet, sehen Sie drei Felder nebeneinander:



| Panel | Zweck |
| - | - |
| **Kommentare** (links) | Listet alle Kommentarzeilen aus der G-Code-Datei auf - klicken Sie auf einen Kommentar, um zu ihm zu springen |
| **Herausgeber** (Mitte) | G-Code-Editor mit Syntaxhervorhebung und Zeilennummern |
| **Leinwand** (rechts) | Interaktive 3D-Werkzeugwegvisualisierung |


Die **Statusleiste** am unteren Rand zeigt das aktive Dialektprofil und alle erkannten Probleme an.


## Laden einer Datei

Öffnen Sie eine G-Code-Datei über **Datei → Öffnen**`(Strg+O`) oder indem Sie eine aktuelle Datei über **Datei → Aktuelle Dateien** öffnen.

Unterstützte Formate: `.gcode`, `.nc`, `.ngc`, `.tap`

Nach dem Laden werden der Editor und die Leinwand gleichzeitig aktualisiert:



- Das **Feld Kommentare** (links, dunkel) listet alle Kommentare/Operationsbezeichnungen in der Datei auf. Klicken Sie auf einen Eintrag, um zu dieser Zeile im Editor zu springen und das entsprechende Pfadsegment auf der Leinwand zu markieren.

- Die **Statusleiste** (unten) zeigt den erkannten Dialekt (z. B. *Erkannter Dialekt: GRBL (80%)*), den aktiven Profilselektor und einen anklickbaren Problemzähler, wenn Probleme gefunden wurden.

- Das Feld für **die Werkstückabmessungen** in der unteren rechten Ecke der Arbeitsfläche zeigt den Begrenzungsrahmen (X/Y/Z-Ausdehnung) an.


## Verstehen der Visualisierung

### Axonometrische 3D-Ansicht

Die Leinwand rendert eine axonometrische (isometrische) Projektion des Werkzeugwegs:



- **Durchgehende blaue Linien** - Schneidezüge (G1/G2/G3)

- **Gestrichelte orangefarbene Linien** - Eilgangbewegungen (G0)

- **Grauer Kasten** - Werkstückbegrenzungsrahmen

- **Achsenmarkierungen** - X- (rot), Y- (grün), Z-Achse (blau) am Ursprung

### Ansicht Würfel

Der Orientierungswürfel in der oberen rechten Ecke der Leinwand zeigt die aktuelle Blickrichtung an:



Klicken Sie auf eine beliebige Fläche des Würfels, um die Ansicht in einer orthografischen Standardausrichtung (Oben, Vorne, Seitlich usw.) zu fixieren. Die Würfelbeschriftung zeigt den aktuellen Modus*(3D*, *Oben*, *Vorne*, ...).

### Navigation

| Aktion | Ergebnis |
| - | - |
| Mausrad | Vergrößern/Verkleinern |
| Ziehen Sie mit der linken Maustaste | Pan |
| Rechts-ziehen | Drehen Sie |
| Strg + rechts-ziehen | Drehen (alternativ) |


Das Navigationsschema der Maus kann in den **Einstellungen** (siehe unten) geändert werden, um es an FreeCAD, Blender, SolidWorks und andere CAD-Pakete anzupassen.


## Der Herausgeber

Der Editor bietet Syntaxhervorhebung für G-Code:



- **Blau** - G- und M-Befehle (G0, G1, M3, ...)

- **Rot / Grün / Blau** - X, Y, Z Koordinaten

- **Orange** - I, J Lichtbogenparameter

- **Lila** - F Vorschubgeschwindigkeit

- **Fettes Grün** - Kommentare (Klammern `(...)` und Semikolon `; ...)`

Zeilen mit Analyseproblemen werden im Hintergrund des Editors hervorgehoben. Fahren Sie mit der Maus über ein Token, um einen **kontextbezogenen Tooltip** anzuzeigen:



Die QuickInfo zeigt den Wert des Tokens (z. B. *X-Koordinate: 42.415*) und alle Analysewarnungen, die für diese Zeile gelten.

### Zeilenauswahl (Editor + Canvas synchron)

Die Auswahl ist zeilenbasiert und über Editor, Suchbereich und Canvas-Markierung vereinheitlicht.

| Interaktion | Ergebnis |
| - | - |
| Klick | Eine Zeile auswählen und Anker setzen |
| Umschalt+Klick | Zusammenhängenden Bereich vom Anker bis zur angeklickten Zeile auswählen |
| Strg+Klick | Einzelne Zeilen umschalten (nicht zusammenhängende Mehrfachauswahl) |
| Ziehen mit linker Maustaste | Auswahlbereich beim Ziehen erweitern |
| Umschalt+Pfeil | Zusammenhängenden Bereich vom Anker aus erweitern |
| Pfeiltasten | Zur Ein-Zeilen-Auswahl wechseln |
| Strg+A | Alle Zeilen auswählen |
| Strg+C / Strg+X | Ausgewählte Zeilen kopieren / ausschneiden |
| Entf / Backspace | Ausgewählte Zeilen löschen |
| Druckbares Zeichen tippen | Ausgewählte Zeilen durch das eingegebene Zeichen ersetzen |

Doppelklick wird bewusst wie Ein-Zeilen-Auswahl behandelt (kein wortweiser Auswahlmodus).

Wenn Zeilen ausgewählt sind, bleiben Editor und Canvas synchron.

### Suchen & Ersetzen

Öffnen Sie Suchen & Ersetzen mit `Strg+F` oder `Strg+H`. Geben Sie in das Suchfeld ein und verwenden Sie die Schaltflächen, um zu den Übereinstimmungen zu navigieren oder sie einzeln/alle auf einmal zu ersetzen.


## Kommentar Browser

Das linke Feld listet alle Kommentarzeilen in der Datei auf:



Klicken Sie auf einen beliebigen Eintrag, um zu der entsprechenden Zeile im Editor zu springen und das passende Pfadsegment auf der Leinwand zu markieren. Dies erleichtert das Navigieren in einer Datei, die aus einer CAM-Software mit benannten Operationen exportiert wurde.


## Dialekt-Profile und automatische Erkennung

GCode Lisa unterstützt mehrere G-Code-Dialekte: **GRBL 1.1**, **GRBL 1.1H**, **GRBL 1.1j**, **LinuxCNC** und **Marlin**.

Beim Laden einer Datei erkennt GCode Lisa automatisch den wahrscheinlichsten Dialekt anhand der verwendeten Befehle. Der erkannte Dialekt und das derzeit aktive Profil werden in der **Statusleiste** angezeigt:



- **Erkannter Dialekt** - das Ergebnis der automatischen Analyse, angezeigt mit einer prozentualen Konfidenz

- **Aktives Profil** - steuert, welche Befehle als gültig angesehen werden; Standardeinstellung ist *Auto* (folgt dem erkannten Dialekt)

Um den Dialekt dauerhaft außer Kraft zu setzen, wählen Sie ein Profil aus der Dropdown-Liste. Die Änderungen werden sofort wirksam und werden für die nächste Sitzung gespeichert.


## Einstellungen

Öffnen Sie **Datei → Einstellungen**, um die globalen Einstellungen zu konfigurieren:



| Einstellung | Beschreibung |
| - | - |
| **Profil des Dialekts** | Standardprofil, wenn die *automatische* Erkennung ausgeschaltet ist |
| **Erkanntes Profil beim Laden einer Datei verwenden** | Wenn diese Option aktiviert ist, wird das aktive Profil bei jedem Öffnen einer Datei automatisch aktualisiert. |
| **Sprache** | Sprache der Benutzeroberfläche (Englisch / Deutsch) |
| **Navigation mit der Maus** | Navigationsschema: CAD (FreeCAD), Blender, SolidWorks, und viele andere |


In der Befehlstabelle unten im Dialogfeld werden alle G-Code-Befehle aufgelistet und es wird angegeben, ob sie von dem ausgewählten Profil unterstützt werden.


## Meldungen und Warnungen

Wenn GCode Lisa mögliche Probleme in der geladenen Datei erkennt, zeigt die Statusleiste einen anklickbaren Problemzähler (z.B. *Fehler:1, Info:1*). Klicken Sie darauf - oder drücken Sie `Strg+I` - um den Dialog Meldungen zu öffnen:



Jede Zeile zeigt:

| Säule | Bedeutung |
| - | - |
| **Typ** | Schweregrad: Fehler (rot), Warnung (gelb), Info (blau) |
| **Nachricht** | Beschreibung des Themas |
| **Leitung** | Zeilennummer im Editor (Zeile anklicken, um dorthin zu springen) |


Verwenden Sie die **Filter-Dropdown-Liste** (Alle / Fehler / Warnung / Info) und das **Textsuchfeld**, um die Liste einzugrenzen. Klicken Sie auf eine Spaltenüberschrift, um zu sortieren.

### Warnarten erklärt

| Typ | Beispiel | Aktion |
| - | - | - |
| **Fehler** | *G54 wird von GRBL nicht unterstützt* | Befehl wird vom aktiven Profil nicht unterstützt - überprüfen Sie die Dialekteinstellung oder entfernen Sie den Befehl |
| **Warnung** | *G1 hat keine Vorschubgeschwindigkeit - fügen Sie einen F-Parameter hinzu* | Potenziell gefährliche Unterlassung - vor der Verschiebung einen expliziten F-Wert hinzufügen |
| **Infos** | *Kein expliziter Arbeitskoordinatenursprung gefunden* | Nur zu Ihrer Information - stellen Sie sicher, dass die Maschine vor dem Betrieb richtig eingestellt ist. |



## Tastaturkurzbefehle

| Abkürzung | Aktion |
| - | - |
| `Strg+N` | Neues Fenster |
| `Strg+O` | Datei öffnen |
| `Strg+S` | Datei speichern |
| `Strg+Z` | Rückgängig machen |
| `Strg+Y` | Redo |
| `Strg+A` | Alle Zeilen auswählen |
| `Strg+C` | Ausgewählte Zeilen kopieren |
| `Strg+X` | Ausgewählte Zeilen ausschneiden |
| `Entf` / `Backspace` | Ausgewählte Zeilen löschen |
| `Strg+V` | Kleister |
| `Strg+F` | finden. |
| `Strg+H` | Suchen & Ersetzen |
| `Strg+I` | Dialogfeld Nachrichten öffnen |
| `Strg+Q` | Beenden Sie |


