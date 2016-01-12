pyUVVIS - A python GUI for UV/VIS spectroscopy
==============================================

*pyUVVIS* is my attempt at providing a lightweight, simple to use GUI for UV/VIS spectroscopy.
The program operates in two major modes, as a simple spectrometer and as a UV/VIS spectrometer.
While the first is used to measure spectra of light sources, adjust illumination settings and record reference and dark spectra,
the latter is used to measure the absorption or optical density of test samples.

Supported features are:
* Save / load spectra.
* Live view / recording.
* Averaging.
* Exposure time / gain settings.
* Automatic optimization of exposure time / gain.
* Dark / background spectra subtraction.
* Direct vs. UV/VIS mode.

Currently supported input devices are:
* Thorlabs' uc480 compatible cameras.
* OceanOptics' spectrometers through `python-seabreeze`.

Installation
============

There is no installation routine / setup file yet. In order to use pyUVVIS, simply download and unpack the zip archive and execute the main file *pyUVVIS.py* using python. I have tested/developed this program using Python 2.7, mainly due to the availability of wxPython at that time. However, it should also run under Python 3 (maybe with some fixes to the print-syntax).

Prerequisites:
* wxPython
* Numpy

For a uc480-based spectrometer, also install
* Thorlabs' *uc480* library (<http://www.thorlabs.com>).

For OceanOptics-based spectrometer, install
* python-seabreeze (<https://github.com/ap--/python-seabreeze>)

Documentation
=============

A full documentation of the program can be found on my GitHub Pages: <http://ddietze.github.io/pyUVVIS>.

Licence
=======

This program is free software: you can redistribute and/or modify
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
