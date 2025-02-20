# -*- coding: utf-8 -*-
# Part of the PsychoPy library
# Copyright (C) 2012-2020 iSolver Software Solutions (C) 2021 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).


from psychopy import visual
import gevent
from psychopy.iohub.util import convertCamelToSnake
from psychopy.iohub.devices import DeviceEvent, Computer
from psychopy.iohub.constants import EventConstants as EC
from psychopy.iohub.devices.keyboard import KeyboardInputEvent
from psychopy.iohub.errors import print2err

currentTime = Computer.getTime


class GazepointPsychopyCalibrationGraphics(object):
    IOHUB_HEARTBEAT_INTERVAL = 0.050
    CALIBRATION_POINT_LIST = [(0.5, 0.5), (0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)]

    _keyboard_key_index = KeyboardInputEvent.CLASS_ATTRIBUTE_NAMES.index('key')

    def __init__(self, eyetrackerInterface, calibration_args):
        self._eyetracker = eyetrackerInterface
        self.screenSize = eyetrackerInterface._display_device.getPixelResolution()
        self.width = self.screenSize[0]
        self.height = self.screenSize[1]
        self._ioKeyboard = None
        self._msg_queue = []
        self._lastCalibrationOK = False
        display = self._eyetracker._display_device

        self._device_config = self._eyetracker.getConfiguration()
        self._calibration_args = self._device_config.get('calibration')

        unit_type = self.getCalibSetting('unit_type')
        if unit_type is None:
            unit_type = display.getCoordinateType()
            self._calibration_args['unit_type'] = unit_type
        color_type = self.getCalibSetting('color_type')
        if color_type is None:
            color_type = display.getColorSpace()
            self._calibration_args['color_type'] = color_type

        calibration_methods = dict(THREE_POINTS=3,
                                   FIVE_POINTS=5,
                                   NINE_POINTS=9,
                                   THIRTEEN_POINTS=13)

        cal_type = self.getCalibSetting('type')

        if cal_type in calibration_methods:
            num_points = calibration_methods[cal_type]

            if num_points == 3:
                GazepointPsychopyCalibrationGraphics.CALIBRATION_POINT_LIST = [(0.5, 0.1),
                                                                               (0.1, 0.9),
                                                                               (0.9, 0.9)]
            elif num_points == 5:
                GazepointPsychopyCalibrationGraphics.CALIBRATION_POINT_LIST = [(0.5, 0.5),
                                                                               (0.1, 0.1),
                                                                               (0.9, 0.1),
                                                                               (0.9, 0.9),
                                                                               (0.1, 0.9)]
            elif num_points == 9:
                GazepointPsychopyCalibrationGraphics.CALIBRATION_POINT_LIST = [(0.5, 0.5),
                                                                               (0.1, 0.5),
                                                                               (0.9, 0.5),
                                                                               (0.1, 0.1),
                                                                               (0.5, 0.1),
                                                                               (0.9, 0.1),
                                                                               (0.9, 0.9),
                                                                               (0.5, 0.9),
                                                                               (0.1, 0.9)]
            elif num_points == 13:
                GazepointPsychopyCalibrationGraphics.CALIBRATION_POINT_LIST = [(0.5, 0.5),
                                                                               (0.1, 0.5),
                                                                               (0.9, 0.5),
                                                                               (0.1, 0.1),
                                                                               (0.5, 0.1),
                                                                               (0.9, 0.1),
                                                                               (0.9, 0.9),
                                                                               (0.5, 0.9),
                                                                               (0.1, 0.9),
                                                                               (0.25, 0.25),
                                                                               (0.25, 0.75),
                                                                               (0.75, 0.75),
                                                                               (0.75, 0.25)
                                                                               ]

        if display.getCoordinateType() != unit_type:
            raise RuntimeWarning("ioHub GP3 Warning: display.getCoordinateType() != "
                                 "self.getCalibSetting('unit_type'): {} {}".format(display.getCoordinateType(),
                                                                                   unit_type))
        self.window = visual.Window(
            self.screenSize,
            monitor=display.getPsychopyMonitorName(),
            units=unit_type,
            fullscr=True,
            allowGUI=False,
            screen=display.getIndex(),
            color=self.getCalibSetting(['screen_background_color']),
            colorSpace=color_type)
        self.window.flip(clearBuffer=True)

        self._createStim()
        self._registerEventMonitors()
        self._lastMsgPumpTime = currentTime()

        self.clearAllEventBuffers()

    def getCalibSetting(self, setting):
        if isinstance(setting, str):
            setting = [setting, ]
        calibration_args = self._calibration_args
        if setting:
            for s in setting[:-1]:
                calibration_args = calibration_args.get(s)
            return calibration_args.get(setting[-1])

    def clearAllEventBuffers(self):
        self._eyetracker._iohub_server.eventBuffer.clear()
        for d in self._eyetracker._iohub_server.devices:
            d.clearEvents()

    def _registerEventMonitors(self):
        kbDevice = None
        if self._eyetracker._iohub_server:
            for dev in self._eyetracker._iohub_server.devices:
                if dev.__class__.__name__ == 'Keyboard':
                    kbDevice = dev

        if kbDevice:
            eventIDs = []
            for event_class_name in kbDevice.__class__.EVENT_CLASS_NAMES:
                eventIDs.append(getattr(EC, convertCamelToSnake(event_class_name[:-5], False)))

            self._ioKeyboard = kbDevice
            self._ioKeyboard._addEventListener(self, eventIDs)
        else:
            print2err(
                'Warning: GazePoint Cal GFX could not connect to Keyboard device for events.')

    def _unregisterEventMonitors(self):
        if self._ioKeyboard:
            self._ioKeyboard._removeEventListener(self)

    def _handleEvent(self, event):
        event_type_index = DeviceEvent.EVENT_TYPE_ID_INDEX
        if event[event_type_index] == EC.KEYBOARD_PRESS:
            ek = event[self._keyboard_key_index]
            if isinstance(ek, bytes):
                ek = ek.decode('utf-8')
            if ek == ' ':
                self._msg_queue.append('SPACE_KEY_ACTION')
                self.clearAllEventBuffers()
            elif ek == 'escape':
                self._msg_queue.append('QUIT')
                self.clearAllEventBuffers()

    def MsgPump(self):
        # keep the psychopy window happy ;)
        if currentTime() - self._lastMsgPumpTime > self.IOHUB_HEARTBEAT_INTERVAL:
            # try to keep ioHub from being blocked. ;(
            if self._eyetracker._iohub_server:
                for dm in self._eyetracker._iohub_server.deviceMonitors:
                    dm.device._poll()
                self._eyetracker._iohub_server.processDeviceEvents()
            self._lastMsgPumpTime = currentTime()

    def getNextMsg(self):
        if len(self._msg_queue) > 0:
            msg = self._msg_queue[0]
            self._msg_queue = self._msg_queue[1:]
            return msg

    def _createStim(self):
        """
            outer_diameter: 35
            outer_stroke_width: 5
            outer_fill_color: [255,255,255]
            outer_line_color: [255,255,255]
            inner_diameter: 5
            inner_stroke_width: 0
            inner_color: [0,0,0]
            inner_fill_color: [0,0,0]
            inner_line_color: [0,0,0]
            calibration_prefs=self._eyetracker.getConfiguration()['calibration']['target_attributes']
        """
        color_type = self.getCalibSetting('color_type')
        unit_type = self.getCalibSetting('unit_type')

        lwidth = self.getCalibSetting(['target_attributes', 'outer_stroke_width'])
        radius = self.getCalibSetting(['target_attributes', 'outer_diameter']) / 2.0
        fcolor = self.getCalibSetting(['target_attributes', 'outer_fill_color'])
        lcolor = self.getCalibSetting(['target_attributes', 'outer_line_color'])
        self.calibrationPointOUTER = visual.Circle(self.window, pos=(0, 0), name='CP_OUTER',
                                                   radius=radius, lineWidth=lwidth,
                                                   fillColor=fcolor, lineColor=lcolor,
                                                   opacity=1.0, interpolate=False,
                                                   edges=64, units=unit_type, colorSpace=color_type)

        lwidth = self.getCalibSetting(['target_attributes', 'inner_stroke_width'])
        radius = self.getCalibSetting(['target_attributes', 'inner_diameter']) / 2.0
        fcolor = self.getCalibSetting(['target_attributes', 'inner_fill_color'])
        lcolor = self.getCalibSetting(['target_attributes', 'inner_line_color'])
        self.calibrationPointINNER = visual.Circle(self.window, pos=(0, 0), name='CP_INNER',
                                                   radius=radius, lineWidth=lwidth,
                                                   fillColor=fcolor, lineColor=lcolor,
                                                   opacity=1.0, interpolate=False,
                                                   edges=64, units=unit_type, colorSpace=color_type)

        instuction_text = 'Press SPACE to Start Calibration; ESCAPE to Exit.'
        self.textLineStim = visual.TextStim(self.window, text=instuction_text,
                                            pos=(0, 0), height=36,
                                            color=(0, 0, 0), colorSpace='rgb255',
                                            units='pix', wrapWidth=self.width * 0.9)

    def runCalibration(self):
        """Run calibration sequence
        """

        instuction_text = 'Press SPACE to Start Calibration.'
        self.showSystemSetupMessageScreen(instuction_text)

        target_delay = self.getCalibSetting('target_delay')
        target_duration = self.getCalibSetting('target_duration')

        cal_target_list = self.CALIBRATION_POINT_LIST
        randomize_points = self.getCalibSetting('randomize')
        if randomize_points is True:
            # Randomize all but first target position.
            cal_target_list = self.CALIBRATION_POINT_LIST[1:]
            import random
            random.seed(None)
            random.shuffle(cal_target_list)
            cal_target_list.insert(0, self.CALIBRATION_POINT_LIST[0])

        self._eyetracker._gp3set('CALIBRATE_SHOW', STATE=0)
        self._eyetracker._gp3set('CALIBRATE_START', STATE=0)

        self._eyetracker._gp3set('CALIBRATE_CLEAR')

        self._eyetracker._gp3set('SCREEN_SIZE', X=0, Y=0, WIDTH=self.width, HEIGHT=self.height)
        #print2err("Set GP3 SCREEN_SIZE: ", self._eyetracker._waitForAck('SCREEN_SIZE'))

        # Inform GazePoint of target list to be used
        for p in cal_target_list:
            x, y = p
            self._eyetracker._gp3set('CALIBRATE_ADDPOINT', X=x, Y=y)
            self._eyetracker._waitForAck('CALIBRATE_ADDPOINT')

        left, top, right, bottom = self._eyetracker._display_device.getCoordBounds()
        w, h = right - left, top - bottom

        self.clearCalibrationWindow()

        # Start drawing calibration points
        self._eyetracker._gp3set('CALIBRATE_SHOW', STATE=0)
        self._eyetracker._gp3set('CALIBRATE_START', STATE=1)

        # seems like gps expects animation at state of every target pos.
        i = 0
        for pt in cal_target_list:
            # Convert GazePoint normalized positions to psychopy window unit positions
            # by using iohub display/window getCoordBounds.
            x, y = left + w * pt[0], bottom + h * (1.0 - pt[1])

            self.clearAllEventBuffers()

            # Target animate / delay
            animate_enable = self.getCalibSetting(['target_attributes', 'animate', 'enable'])
            animate_expansion_ratio = self.getCalibSetting(['target_attributes', 'animate', 'expansion_ratio'])
            animate_contract_only = self.getCalibSetting(['target_attributes', 'animate', 'contract_only'])

            start_time = currentTime()
            while currentTime()-start_time <= target_delay:
                if animate_enable and i > 0:
                        t = (currentTime() - start_time) / target_delay
                        v1 = cal_target_list[i-1]
                        v2 = pt
                        t = 60.0 * ((1.0 / 10.0) * t ** 5 - (1.0 / 4.0) * t ** 4 + (1.0 / 6.0) * t ** 3)
                        mx, my = ((1.0 - t) * v1[0] + t * v2[0], (1.0 - t) * v1[1] + t * v2[1])
                        moveTo = left + w * mx, bottom + h * (1.0 - my)
                        self.drawCalibrationTarget(moveTo, reset=False)
                else:
                    self.drawCalibrationTarget((x, y), False)

                self.getNextMsg()
                self.MsgPump()

            self.drawCalibrationTarget((x, y))
            start_time = currentTime()

            outer_diameter = self.getCalibSetting(['target_attributes', 'outer_diameter'])
            inner_diameter = self.getCalibSetting(['target_attributes', 'inner_diameter'])
            while currentTime()-start_time <= target_duration:
                elapsed_time = currentTime()-start_time
                d = t = None
                if animate_contract_only:
                    # Change target size from outer diameter to inner diameter over target_duration seconds.
                    t = elapsed_time / target_duration
                    d = outer_diameter - t * (outer_diameter - inner_diameter)
                    self.calibrationPointOUTER.radius = d / 2
                    self.calibrationPointOUTER.draw()
                    self.calibrationPointINNER.draw()
                    self.window.flip(clearBuffer=True)
                elif animate_expansion_ratio not in [1, 1.0]:
                    if elapsed_time <= target_duration/2:
                        # In expand phase
                        t = elapsed_time / (target_duration/2)
                        d = outer_diameter + t * (outer_diameter*animate_expansion_ratio - outer_diameter)
                    else:
                        # In contract phase
                        t = (elapsed_time-target_duration/2) / (target_duration/2)
                        d = outer_diameter*animate_expansion_ratio - t * (outer_diameter*animate_expansion_ratio - inner_diameter)
                if d:
                    self.calibrationPointOUTER.radius = d / 2
                    self.calibrationPointOUTER.draw()
                    self.calibrationPointINNER.draw()
                    self.window.flip(clearBuffer=True)

                #print2err(inner_diameter, " ", outer_diameter, " ", t, " ", d)

                self.getNextMsg()
                self.MsgPump()
                gevent.sleep(0.001)

            self.clearCalibrationWindow()
            self.clearAllEventBuffers()
            i += 1
        instuction_text = "Calibration Complete. Press 'SPACE' key to continue."
        self.showSystemSetupMessageScreen(instuction_text)


    def clearCalibrationWindow(self):
        self.window.flip(clearBuffer=True)

    def showSystemSetupMessageScreen(self, text_msg='Press SPACE to Start Calibration; ESCAPE to Exit.'):

        self.clearAllEventBuffers()

        while True:
            self.textLineStim.setText(text_msg)
            self.textLineStim.draw()
            self.window.flip()

            msg = self.getNextMsg()
            if msg == 'SPACE_KEY_ACTION':
                self.clearAllEventBuffers()
                return True
            elif msg == 'QUIT':
                self.clearAllEventBuffers()
                return False
            self.MsgPump()
            gevent.sleep(0.001)

    def drawDefaultTarget(self):
        self.calibrationPointOUTER.radius = self.getCalibSetting(['target_attributes', 'outer_diameter']) / 2.0
        self.calibrationPointOUTER.setLineColor(self.getCalibSetting(['target_attributes', 'outer_line_color']))
        self.calibrationPointOUTER.setFillColor(self.getCalibSetting(['target_attributes', 'outer_fill_color']))
        self.calibrationPointOUTER.lineWidth = int(self.getCalibSetting(['target_attributes', 'outer_stroke_width']))
        self.calibrationPointINNER.radius = self.getCalibSetting(['target_attributes', 'inner_diameter']) / 2.0
        self.calibrationPointINNER.setLineColor(self.getCalibSetting(['target_attributes', 'inner_line_color']))
        self.calibrationPointINNER.setFillColor(self.getCalibSetting(['target_attributes', 'inner_fill_color']))
        self.calibrationPointINNER.lineWidth = int(self.getCalibSetting(['target_attributes', 'inner_stroke_width']))

        self.calibrationPointOUTER.draw()
        self.calibrationPointINNER.draw()
        return self.window.flip(clearBuffer=True)

    def drawCalibrationTarget(self, tp, reset=True):
        self.calibrationPointOUTER.setPos(tp)
        self.calibrationPointINNER.setPos(tp)
        if reset:
            return self.drawDefaultTarget()
        else:
            self.calibrationPointOUTER.draw()
            self.calibrationPointINNER.draw()
            return self.window.flip(clearBuffer=True)