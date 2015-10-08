import inspect
import os
import sys
import time

import maya.cmds as cmds
import maya.mel as mel
import maya.OpenMaya as OpenMaya
import maya.OpenMayaMPx as OpenMayaMPx

kPluginCmdName = "Mitsuba"

pluginDir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
sys.path.append(pluginDir)

sys.path.append(os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'util')))

from process import Process

# Import modules for settings, material, lights and volumes
import MitsubaRenderSettings

global renderSettings
renderSettings = None


#
# IO
#
import MitsubaRendererIO

#
# Utility functions
#
def registMaterialNodeType(materialNodeType):
    MitsubaRendererIO.materialNodeTypes.append(materialNodeType)

def createRenderSettingsNode():
    global renderSettings
    print( "\n\n\nMitsuba Render Settings - Create Node - Python\n\n\n" )

    existingSettings = cmds.ls(type='MitsubaRenderSettings')
    if existingSettings != []:
        # Just use the first one?
        renderSettings = existingSettings[0]
        print( "Using existing Mitsuba settings node : %s" % renderSettings)
    else:
        renderSettings = cmds.createNode('MitsubaRenderSettings', name='defaultMitsubaRenderGlobals', shared=True)
        print( "Creating new Mitsuba settings node : %s" % renderSettings)

def getRenderSettingsNode():
    global renderSettings
    return renderSettings

def updateRenderSettings():
    global renderSettings
    print( "\n\n\nMitsuba Render Settings - Update - Python\n\n\n" )

#
# UI
#
import MitsubaRendererUI

#
# Renderer functions
#
def renderScene(outFileName, renderDir, mitsubaPath, mtsDir, keepTempFiles, geometryFiles, animation=False, frame=1, verbose=False):
    imageDir = os.path.join(os.path.split(renderDir)[0], 'images')
    os.chdir(imageDir)

    imagePrefix = cmds.getAttr("defaultRenderGlobals.imageFilePrefix")
    if imagePrefix is None:
        imagePrefix = "mitsubaTempRender"
    if animation:
        extensionPadding = cmds.getAttr("defaultRenderGlobals.extensionPadding")
        logName = os.path.join(imageDir, imagePrefix + "." + str(frame).zfill(extensionPadding) +".log")
        imageName = os.path.join(imageDir, imagePrefix + "." + str(frame).zfill(extensionPadding) +".exr")
    else:
        logName = os.path.join(imageDir, imagePrefix + ".log")
        imageName = os.path.join(imageDir, imagePrefix + ".exr")

    args = []
    if verbose:
        args.append('-v')
    args.extend([
        '-o',
        imageName,
        outFileName])
    if ' ' in mtsDir:
        env = {"LD_LIBRARY_PATH":str("\"%s\"" % mtsDir)}
    else:
        env = {"LD_LIBRARY_PATH":str(mtsDir)}
    mitsubaRender = Process(description='render an image',
        cmd=mitsubaPath,
        args=args,
        env=env)
    mitsubaRender.execute()
    #mitsubaRender.write_log_to_disk(logName, format='txt')

    print( "Render execution returned : %s" % mitsubaRender.status )

    if not keepTempFiles:
        #Delete all of the temp file we just made
        os.chdir(renderDir)
        for geometryFile in geometryFiles:
            #print( "Removing geometry : %s" % geometryFile )
            os.remove(geometryFile)
        #print( "Removing mitsuba scene description : %s" % outFileName )
        os.remove(outFileName)
        #os.remove(logName)
    else:
        print( "Keeping temporary files" )

    return imageName

