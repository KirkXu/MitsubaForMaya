MitsubaForMaya
=

A Maya plugin for the Mitsuba rendering engine.

Installation and Usage
-

- Load from anywhere using Python command
	- cmds.loadPlugin( "/path/where/you/downloaded/MitsubaForMaya.py" )

- Unload as appropriate
	- cmds.unloadPlugin( "MitsubaForMaya.py" )

- ****VERY IMPORTANT**** 
- Render Settings' Mitsuba tab has to have been displayed before a render can start

- ****VERY IMPORTANT**** 
- The first field in the Render Settings Mituba tab is the path to the 'mitsuba' binary. You must set this to be able to render.
	- OSX: ex. /path/where/you/downloaded/Mitsuba.app/Contents/MacOS/mitsuba
	- Linux: ex. /usr/local/mitsuba/mitsuba
	- Windows: ex. C:/path/where/you/downloaded/Mitsuba 0.5.0 64bit/Mitsuba 0.5.0/mitsuba.exe

- Renders EXRs

Testing
-

This plugin was tested with Maya 2016 on OSX Yosemite, Windows 7 and CentOS 7 Linux.

Notes
-

The default lighting in Mitsuba is a sunsky, so if you do not use any lighting yourself, that is what this tool will default to as well.  The other lights available are directional, environment maps and object area lights.  Mitsuba supports a variety of other lights, but they have not been ported.  To use a directional light, simply create a normal, Maya directional light and position it as normal.  For an environment map or custom sunsky, see the appropriate nodes in the Hypershader, under Maya/Lights.  Note that you can specify either an environment map or sunsky node (ie you can not have one of each). To use an area light, assign the MitsubaObjectAreaLightShader shader as the Material for the object that you would like to act as an area light.

For a variety of Mitsuba materials, check the Hypershade under Maya/Surface.

Render settings have been set to balance render time vs. quality.  More information can be found here.  The main thing that controls render quality is the sampleCount in the Image Sampler drop down.

References
-

- [Mitsuba](http://www.mitsuba-renderer.org/)

- [Mitsuba Downloads](http://www.mitsuba-renderer.org/download.html)

- [Mitsuba Blog](http://www.mitsuba-renderer.org/devblog/)

- [Mitsuba Respository](https://www.mitsuba-renderer.org/repos/)

- [OpenMaya renderer integrations](https://github.com/haggi/OpenMaya)

- [Irawan Cloth Data Sets](http://www.mitsuba-renderer.org/scenes/irawan.zip)

