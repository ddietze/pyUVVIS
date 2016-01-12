"""
.. module: pyUVVIS
   :platform: Windows, Linux, OSX
.. moduleauthor:: Daniel Dietze <daniel.dietze@berkeley.edu>

A python based GUI for UV/VIS spectroscopy.

..
   This program is free software: you can redistribute it and/or modify
   it under the terms of the GNU General Public License as published by
   the Free Software Foundation, either version 3 of the License, or
   (at your option) any later version.

   This program is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.

   You should have received a copy of the GNU General Public License
   along with this program.  If not, see <http://www.gnu.org/licenses/>.

   Copyright 2016 Daniel Dietze <daniel.dietze@berkeley.edu>.
"""
# pyUVVIS - main application
import wx
import os
import time
import numpy as np
import wx.lib.plot as plot

# ---------------------------------------------------------------------------
# import camera driver
try:
    import drivers.uc480 as cam
    cam480 = cam.uc480()
    cam480.connect()    # see whether we can connect
    sensor_width, _ = cam480.get_sensor_size()
    cam480.close()
    uc480avail = True
except:
    sensor_width = 1024  # some default
    uc480avail = False

# import seabreeze module
try:
    import seabreeze
    seabreeze.use('pyseabreeze')
    import seabreeze.spectrometers as sb
    if len(sb.list_devices()) == 0:    # count connected OOs
        raise
    sensor_active_pixels = (1, -1)
    OOavail = True
except:
    OOavail = False
# ---------------------------------------------------------------------------


