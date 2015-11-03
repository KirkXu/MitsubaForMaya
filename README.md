MitsubaForMaya
=

A Maya plugin for the Mitsuba rendering engine.

Usage
-

- Load from anywhere using Python command
	- cmds.loadPlugin( "/path/where/you/downloaded/MitsubaForMaya.py" )

- Unload as appropriate
	- cmds.unloadPlugin( "MitsubaForMaya.py" )

- ****VERY IMPORTANT**** 
- The first field in the Render Settings Mituba tab is the path to the 'mitsuba' binary. You must set this to be able to render. The setting can be specified using the MITSUBA_PATH environment variable, as described below, or manually from the Render Settings UI. The path will be retained in a file's Render Settings, so the value only has to be specified the first time you use a scene.

	- OSX: ex. /path/where/you/downloaded/Mitsuba.app/Contents/MacOS/mitsuba

	- Linux: ex. /usr/local/mitsuba/mitsuba

	- Windows: ex. C:/path/where/you/downloaded/Mitsuba 0.5.0 64bit/Mitsuba 0.5.0/mitsuba.exe

- Currently, only Mitsuba Lights and Materials are supported. These can be found and assigned using the Hypershade

Installation and Application Environment
- 
The path to the Mitsuba binary has to be specified, either in the Render Settings manually or by using the Maya.env or other environment setup file.

- The environment variable to set is MITSUBA_PATH 

	- Windows: MITSUBA_PATH = C:\path\to\Mitsuba 0.5.0\mitsuba.exe

	- Mac: MITSUBA_PATH = /path/to/Mitsuba.app/Contents/MacOS/mitsuba

	- Linux: MITSUBA_PATH = /path/to/mitsuba

In order to render in Batch mode, you'll need to set two environment variables

- MAYA_RENDER_DESC_PATH has to point to the folder containing the MitsubaRenderer.xml file.

- MAYA_PLUG_IN_PATH has to point to the MitsubaForMaya plug-ins folder

- Example Maya.env settings for Windows:

	- MAYA_RENDER_DESC_PATH = C:\path\to\MitsubaForMaya

	- MAYA_PLUG_IN_PATH = C:\path\to\MitsubaForMaya\plug-ins

****VERY IMPORTANT**** 
If your scene contains animated parameters for the Mitsuba lights or materials and you want to use Maya 2016 or later, you will need to set the following environment variable

- MAYA_RELEASE_PYTHON_GIL = 1

- Without this setting, Maya will lock up.

- [Discussion on Python Programming for Autodesk Maya Google Group](https://groups.google.com/forum/?hl=en#!topic/python_inside_maya/Zk7FKPu7J_A)


Maya.env
-

Maya.env files can be saved in the following folders

- Windows: C:\Users\*username*\Documents\maya\<mayaVersion>

- Mac: /Users/*username*/Library/Preferences/Autodesk/maya/<mayaVersion>

- Linux: /home/*username*/maya/<mayaVersion>

*Autodesk Reference links*

- [Setting the Maya.env](http://help.autodesk.com/view/MAYAUL/2016/ENU/?guid=GUID-8EFB1AC1-ED7D-4099-9EEE-624097872C04)

- [Brief description of MAYA_RENDER_DESC_PATH](http://knowledge.autodesk.com/support/maya/learn-explore/caas/CloudHelp/cloudhelp/2016/ENU/Maya/files/GUID-AF8A7EA4-DEEF-49EF-A18C-CDA72B4F9E1E-htm.html)


Rendering in Batch
-
Rendering an animation in Batch mode works, with a couple of caveats

- Batch renders can't be canceled from the UI

- Animated parameters on Mitsuba shading, lighting and volume nodes aren't supported

Notes
-

The default lighting in Mitsuba is a sunsky, so if you do not use any lighting yourself, that is what this tool will default to as well.  The other lights available are directional, environment maps and object area lights.  Mitsuba supports a variety of other lights, but they have not been ported.  To use a directional light, simply create a normal, Maya directional light and position it as normal.  For an environment map or custom sunsky, see the appropriate nodes in the Hypershader, under Maya/Lights.  Note that you can specify either an environment map or sunsky node (ie you can not have one of each). To use an area light, assign the MitsubaObjectAreaLightShader shader as the Material for the object that you would like to act as an area light.

For a variety of Mitsuba materials, check the Hypershade under Maya/Surface.

Render settings have been set to balance render time vs. quality. The main thing that controls render quality is the sampleCount in the Image Sampler drop down.

References
-

- [Mitsuba](http://www.mitsuba-renderer.org/)

- [Mitsuba Downloads](http://www.mitsuba-renderer.org/download.html)

- [Mitsuba Blog](http://www.mitsuba-renderer.org/devblog/)

- [Mitsuba Respository](https://www.mitsuba-renderer.org/repos/)

- [OpenMaya renderer integrations](https://github.com/haggi/OpenMaya)

- [Irawan Cloth Data Sets](http://www.mitsuba-renderer.org/scenes/irawan.zip)

Testing
-

This plugin was tested with Maya 2016 on OSX Yosemite, Windows 7 and CentOS 7 Linux.