# This registers a mel command to render with Maya
class mitsubaForMaya(OpenMayaMPx.MPxCommand):
    def __init__(self):
        OpenMayaMPx.MPxCommand.__init__(self)

    # Invoked when the command is run.
    def doIt(self,argList):
        global renderSettings

        # Create a render settings node
        createRenderSettingsNode()

        print "Rendering with Mitsuba..."

        #Save the user's selection
        userSelection = cmds.ls(sl=True)
        
        print( "Render Settings - Node            : %s" % renderSettings )

        #Get the directories and other variables
        projectDir = cmds.workspace(q=True, fn=True)
        renderDir = os.path.join(projectDir, "renderData")
        pluginDir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
        version = cmds.about(v=True).replace(" ", "-")

        # Get render settings
        mitsubaPath = cmds.getAttr("%s.%s" % (renderSettings, "mitsubaPath"))
        mtsDir = os.path.split(mitsubaPath)[0]
        integrator = cmds.getAttr("%s.%s" % (renderSettings, "integrator"))
        sampler = cmds.getAttr("%s.%s" % (renderSettings, "sampler"))
        sampleCount = cmds.getAttr("%s.%s" % (renderSettings, "sampleCount"))
        reconstructionFilter = cmds.getAttr("%s.%s" % (renderSettings, "reconstructionFilter"))
        keepTempFiles = cmds.getAttr("%s.%s" % (renderSettings, "keepTempFiles"))
        verbose = cmds.getAttr("%s.%s" % (renderSettings, "verbose"))
        animation = cmds.getAttr("defaultRenderGlobals.animation")

        print( "Render Settings - Mitsuba Path    : %s" % mitsubaPath )
        print( "Render Settings - Integrator      : %s" % integrator )
        print( "Render Settings - Sampler         : %s" % sampler )
        print( "Render Settings - Sample Count    : %s" % sampleCount )
        print( "Render Settings - Reconstruction  : %s" % reconstructionFilter )
        print( "Render Settings - Keep Temp Files : %s" % keepTempFiles )
        print( "Render Settings - Verbose         : %s" % verbose )
        print( "Render Settings - Animation       : %s" % animation )
        print( "Render Settings - Render Dir      : %s" % renderDir )

        if not cmds.about(batch=True) and animation:
            print( "Animation isn't currently supported outside of Batch mode. Rendering current frame." )
            animation = False

        # Animation doesn't work
        if animation:
            startFrame = int(cmds.getAttr("defaultRenderGlobals.startFrame"))
            endFrame = int(cmds.getAttr("defaultRenderGlobals.endFrame"))
            byFrame = int(cmds.getAttr("defaultRenderGlobals.byFrameStep"))
            print( "Animation frame range : %d to %d, step %d" % (
                startFrame, endFrame, byFrame) )

            for frame in range(startFrame, endFrame+1, byFrame):
                print( "Rendering frame " + str(frame) + " - begin" )

                # Calling this leads to Maya locking up
                cmds.currentTime(float(frame))

                print( "Rendering frame " + str(frame) + " - frame set" )

                outFileName = os.path.join(renderDir, "temporary.xml")

                # Export scene and geometry
                geometryFiles = MitsubaRendererIO.writeScene(outFileName, renderDir, renderSettings)
        
                # Render scene, delete scene and geometry
                imageName = renderScene(outFileName, renderDir, mitsubaPath, 
                    mtsDir, keepTempFiles, geometryFiles, animation, frame, verbose)

                print( "Rendering frame " + str(frame) + " - end" )

            print( "Animation finished" )
        else:
            outFileName = os.path.join(renderDir, "temporary.xml")

            # Export scene and geometry
            geometryFiles = MitsubaRendererIO.writeScene(outFileName, renderDir, renderSettings)

            # Render scene
            # Clean up scene and geometry
            imageName = renderScene(outFileName, renderDir, mitsubaPath, 
                mtsDir, keepTempFiles, geometryFiles, verbose=verbose)

            # Display the render
            if not cmds.about(batch=True):
                MitsubaRendererUI.showRender(imageName)

        if cmds.about(batch=True):
            print( "End of Batch Render" )

        # Select the objects that the user had selected before they rendered, or clear the selection
        if len(userSelection) > 0:
            cmds.select(userSelection)
        else:
            cmds.select(cl=True)

