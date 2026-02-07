import sys
import serial
import threading
import re
import math
import statistics
from collections import deque
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QTimer
import pyqtgraph as pg
from PyQt6.QtGui import QFont

# --- CONFIGURATION ---
PORT_ARDUINO = "COM9"  # CHECK YOUR PORT (e.g., COM3 on Windows)
BAUD_RATE = 115200             # Match the Arduino Code!
BUFFER_SIZE = 300
TOLERANCE_MM = 5.0             # Sensitivity: +/- 5mm triggers defect

class SerialWorker(QObject):
    valoare_signal = pyqtSignal(float)

    def __init__(self):
        super().__init__()
        self.running = True

    def citeste_serial(self):
        try:
            ser = serial.Serial(PORT_ARDUINO, BAUD_RATE, timeout=1)
            print(f"[OK] Connected to {PORT_ARDUINO}")
            while self.running:
                line = ser.readline().decode("utf-8", errors='ignore').strip()
                if not line:
                    continue
                
                # Regex to find float number in string
                match = re.search(r"[-+]?\d*[\.,]?\d+", line)
                if match:
                    try:
                        valoare = float(match.group(0).replace(",", "."))
                        # Arduino sends cm, convert to mm for better precision display
                        valoare_mm = valoare * 10 
                        self.valoare_signal.emit(valoare_mm)
                    except ValueError:
                        pass
        except serial.SerialException:
            print("[ERROR] Cannot connect to Arduino! Check port.")

class DefectoscopGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ultrasonic Surface Profiler (Defectoscope)")
        self.setStyleSheet("background-color: #2b2b2b;") # Dark Theme
        self.setFixedSize(800, 600)
        
        self.data_buffer = deque(maxlen=BUFFER_SIZE)
        self.reference_distance = None # The "Zero" point
        
        layout = QVBoxLayout()

        # --- HEADER ---
        self.label_titlu = QLabel("SURFACE DEPTH (mm)")
        self.label_titlu.setStyleSheet("color: white; font-size: 18px; font-weight: bold;")
        self.label_titlu.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # --- MAIN VALUE ---
        self.label_valoare = QLabel("--")
        self.label_valoare.setStyleSheet("color: #00ffcc; font-size: 80px; font-weight: bold;")
        self.label_valoare.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # --- STATUS ---
        self.label_status = QLabel("NOT CALIBRATED")
        self.label_status.setStyleSheet("color: orange; font-size: 24px; font-weight: bold; padding: 10px;")
        self.label_status.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # --- CALIBRATION BUTTON ---
        self.btn_calibrate = QPushButton("CALIBRATE (ZERO)")
        self.btn_calibrate.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_calibrate.setStyleSheet("""
            QPushButton {
                background-color: #444; color: white; border-radius: 5px; padding: 10px; font-size: 16px; font-weight: bold;
            }
            QPushButton:hover { background-color: #666; }
            QPushButton:pressed { background-color: #888; }
        """)
        self.btn_calibrate.clicked.connect(self.calibrate_sensor)

        # --- GRAPH ---
        self.graph = pg.PlotWidget()
        self.graph.setBackground('#1e1e1e')
        self.graph.showGrid(x=True, y=True, alpha=0.3)
        self.graph.getAxis("left").setPen(pg.mkPen(color="white"))
        self.graph.getAxis("bottom").setPen(pg.mkPen(color="white"))
        
        # Create a "Reference Line" (The Zero Point)
        self.ref_line = pg.InfiniteLine(angle=0, pen=pg.mkPen('y', width=2, style=Qt.PenStyle.DashLine))
        self.graph.addItem(self.ref_line)
        
        self.curve = self.graph.plot(pen=pg.mkPen(color="#00ffcc", width=3))

        # --- LAYOUT ASSEMBLY ---
        layout.addWidget(self.label_titlu)
        layout.addWidget(self.label_valoare)
        layout.addWidget(self.label_status)
        layout.addWidget(self.btn_calibrate) # Added Button
        layout.addWidget(self.graph)
        self.setLayout(layout)

        # --- SERIAL THREAD ---
        self.worker = SerialWorker()
        self.worker.valoare_signal.connect(self.update_gui)
        self.thread = threading.Thread(target=self.worker.citeste_serial)
        self.thread.daemon = True
        self.thread.start()

        # --- GRAPH TIMER ---
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_graph)
        self.timer.start(50)

    def calibrate_sensor(self):
        """Sets the current average distance as the 'Normal' surface level"""
        if len(self.data_buffer) < 10:
            self.label_status.setText("WAITING FOR DATA...")
            return
            
        # Take average of last 10 readings to avoid noise
        recent_data = list(self.data_buffer)[-10:]
        self.reference_distance = statistics.mean(recent_data)
        
        # Update Graph Reference Line
        self.ref_line.setPos(self.reference_distance)
        self.label_status.setText("CALIBRATED - READY TO SCAN")
        self.label_status.setStyleSheet("color: #00ffcc; font-size: 24px; font-weight: bold;")
        print(f"Calibrated at: {self.reference_distance} mm")

    def update_gui(self, valoare: float):
        # Store Data
        self.data_buffer.append(valoare)
        
        # Update Text
        self.label_valoare.setText(f"{valoare:.1f}")
        
        # Logic: Only check defects if Calibrated
        if self.reference_distance is not None:
            diff = valoare - self.reference_distance
            
            # CASE 1: HOLE (Distance Increases)
            if diff > TOLERANCE_MM:
                self.setStyleSheet("background-color: #800000;") # Dark Red
                self.label_status.setText(f"⚠ HOLE DETECTED (+{diff:.1f}mm)")
                self.label_valoare.setStyleSheet("color: red; font-size: 80px; font-weight: bold;")

            # CASE 2: BUMP/OBSTACLE (Distance Decreases)
            elif diff < -TOLERANCE_MM:
                self.setStyleSheet("background-color: #804000;") # Dark Orange
                self.label_status.setText(f"⚠ BUMP DETECTED ({diff:.1f}mm)")
                self.label_valoare.setStyleSheet("color: orange; font-size: 80px; font-weight: bold;")

            # CASE 3: NORMAL
            else:
                self.setStyleSheet("background-color: #2b2b2b;") # Reset to Grey
                self.label_status.setText("SURFACE NORMAL")
                self.label_valoare.setStyleSheet("color: #00ffcc; font-size: 80px; font-weight: bold;")

    def update_graph(self):
        if len(self.data_buffer) > 0:
            values = list(self.data_buffer)
            self.curve.setData(values)
            
            # Keep the graph centered around the reference if it exists
            if self.reference_distance:
                self.graph.setYRange(self.reference_distance - 50, self.reference_distance + 50)

    def closeEvent(self, event):
        self.worker.running = False
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DefectoscopGUI()
    window.show()
    sys.exit(app.exec())