# main class
class pyUVVIS(wx.Frame):

    # initialize the app window
    def __init__(self, parent, title):
        super(pyUVVIS, self).__init__(parent, title=title, style=wx.DEFAULT_FRAME_STYLE | wx.MAXIMIZE)

        # camera handle
        self.cam = None        # camera handle
        self.activeCam = None  # type of camera = "uc480" or "OO"

        # default camera and acquisition parameters
        self.gain = 0          # gain
        self.gainmin = 0
        self.gainmax = 100
        self.gaininc = 1
        self.exp = 0           # exposure settings
        self.expmin = 0
        self.expmax = 100
        self.expinc = 1
        self.avg = 32          # averages settings
        self.avgmin = 1
        self.avgmax = 1000
        self.avginc = 1
        self.cAvg = 0

        # measurement mode of program
        self.recording = False
        self.modeUVVIS = False        # False = spectrum, True = UVVIS
        self.running = False
        self.ok_to_overwrite = False

        # current data
        self.data = None              # current dataset
        self.reference = None         # reference for UVVIS mode
        self.dark = None              # dark background spectrum

        # light level
        self.levelwasok = True
        self.satlevel = 1.0

        # get wavelength axis
        self.wlAxis = self.getWlAxis()

        # try to connect to camera
        self.connectCamera()
        self.updThread = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnUpdate, self.updThread)

        # some plotting stuff
        # list of colors for the plots
        self.colors = [wx.Colour(255, 0, 0), wx.Colour(255, 128, 0),
                       wx.Colour(255, 255, 0), wx.Colour(128, 255, 0),
                       wx.Colour(0, 200, 0), wx.Colour(0, 255, 128),
                       wx.Colour(0, 255, 255), wx.Colour(0, 128, 255),
                       wx.Colour(0, 0, 255)]
        self.lines = []               # list of lines to display

        # build the main GUI
        self.createUI()

        # display myself
        self.Show()

    # --------------------------------------------------------------------------
    # GUI creation stuff
    def createUI(self):
        self.createTB()
        self.createPlotWnd()
        self.Fit()

    def createTB(self):
        # create toolbar
        tb = self.CreateToolBar()
        tb.SetFont(wx.Font(-1, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, False))

        tbsave = tb.AddLabelTool(wx.ID_ANY, "Save Spectrum", wx.Bitmap('icons/10_7.png'), shortHelp="Save current spectrum.")
        tbload = tb.AddLabelTool(wx.ID_ANY, "Load Spectrum", wx.Bitmap('icons/11_5.png'), shortHelp="Load spectrum as overlay.")
        tbdelete = tb.AddLabelTool(wx.ID_ANY, "Remove Spectrum", wx.Bitmap('icons/11_4.png'), shortHelp="Remove spectrum.")
        tb.AddSeparator()
        tb.AddControl(wx.StaticText(tb, label="Averages", size=(90, -1)))
        tbavgdec = tb.AddLabelTool(wx.ID_ANY, "Reduce Averages", wx.Bitmap('icons/8_7.png'), shortHelp="Reduce numer of averages.")
        self.tbavg = wx.StaticText(tb, label="32", size=(44, -1), style=wx.ALIGN_CENTRE_HORIZONTAL | wx.ST_NO_AUTORESIZE)
        tb.AddControl(self.tbavg)
        tbavginc = tb.AddLabelTool(wx.ID_ANY, "Increase Averages", wx.Bitmap('icons/8_6.png'), shortHelp="Increase number of averages.")

        if self.camSupportsGain():
            tb.AddSeparator()
            tb.AddControl(wx.StaticText(tb, label="Gain", size=(50, -1)))
            tbgaindec = tb.AddLabelTool(wx.ID_ANY, "Reduce Gain", wx.Bitmap('icons/8_7.png'), shortHelp="Reduce gain.")
            self.tbgain = wx.StaticText(tb, label=str(self.gain), size=(44, -1), style=wx.ALIGN_CENTRE_HORIZONTAL | wx.ST_NO_AUTORESIZE)
            tb.AddControl(self.tbgain)
            tbgaininc = tb.AddLabelTool(wx.ID_ANY, "Increase Gain", wx.Bitmap('icons/8_6.png'), shortHelp="Increase gain.")

        if self.camSupportsExp():
            tb.AddSeparator()
            tb.AddControl(wx.StaticText(tb, label="Exposure Time", size=(150, -1)))
            tbexpdec = tb.AddLabelTool(wx.ID_ANY, "Reduce Exposure", wx.Bitmap('icons/8_7.png'), shortHelp="Reduce exposure time.")
            self.tbexp = wx.StaticText(tb, label=str(self.exp), size=(64, -1), style=wx.ALIGN_CENTRE_HORIZONTAL | wx.ST_NO_AUTORESIZE)
            tb.AddControl(self.tbexp)
            tbexpinc = tb.AddLabelTool(wx.ID_ANY, "Increase Exposure", wx.Bitmap('icons/8_6.png'), shortHelp="Increase exposure time.")

        tb.AddSeparator()
        self.tbstart1BMP = wx.Bitmap('icons/15_7.png')
        self.tbstart2BMP = wx.Bitmap('icons/15_6.png')
        self.tbstart = wx.BitmapButton(tb, wx.ID_ANY, self.tbstart1BMP, style=wx.NO_BORDER)
        tb.AddControl(self.tbstart)
        self.tbrecord = tb.AddLabelTool(wx.ID_ANY, "Record", wx.Bitmap('icons/4_6.png'), shortHelp="Start recording.")
        self.tbmode1BMP = wx.Bitmap('icons/3_6.png')
        self.tbmode2BMP = wx.Bitmap('icons/3_4.png')
        self.tbmode = wx.BitmapButton(tb, wx.ID_ANY, self.tbmode1BMP, style=wx.NO_BORDER)
        tb.AddControl(self.tbmode)
        tb.AddSeparator()
        self.tblightlevel1BMP = wx.Bitmap('icons/levelok.png')
        self.tblightlevel2BMP = wx.Bitmap('icons/levelbad.png')
        self.tblightlevel = wx.StaticBitmap(tb, wx.ID_ANY, self.tblightlevel1BMP)
        tb.AddControl(self.tblightlevel)
        tb.AddSeparator()
        tbauto = tb.AddLabelTool(wx.ID_ANY, "Auto Gain / Exposure", wx.Bitmap('icons/1_11.png'), shortHelp="Set auto gain / exposure.")
        tbdark = tb.AddLabelTool(wx.ID_ANY, "Dark Signal Subtraction", wx.Bitmap('icons/1_9.png'), shortHelp="Subtract dark pattern.")
        tbquit = tb.AddLabelTool(wx.ID_ANY, "Quit", wx.Bitmap('icons/1_8.png'), shortHelp="Close pyUVVIS.")

        # finalize TB
        tb.Realize()
        self.tb = tb

        # add event bindings
        self.Bind(wx.EVT_TOOL, self.OnTBSave, tbsave)
        self.Bind(wx.EVT_TOOL, self.OnTBLoad, tbload)
        self.Bind(wx.EVT_TOOL, self.OnTBDelete, tbdelete)

        self.Bind(wx.EVT_TOOL, self.OnTBAvgInc, tbavginc)
        self.Bind(wx.EVT_TOOL, self.OnTBAvgDec, tbavgdec)
        self.Bind(wx.EVT_TOOL_RCLICKED, self.OnRTBAvgInc, tbavginc)
        self.Bind(wx.EVT_TOOL_RCLICKED, self.OnRTBAvgDec, tbavgdec)

        if self.camSupportsGain():
            self.Bind(wx.EVT_TOOL, self.OnTBGainInc, tbgaininc)
            self.Bind(wx.EVT_TOOL, self.OnTBGainDec, tbgaindec)
            self.Bind(wx.EVT_TOOL_RCLICKED, self.OnRTBGainInc, tbgaininc)
            self.Bind(wx.EVT_TOOL_RCLICKED, self.OnRTBGainDec, tbgaindec)

        if self.camSupportsExp():
            self.Bind(wx.EVT_TOOL, self.OnTBExpInc, tbexpinc)
            self.Bind(wx.EVT_TOOL, self.OnTBExpDec, tbexpdec)
            self.Bind(wx.EVT_TOOL_RCLICKED, self.OnRTBExpInc, tbexpinc)
            self.Bind(wx.EVT_TOOL_RCLICKED, self.OnRTBExpDec, tbexpdec)

        self.Bind(wx.EVT_TOOL, self.OnTBAuto, tbauto)
        self.Bind(wx.EVT_BUTTON, self.OnTBStart, self.tbstart)
        self.Bind(wx.EVT_TOOL, self.OnTBRecord, self.tbrecord)
        self.Bind(wx.EVT_BUTTON, self.OnTBMode, self.tbmode)
        self.Bind(wx.EVT_TOOL, self.OnQuit, tbquit)
        self.Bind(wx.EVT_TOOL, self.OnTBDark, tbdark)

        # bind the app exit event to an event handler so we can check whether there are some experiments running and shut down all the modules properly
        self.Bind(wx.EVT_CLOSE, self.OnQuit)

    def createPlotWnd(self):
        self.plotWnd = plot.PlotCanvas(self)
        self.plotWnd.SetEnableZoom(False)
        self.plotWnd.SetEnableGrid(True)
        self.plotWnd.SetEnableTitle(False)
        self.plotWnd.SetXSpec('min')
        self.plotWnd.SetFontSizeAxis(18)
        self.addLine([0, 1], [0, 0])

    # --------------------------------------------------------------------------
    # camera interaction
    def connectCamera(self):
        if uc480avail and OOavail:
            dlg = wx.SingleChoiceDialog(None, 'Please select input device..', 'Camera setup', ['uc480', 'OceanOptics'], style=wx.OK)
            dlg.ShowModal()
            if dlg.GetSelection() == 0:
                self.connectUC480()
            else:
                self.connectOO()
            dlg.Destroy()
        elif uc480avail:
            self.connectUC480()
        elif OOavail:
            self.connectOO()
        else:
            wx.MessageBox('No input device detected! Please check connections..', 'Camera setup', style=wx.OK | wx.ICON_EXCLAMATION)

    def connectUC480(self):
        self.cam = cam.uc480()
        self.cam.connect()

        self.gain = self.cam.get_gain()
        self.gainmin, self.gainmax, self.gaininc = self.cam.get_gain_limits()
        self.exp = self.cam.get_exposure()
        self.expmin, self.expmax, self.expinc = self.cam.get_exposure_limits()

        self.activeCam = 'uc480'

    def connectOO(self):
        devices = sb.list_devices()
        self.cam = sb.Spectrometer(devices[0])

        self.exp = self.cam.minimum_integration_time_micros / 1000 + 1.0
        self.cam.integration_time_micros(self.exp * 1000)
        self.expmin, self.expmax, self.expinc = self.exp, 65000, 2
        self.satlevel = self.cam._dev.interface._MAX_PIXEL_VALUE

        self.wlAxis = self.cam.wavelengths()[sensor_active_pixels[0]:sensor_active_pixels[1]]
        self.activeCam = 'OO'

    def camClose(self):
        if self.activeCam == 'uc480':
            self.cam.disconnect()
        elif self.activeCam == 'OO':
            self.cam.close()

    # read a frame from the active input device and check for overexposure
    def readCamera(self):
        if self.activeCam == 'uc480':
            data, _, mint = self.cam.acquireBinned(1)
            data = np.flipud(data)
            ovexp = mint >= 255

        elif self.activeCam == 'OO':
            data = self.cam.intensities()[sensor_active_pixels[0]:sensor_active_pixels[1]]
            ovexp = np.amax(data) >= self.satlevel

        else:
            data = (np.random.rand(64) + 1) * 10
            ovexp = False

        return data, ovexp

    def camSupportsGain(self):
        if self.activeCam == 'uc480':
            return True
        return False

    def camSupportsExp(self):
        if self.activeCam in ['uc480', 'OO']:
            return True
        return False

    def camSetGain(self, g):
        if self.activeCam == 'uc480':
            self.cam.set_gain(g)

    def camSetExp(self, e):
        if self.activeCam == 'uc480':
            self.cam.set_exposure(e)
        elif self.activeCam == 'OO':
            self.cam.integration_time_micros(e * 1000.0)

    def getWlAxis(self):
        # get wavelength axis
        # if uc480 is used and calibration file exists
        wlAxis = None
        if uc480avail:
            if os.path.exists("calibration.dat"):
                px, wl = np.loadtxt("calibration.dat", unpack=True)
                n = float(len(px))
                b = (n * np.sum(px * wl) - np.sum(px) * np.sum(wl)) / (n * np.sum(px**2) - np.sum(px)**2)
                a = np.mean(wl) - b * np.mean(px)
                wlAxis = a + np.arange(sensor_width) * b
        return wlAxis

    # --------------------------------------------------------------------------
    # plotting stuff

    # add line to plot window
    def addLine(self, x, y, id=None):
        # convert arrays to array of point tuples
        data = np.swapaxes(np.vstack((x, y)), 0, 1)

        # get plot colors
        if id is not None:
            clr = self.colors[id % len(self.colors)]
        else:
            clr = self.colors[len(self.lines) % len(self.colors)]

        # generate new line object
        line = plot.PolyLine(data, width=2, colour=clr)

        # add to line stack
        if id is None or len(self.lines) == 0:
            self.lines.append(line)
        else:
            self.lines[id] = line

        # replot
        self.refreshPlot()

    # refresh the plot window
    def refreshPlot(self):
        if self.modeUVVIS:
            gc = plot.PlotGraphics(self.lines, '', 'Wavelength', 'OD')
        else:
            gc = plot.PlotGraphics(self.lines, '', 'Wavelength', 'Counts')

        self.plotWnd.Draw(gc)

    # -------------------------------------------------------------------------------------------------------------------
    # events

    def OnQuit(self, event):
        self.updThread.Stop()
        time.sleep(0.5)
        self.camClose()
        self.Destroy()

    def OnTBSave(self, event):
        if self.data is None:
            wx.MessageBox('Please record a spectrum first!', 'Save Spectrum', wx.OK | wx.ICON_INFORMATION)
            return
        if self.running:
            rng = True
            self.OnTBStart()
        else:
            rng = False

        dlg = wx.FileDialog(None, "Save Spectrum", os.getcwd(), "", "*.*", wx.SAVE)
        if dlg.ShowModal() == wx.ID_OK:
            filename = dlg.GetPath()

            # set new working directory
            directory = os.path.split(filename)
            if not os.path.isdir(filename):
                os.chdir(directory[0])

            # save file
            np.savetxt(filename, np.transpose(np.array([self.wlAxis, self.data])))

            # add to plot window
            self.addLine(self.wlAxis, self.data)
        dlg.Destroy()

        if rng:
            self.OnTBStart()

    def OnTBLoad(self, event):
        if self.running:
            rng = True
            self.OnTBStart()
        else:
            rng = False

        dlg = wx.FileDialog(None, "Open Spectrum", os.getcwd(), "", "*.*", wx.OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            filename = dlg.GetPath()
            # set new working directory
            directory = os.path.split(filename)
            if not os.path.isdir(filename):
                os.chdir(directory[0])
            # save file
            tmpx, tmpy = np.loadtxt(filename, unpack=True)
            # add to plot window
            self.addLine(tmpx, tmpy)

        dlg.Destroy()

        if rng:
            self.OnTBStart()

    def OnTBDelete(self, event):
        # remove the last plot in the list
        if len(self.lines) > 1:
            self.lines.pop()
        self.refreshPlot()

    def OnTBAvgInc(self, event=None):
        if self.avg + self.avginc <= self.avgmax:
            self.avg = self.avg + self.avginc
            self.tbavg.SetLabel(str(self.avg))

    def OnTBAvgDec(self, event=None):
        if self.avg - self.avginc >= self.avgmin:
            self.avg = self.avg - self.avginc
            self.tbavg.SetLabel(str(self.avg))

    def OnTBGainInc(self, event=None):
        self.gain = min(self.gainmax, self.gain + self.gaininc)
        self.tbgain.SetLabel(str(self.gain))
        self.camSetGain(self.gain)

    def OnTBGainDec(self, event=None):
        self.gain = max(self.gainmin, self.gain - self.gaininc)
        self.tbgain.SetLabel(str(self.gain))
        self.camSetGain(self.gain)

    def OnTBExpInc(self, event=None):
        self.exp = min(self.expmax, self.exp + self.expinc)
        self.tbexp.SetLabel(str(self.exp))
        self.camSetExp(self.exp)

    def OnTBExpDec(self, event=None):
        self.exp = max(self.expmin, self.exp - self.expinc)
        self.tbexp.SetLabel(str(self.exp))
        self.camSetExp(self.exp)

    def OnRTBAvgInc(self, event=None):
        self.avg = min(self.avgmax, self.avg + 10 * self.avginc)
        self.tbavg.SetLabel(str(self.avg))

    def OnRTBAvgDec(self, event=None):
        self.avg = max(self.avgmin, self.avg - 10 * self.avginc)
        self.tbavg.SetLabel(str(self.avg))

    def OnRTBGainInc(self, event=None):
        self.gain = min(self.gainmax, self.gain + 10 * self.gaininc)
        self.tbgain.SetLabel(str(self.gain))
        self.camSetGain(self.gain)

    def OnRTBGainDec(self, event=None):
        self.gain = max(self.gainmin, self.gain - 10 * self.gaininc)
        self.tbgain.SetLabel(str(self.gain))
        self.camSetGain(self.gain)

    def OnRTBExpInc(self, event=None):
        self.exp = min(self.expmax, self.exp + 10 * self.expinc)
        self.tbexp.SetLabel("%.2f" % self.exp)
        self.camSetExp(self.exp)

    def OnRTBExpDec(self, event=None):
        self.exp = max(self.expmin, self.exp - 10 * self.expinc)
        self.tbexp.SetLabel("%.2f" % self.exp)
        self.camSetExp(self.exp)

    def OnTBStart(self, event=None):
        if self.running:
            self.tbstart.SetBitmapLabel(self.tbstart1BMP)
            self.running = False
            self.recording = False
            self.updThread.Stop()
        else:
            self.tbstart.SetBitmapLabel(self.tbstart2BMP)
            self.running = True
            self.ok_to_overwrite = True
            self.cAvg = 0
            self.data = None
            self.OnUpdate()

    def OnTBRecord(self, event=None):
        if self.running:
            self.OnTBStart()
        self.recording = True
        self.OnTBStart()

    def OnTBMode(self, event):
        if self.modeUVVIS:
            self.tbmode.SetBitmapLabel(self.tbmode1BMP)
            self.reference = None
            self.modeUVVIS = False
        else:
            self.tbmode.SetBitmapLabel(self.tbmode2BMP)
            self.reference = self.data
            self.modeUVVIS = True

    # auto exposure / gain settings
    def OnTBAuto(self, event):
        if self.cam is None:
            return

        if self.running:
            wx.MessageBox('Please pause acquisition first!', 'Acquisition in progress!', wx.OK | wx.ICON_INFORMATION)
            return

        msg = "Setting automatic exposure time / gain.. please wait.."
        busyDlg = wx.BusyInfo(msg)
        self.tb.Enable(False)
        wx.GetApp().Yield()

        _, ovexp = self.readCamera()
        while not ovexp:
            if self.camSupportsExp() and self.exp < self.expmax:
                self.OnRTBExpInc()
            elif self.camSupportsGain() and self.gain < self.gainmax:
                self.OnRTBGainInc()
            else:
                break
            _, ovexp = self.readCamera()
            wx.GetApp().Yield()
        while ovexp:
            if self.camSupportsGain() and self.gain > self.gainmin:
                self.OnRTBGainDec()
            elif self.camSupportsExp() and self.exp > self.expmin:
                self.OnRTBExpDec()
            else:
                break
            _, ovexp = self.readCamera()
            wx.GetApp().Yield()

        busyDlg = None
        self.tb.Enable(True)

    def OnTBDark(self, event):
        if self.dark is not None:
            self.dark = None
        elif self.data is None:
            wx.MessageBox('Please record a spectrum first!', 'Background Correction', wx.OK | wx.ICON_INFORMATION)
        else:
            self.dark = self.data.copy()

    # --------------------------------------------------------------------------
    # this is the main measurement routine where all the magic happens
    def OnUpdate(self, event=None):
        # read data from camera
        # if self.cam is None:
        #   return
        data, ovexp = self.readCamera()

        # light level warning
        if self.levelwasok and ovexp:
            self.levelwasok = False
            self.tblightlevel.SetBitmap(self.tblightlevel2BMP)
        elif not self.levelwasok and not ovexp:
            self.levelwasok = True
            self.tblightlevel.SetBitmap(self.tblightlevel1BMP)

        # dark level subtraction
        if self.dark is not None:
            data = data - self.dark

        # force minimum pixel value to be 1 to prevent NaNs
        data = np.maximum(np.ones(len(data)), data)

        # UVVIS or spectrum
        if self.modeUVVIS and self.reference is not None:
            data = np.nan_to_num(-np.log10(data / self.reference))

        # add to running average if recording
        if self.recording:
            if self.data is not None:
                self.data = (float(self.cAvg) * self.data + data) / float(self.cAvg + 1)
                self.cAvg = self.cAvg + 1
            else:
                self.data = data.copy()
                self.cAvg = 1

            if self.cAvg >= self.avg:
                self.ok_to_overwrite = False
                self.OnTBStart()            # recording stops
        elif self.ok_to_overwrite:
            self.data = data.copy()

        # force some kind of x-axis
        if self.wlAxis is None:
            self.wlAxis = np.arange(len(self.data))

        # overwrite main line in plot
        self.addLine(self.wlAxis, self.data, id=0)

        # restart timer
        if self.running:
            wx.GetApp().Yield()    # process all GUI events to keep the program responsive
            self.updThread.Start(200, wx.TIMER_ONE_SHOT)

if __name__ == '__main__':
    app = wx.App()
    pyUVVIS(None, title="pyUVVIS - (c) D. Dietze, 2015, 2016")
    app.MainLoop()