def batchRenderProcedure(options):
    print("\n\n\nbatchRenderProcedure: options " + str(options) + "\n\n\n")

def batchRenderOptionsProcedure():
    print("\n\n\nbatchRenderOptionsProcedure\n\n\n")

def batchRenderOptionsStringProcedure():
    print("\n\n\nbatchRenderOptionsStringProcedure\n\n\n")
    return ' -r %s' % kPluginCmdName

def cancelBatchRenderProcedure():
    print("\n\n\ncancelBatchRenderProcedure\n\n\n")

def commandRenderProcedure(options):
    print("\n\n\ncommandRenderProcedure - %s\n\n\n" % options)

    kwargs = {}
    try:
        cmds.Mitsuba(batch=True, **kwargs)
    except RuntimeError, err:
        print err

# Creator
def cmdCreator():
    return OpenMayaMPx.asMPxPtr( mitsubaForMaya() )

# Register Renderer
def registerRenderer():
    # Mel to call rendering functions
    pluginDir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
    renderSettingsMel = os.path.join(pluginDir, "MitsubaRenderer.mel")
    mel.eval('source \"%s\";' % renderSettingsMel.replace('\\', '/'))

    cmds.renderer("Mitsuba", rendererUIName="Mitsuba")
    cmds.renderer("Mitsuba", edit=True, renderProcedure=kPluginCmdName)

    cmds.renderer("Mitsuba", edit=True, batchRenderProcedure="mitsubaBatchRenderProcedure")
    cmds.renderer("Mitsuba", edit=True, batchRenderOptionsProcedure="mitsubaBatchRenderOptionsProcedure")
    cmds.renderer("Mitsuba", edit=True, batchRenderOptionsStringProcedure="mitsubaBatchRenderOptionsStringProcedure")
    cmds.renderer("Mitsuba", edit=True, cancelBatchRenderProcedure="mitsubaCancelBatchRenderProcedure")
    cmds.renderer("Mitsuba", edit=True, commandRenderProcedure="mitsubaCommandRenderProcedure")

    cmds.renderer("Mitsuba", edit=True, addGlobalsTab=("Common", 
        "createMayaSoftwareCommonGlobalsTab", 
        "updateMayaSoftwareCommonGlobalsTab"))

    cmds.renderer("Mitsuba", edit=True, addGlobalsTab=("Mitsuba Common", 
        "mitsubaCreateRenderSettings", 
        "mitsubaUpdateSettingsUpdate"))

    cmds.renderer("Mitsuba", edit=True, addGlobalsNode="defaultMitsubaRenderGlobals" )


# Initialize the script plug-in
def initializePlugin(mobject):
    mplugin = OpenMayaMPx.MFnPlugin(mobject)

    # Load needed plugins
    try:
        if not cmds.pluginInfo( "objExport", query=True, loaded=True ):
            cmds.loadPlugin( "objExport" )
    except:
            sys.stderr.write( "Failed to load objExport plugin\n" )
            raise

    try:
        # Register Mitsuba Renderer
        mplugin.registerCommand( kPluginCmdName, cmdCreator )
    except:
        sys.stderr.write( "Failed to register command: %s\n" % kPluginCmdName )
        raise

    try:
        registerRenderer()
    except:
        sys.stderr.write( "Failed to register renderer: %s\n" % kPluginCmdName )
        raise

# Uninitialize the script plug-in
def uninitializePlugin(mobject):
    global materialNodeModules
    global generalNodeModules

    mplugin = OpenMayaMPx.MFnPlugin(mobject)
    try:
        cmds.renderer("Mitsuba", edit=True, unregisterRenderer=True)
    except:
        sys.stderr.write( "Failed to unregister renderer: %s\n" % kPluginCmdName )

    try:
        mplugin.deregisterCommand( kPluginCmdName )
    except:
        sys.stderr.write( "Failed to unregister command: %s\n" % kPluginCmdName )

