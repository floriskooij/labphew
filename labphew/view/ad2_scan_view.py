"""
labphew.view.monitor_view.py
==============
The MonitorWindow class displays a plot or other data that updates over time at a given rate. (TODO: or view images)
All the processes that are not relating to user interaction are handled by the Operator class in the model folder

To change parameters the user needs to open the configuration window.
To execute a special routine, one should run an instance of scan_view.
For inspiration: the initiation of scan_view routines can be implemented as buttons on the monitor_view
TODO:
    - build the UI without a design file necessary
    - connect the UI parameters to config file

"""

import os
import numpy as np
import pyqtgraph as pg   # used for additional plotting features

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import * # QMainWindow, QWidget, QPushButton, QVBoxLayout, QApplication, QSlider, QLabel, QMessageBox
from PyQt5.QtGui import QFont, QIcon
from labphew.core.tools.gui_tools import set_spinbox_stepsize

from labphew.core.base.general_worker import WorkThread

import logging

# TODO: the following imports are necessary for child windows, they have to be adjusted and tested
#from .config_view import ConfigWindow  # to adjust experiment parameters
#from .scan_view import ScanWindow      # to perform single scan


class ScanWindow(QMainWindow):
    def __init__(self, operator, monitor=None, parent=None):
        self.logger = logging.getLogger(__name__)
        super().__init__(parent)
        self.setWindowTitle('Analog Discovery 2')
        self.operator = operator
        self.monitor = monitor

        # # For loading a .ui file (created with QtDesigner):
        # p = os.path.dirname(__file__)
        # uic.loadUi(os.path.join(p, 'design/UI/main_window.ui'), self)

        self.set_UI()


        # create thread and timer objects for scan
        self.scan_timer = QTimer()
        self.scan_timer.timeout.connect(self.update_scan)
        self.scan_thread = WorkThread(self.operator.do_scan)


        self.show()  # display the GUI

        # TODO: uncomment for testing the child windows
        # self.config_window = ConfigWindow(operator, parent=self)
        # self.config_window.propertiesChanged.connect(self.update_properties)
        # self.actionConfig.triggered.connect(self.config_window.show)
        #
        # self.scan_window = ScanWindow(operator)
        # self.actionScan.triggered.connect(self.scan_window.show)

    def set_UI(self):
        """
        Code-based generation of the user-interface based on PyQT
        """

        ### General layout
        central_widget = QWidget()
        central_layout = QHBoxLayout(central_widget)

        # Layout for left hand controls
        control_layout = QVBoxLayout()

        ### Scan box
        self.box_scan = QGroupBox('Scan')
        layout_scan = QVBoxLayout()
        self.box_scan.setLayout(layout_scan)
        control_layout.addWidget(self.box_scan)

        layout_scan_form = QFormLayout()
        layout_scan.addLayout(layout_scan_form)
        layout_scan_buttons = QHBoxLayout()
        layout_scan.addLayout(layout_scan_buttons)

        self.scan_start_spinbox = QDoubleSpinBox()
        self.scan_start_spinbox.setSuffix('V')
        self.scan_start_spinbox.setMinimum(-100)  # limits are checked by the Operator
        self.scan_start_spinbox.valueChanged.connect(self.scan_start_value)
        self.scan_start_spinbox.setSingleStep(0.1)

        self.scan_stop_spinbox = QDoubleSpinBox()
        self.scan_stop_spinbox.setSuffix('V')
        self.scan_stop_spinbox.setMinimum(-100)  # limits are checked by the Operator
        self.scan_stop_spinbox.valueChanged.connect(self.scan_stop_value)
        self.scan_stop_spinbox.setSingleStep(0.1)

        self.scan_step_spinbox = QDoubleSpinBox()
        self.scan_step_spinbox.setSuffix('V')
        self.scan_step_spinbox.setMinimum(-100)  # limits are checked by the Operator
        self.scan_step_spinbox.valueChanged.connect(self.scan_step_value)
        self.scan_step_spinbox.setSingleStep(0.1)


        self.scan_start_label = QLabel('start')
        self.scan_stop_label = QLabel('stop')
        self.scan_step_label = QLabel('step')
        layout_scan_form.addRow(self.scan_start_label, self.scan_start_spinbox)
        layout_scan_form.addRow(self.scan_stop_label, self.scan_stop_spinbox)
        layout_scan_form.addRow(self.scan_step_label, self.scan_step_spinbox)

        self.start_button = QPushButton('Start')
        self.start_button.clicked.connect(self.start_scan)
        self.pause_button = QPushButton('Pause')
        self.pause_button.clicked.connect(self.pause)
        self.stop_button = QPushButton('Stop')
        self.stop_button.clicked.connect(self.stop)
        self.kill_button = QPushButton('Kill')
        self.kill_button.clicked.connect(self.kill_scan)
        # Haven't decided what names are best. Suggestions:
        # start, pause, interrupt, stop, abort, quit, kill

        layout_scan_buttons.addWidget(self.start_button)
        layout_scan_buttons.addWidget(self.pause_button)
        layout_scan_buttons.addWidget(self.stop_button)
        layout_scan_buttons.addWidget(self.kill_button)

        ### Graphs:
        self.graph_win = pg.GraphicsWindow()
        self.graph_win.resize(1000, 600)
        self.plot1 = self.graph_win.addPlot()
        self.curve1 = self.plot1.plot(pen='y')

        # Add an empty widget at the bottom of the control layout to make layout nicer
        dummy = QWidget()
        dummy.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        control_layout.addWidget(dummy)
        # Add control layout and graph window to central layout and apply central layout to window
        central_layout.addLayout(control_layout)
        central_layout.addWidget(self.graph_win)
        self.setCentralWidget(central_widget)

        self.apply_properties(self.operator.properties)
        self.reset_fields()

    def apply_properties(self, props):
        """
        Apply properties dictionary to gui elements
        :param props: properties
        :type props: dict
        """

        self.operator._set_scan_start(self.operator.properties['scan']['start'])  # this optional line checks validity
        self.scan_start_spinbox.setValue(self.operator.properties['scan']['start'])

        self.operator._set_scan_stop(self.operator.properties['scan']['stop'])  # this optional line checks validity
        self.scan_stop_spinbox.setValue(self.operator.properties['scan']['stop'])

        self.operator._set_scan_start(self.operator.properties['scan']['step'])  # this optional line checks validity
        self.scan_step_spinbox.setValue(self.operator.properties['scan']['step'])

        if 'name' in self.operator.properties['scan']:
            self.box_scan.setTitle(self.operator.properties['scan']['name'])
            self.plot1.setTitle(props['scan']['name'])

        xlabel = self.operator.properties['scan']['x_label']
        ylabel = self.operator.properties['scan']['y_label']
        self.plot1.setLabel('bottom', xlabel[0], units=xlabel[1])
        self.plot1.setLabel('left', ylabel[0], units=ylabel[1])

        # self.ao1_label.setText(props['ao'][1]['name'])
        # self.ao2_label.setText(props['ao'][2]['name'])
        #
        # self.time_step_spinbox.setValue(props['monitor']['time_step'])
        # self.plot_points_spinbox.setValue(props['monitor']['plot_points'])
        #

    def scan_start_value(self):
        """
        Called when Scan Start spinbox is modified.
        Updates the parameter using a method of operator (which checks validity and also fixes the sign of step) and
        forces the (corrected) parameter in the gui elements
        """
        self.operator._set_scan_start(self.scan_start_spinbox.value())
        self.scan_start_spinbox.setValue(self.operator.properties['scan']['start'])
        self.scan_step_spinbox.setValue(self.operator.properties['scan']['step'])
        set_spinbox_stepsize(self.scan_start_spinbox)

    def scan_stop_value(self):
        """
        Called when Scan Stop spinbox is modified.
        Updates the parameter using a method of operator (which checks validity and also fixes the sign of step) and
        forces the (corrected) parameter in the gui elements
        """
        self.operator._set_scan_stop(self.scan_stop_spinbox.value())
        self.scan_stop_spinbox.setValue(self.operator.properties['scan']['stop'])
        self.scan_step_spinbox.setValue(self.operator.properties['scan']['step'])
        set_spinbox_stepsize(self.scan_stop_spinbox)

    def scan_step_value(self):
        """
        Called when Scan Step spinbox is modified.
        Updates the parameter using a method of operator (which checks validity) and forces the (corrected) parameter in the gui element
        """
        self.operator._set_scan_step(self.scan_step_spinbox.value())
        self.scan_step_spinbox.setValue(self.operator.properties['scan']['step'])
        set_spinbox_stepsize(self.scan_step_spinbox)

    def reset_fields(self):
        self.start_button.setEnabled(True)
        self.pause_button.setText('Pause')
        self.pause_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.scan_start_spinbox.setEnabled(True)
        self.scan_stop_spinbox.setEnabled(True)
        self.scan_step_spinbox.setEnabled(True)
        # Reset all flow control flags
        self.operator._busy = False
        self.operator._pause = False
        self.operator._stop = False

    def start_scan(self):
        """
        Called when start button is pressed.
        Starts the monitor (thread and timer) and disables some gui elements
        """
        if self.operator._busy:
            self.logger.debug("Operator is busy")
            return
        else:
            self.logger.debug('Starting scan')
            self.start_button.setEnabled(False)
            self.pause_button.setEnabled(True)
            self.stop_button.setEnabled(True)
            # self.operator._stop = False  # enable operator monitor loop to run
            self.scan_thread.start()  # start the operator monitor
            self.scan_timer.start(self.operator.properties['scan']['gui_refresh_time'])  # start the update timer
            self.scan_start_spinbox.setEnabled(False)
            self.scan_stop_spinbox.setEnabled(False)
            self.scan_step_spinbox.setEnabled(False)

    def pause(self):
        if not self.operator._pause:
            self.operator._pause = True
            self.pause_button.setText('Continue')
        else:
            self.operator._pause = False
            self.pause_button.setText('Pause')

    def stop(self):
        """
        Stop all loop threads:
        - flags the operator to stop
        - uses the Workthread stop method to wait a bit for the operator to finish, or terminate thread if timeout occurs
        """
        self.logger.debug('Stopping operator')
        self.stop_button.setEnabled(False)
        self.operator._stop = True
        if self.scan_thread.isRunning():
            self.scan_thread.stop(self.operator.properties['scan']['stop_timeout'])
        self.operator._busy = False  # Reset in case the monitor was not stopped gracefully, but forcefully stopped
        self.reset_fields()

    def kill_scan(self):
        """
        Forcefully terminates the scan thread
        """
        self.logger.debug('Killing operator threads')
        self.operator._stop = True
        self.scan_thread.terminate()
        self.reset_fields()

    def update_scan(self):
        if self.operator._new_scan_data:
            self.operator._new_scan_data = False
            self.curve1.setData(self.operator.scan_voltages, self.operator.measured_voltages)
        if self.scan_thread.isFinished():
            self.logger.debug('Scan thread is finished')
            self.scan_timer.stop()
            self.reset_fields()

    def closeEvent(self, event):
        """ Gets called when the window is closed. Could be used to do some cleanup before closing. """

        # # Use this bit to display an "Are you sure"-dialogbox
        # quit_msg = "Are you sure you want to exit labphew monitor?"
        # reply = QMessageBox.question(self, 'Message', quit_msg, QMessageBox.Yes, QMessageBox.No)
        # if reply == QMessageBox.No:
        #     event.ignore()
        #     return
        self.stop()  # stop scan
        self.scan_timer.stop()  # stop monitor timer, just to be nice
        # perhaps also disconnect devices
        event.accept()


if __name__ == "__main__":
    import labphew  # import this to use labphew style logging

    import sys
    from PyQt5.QtWidgets import QApplication
    from labphew.model.analog_discovery_2_model import Operator

    # To use with real device
    # from labphew.controller.digilent.waveforms import DfwController

    # To test with simulated device
    from labphew.controller.digilent.waveforms import SimulatedDfwController as DfwController

    from labphew.view.analog_discovery_2_view import MonitorWindow

    instrument = DfwController()
    opr = Operator(instrument)
    opr.load_config()


    app = QApplication(sys.argv)
    monitor_gui = MonitorWindow(opr)
    gui = ScanWindow(opr, monitor_gui)
    app.exit(app.exec_())