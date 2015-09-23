import inspect
import os
import sys
import time

import maya.cmds as cmds
import maya.mel as mel
import maya.OpenMaya as OpenMaya
import maya.OpenMayaMPx as OpenMayaMPx

from process import Process

kPluginCmdName = "mitsuba"

pluginDir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
sys.path.append(pluginDir)

# Import modules for settings, material, lights and volumes
import MitsubaRenderSettings

from materials import bump
from materials import coating
from materials import conductor
from materials import dielectric
from materials import difftrans
from materials import diffuse
from materials import mask
from materials import mixturebsdf
from materials import phong
from materials import plastic
from materials import roughcoating
from materials import roughconductor
from materials import roughdielectric
from materials import roughdiffuse
from materials import roughplastic
from materials import thindielectric
from materials import twosided
from materials import ward
from materials import irawan

from volumes import homogeneous
from volumes import volume

from lights import envmap
from lights import sunsky
from lights import arealight

global materialNodeTypes
global materialNodeModules
global generalNodeModules

#The list of possible material types
materialNodeTypes = ["MitsubaBumpShader", 
    "MitsubaSmoothCoatingShader", 
    "MitsubaConductorShader", 
    "MitsubaDielectricShader", 
    "MitsubaDiffuseTransmitterShader", 
    "MitsubaDiffuseShader", 
    "MitsubaMaskShader", 
    "MitsubaMixtureShader", 
    "MitsubaPhongShader", 
    "MitsubaPlasticShader", 
    "MitsubaRoughCoatingShader", 
    "MitsubaRoughConductorShader", 
    "MitsubaRoughDielectricShader", 
    "MitsubaRoughDiffuseShader", 
    "MitsubaRoughPlasticShader", 
    "MitsubaThinDielectricShader", 
    "MitsubaTwoSidedShader", 
    "MitsubaWardShader",
    "MitsubaIrawanShader",
    "MitsubaObjectAreaLightShader"]

materialNodeModules = [
    # materials
    bump,
    coating,
    conductor,
    dielectric,
    difftrans,
    diffuse,
    mask,
    mixturebsdf,
    phong,
    plastic,
    roughcoating,
    roughconductor,
    roughdielectric,
    roughdiffuse,
    roughplastic,
    thindielectric,
    twosided,
    ward,
    irawan,
    # lights
    envmap,
    sunsky,
    arealight,
    # volumes
    homogeneous,
    volume]

generalNodeModules = [
    MitsubaRenderSettings]

#
# UI functions
#
import MitsubaRenderSettingsUI

#
# IO functions
#
import MitsubaForMayaIO

#
# Renderer functions
#
def renderScene(outFileName, projectDir, mitsubaPath, mtsDir, keepTempFiles, geometryFiles, animation=False, frame=1):
    renderDir = os.path.join(projectDir, 'images')
    os.chdir(renderDir)

    imagePrefix = cmds.getAttr("defaultRenderGlobals.imageFilePrefix")
    if imagePrefix is None:
        imagePrefix = "tempRender"
    if animation:
        extensionPadding = cmds.getAttr("defaultRenderGlobals.extensionPadding")
        logName = os.path.join(renderDir, imagePrefix + "." + str(frame).zfill(extensionPadding) +".log")
        imageName = os.path.join(renderDir, imagePrefix + "." + str(frame).zfill(extensionPadding) +".exr")
    else:
        logName = os.path.join(renderDir, imagePrefix + ".log")
        imageName = os.path.join(renderDir, imagePrefix + ".exr")

    args = ['-v',
        '-o',
        imageName,
        outFileName]
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
        os.chdir(os.path.join(projectDir, "renderData"))
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
        print "Rendering with Mitsuba..."

        #Save the user's selection
        userSelection = cmds.ls(sl=True)
        
        renderSettings = MitsubaRenderSettingsUI.renderSettings
        print( "Render Settings - Node            : %s" % renderSettings )

        #Get the directories and other variables
        projectDir = cmds.workspace(q=True, fn=True)
        outFileName = os.path.join(projectDir, "renderData", "temporary.xml")
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
        animation = cmds.getAttr("defaultRenderGlobals.animation")

        print( "Render Settings - Mitsuba Path    : %s" % mitsubaPath )
        print( "Render Settings - Integrator      : %s" % integrator )
        print( "Render Settings - Sampler         : %s" % sampler )
        print( "Render Settings - Sample Count    : %s" % sampleCount )
        print( "Render Settings - Reconstruction  : %s" % reconstructionFilter )
        print( "Render Settings - Keep Temp Files : %s" % keepTempFiles )
        print( "Render Settings - Animation       : %s" % animation )

        if not cmds.about(batch=True) and animation:
            print( "Animation isn't currently supported. Rendering current frame." )
            animation = False

        # Animation doesn't work
        if animation:
            startFrame = int(cmds.getAttr("defaultRenderGlobals.startFrame"))
            endFrame = int(cmds.getAttr("defaultRenderGlobals.endFrame"))
            byFrame = int(cmds.getAttr("defaultRenderGlobals.byFrameStep"))
            print( "Animation frame range : %d to %d, step %d" % (
                startFrame, endFrame, byFrame) )

            for frame in range(startFrame, endFrame+1, byFrame):
                # Calling this leads to Maya locking up
                cmds.currentTime(frame)
                print( "Rendering frame " + str(frame) + " - begin" )

                # Export scene and geometry
                geometryFiles = MitsubaForMayaIO.writeScene(outFileName, projectDir)
        
                # Render scene, delete scene and geometry
                imageName = renderScene(outFileName, projectDir, mitsubaPath, 
                    mtsDir, keepTempFiles, geometryFiles, animation, frame)

                print("Rendering frame " + str(frame) + " - end" )
                time.sleep(2)
        else:
            # Export scene and geometry
            geometryFiles = MitsubaForMayaIO.writeScene(outFileName, projectDir)

            # Render scene
            # Clean up scene and geometry
            imageName = renderScene(outFileName, projectDir, mitsubaPath, 
                mtsDir, keepTempFiles, geometryFiles)

            # Display the render
            MitsubaRenderSettingsUI.showRender(imageName)

        # Select the objects that the user had selected before they rendered, or clear the selection
        if len(userSelection) > 0:
            cmds.select(userSelection)
        else:
            cmds.select(cl=True)

def batchRenderProcedure(options):
    print("batchRenderProcedure: options " + str(options))

def batchRenderOptionsProcedure():
    print("batchRenderOptionsProcedure")

def batchRenderOptionsStringProcedure():
    print("batchRenderOptionsStringProcedure")
    return ' -r Mitsuba'

def cancelBatchRenderProcedure():
    print("cancelBatchRenderProcedure")


# Creator
def cmdCreator():
    return OpenMayaMPx.asMPxPtr( mitsubaForMaya() )

# Initialize the script plug-in
def initializePlugin(mobject):
    global materialNodeModules

    pluginDir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))

    mplugin = OpenMayaMPx.MFnPlugin(mobject)

    try:
        # Load needed plugins
        if not cmds.pluginInfo( "objExport", query=True, loaded=True ):
            cmds.loadPlugin( "objExport" )

        # Register general nodes
        try:
            for generalNodeModule in generalNodeModules:
                mplugin.registerNode( generalNodeModule.kPluginNodeName, 
                    generalNodeModule.kPluginNodeId, 
                    generalNodeModule.nodeCreator, 
                    generalNodeModule.nodeInitializer, 
                    OpenMayaMPx.MPxNode.kDependNode )
                print( "Registered Mitsuba node     : %s" % generalNodeModule.kPluginNodeName)
        except:
                sys.stderr.write( "Failed to register node: %s\n" % generalNodeModule.kPluginNodeName )
                raise

        # Register Materials
        try:
            for materialNodeModule in materialNodeModules:
                mplugin.registerNode( materialNodeModule.kPluginNodeName, 
                    materialNodeModule.kPluginNodeId, 
                    materialNodeModule.nodeCreator, 
                    materialNodeModule.nodeInitializer, 
                    OpenMayaMPx.MPxNode.kDependNode, 
                    materialNodeModule.kPluginNodeClassify )
                print( "Registered Mitsuba material : %s" % materialNodeModule.kPluginNodeName)
        except:
                sys.stderr.write( "Failed to register node: %s\n" % materialNodeModule.kPluginNodeName )
                raise

        # Register Mitsuba Renderer
        mplugin.registerCommand( kPluginCmdName, cmdCreator )

        # Mel to call rendering functions
        renderSettingsMel = os.path.join(pluginDir, "MitsubaForMaya.mel")
        mel.eval('source \"%s\";' % renderSettingsMel.replace('\\', '/'))

        cmds.renderer("Mitsuba", rendererUIName="Mitsuba")
        cmds.renderer("Mitsuba", edit=True, renderProcedure=kPluginCmdName)

        cmds.renderer("Mitsuba", edit=True, batchRenderProcedure="mitsubaBatchRenderProcedure")
        cmds.renderer("Mitsuba", edit=True, batchRenderOptionsProcedure="mitsubaBatchRenderOptionsProcedure")
        cmds.renderer("Mitsuba", edit=True, batchRenderOptionsStringProcedure="mitsubaBatchRenderOptionsStringProcedure")
        cmds.renderer("Mitsuba", edit=True, cancelBatchRenderProcedure="mitsubaCancelBatchRenderProcedure")

        cmds.renderer("Mitsuba", edit=True, addGlobalsTab=("Common", 
            "createMayaSoftwareCommonGlobalsTab", 
            "updateMayaSoftwareCommonGlobalsTab"))

        cmds.renderer("Mitsuba", edit=True, addGlobalsTab=("Mitsuba Common", 
            "mitsubaCreateRenderSettings", 
            "mitsubaUpdateSettingsUpdate"))

        cmds.renderer("Mitsuba", edit=True, addGlobalsNode="defaultMitsubaRenderGlobals" )

        # Create a render settings node
        MitsubaRenderSettingsUI.createRenderSettingsNode()

    except:
        sys.stderr.write( "Failed to register command: %s\n" % kPluginCmdName )
        raise

# Uninitialize the script plug-in
def uninitializePlugin(mobject):
    global materialNodeModules

    mplugin = OpenMayaMPx.MFnPlugin(mobject)
    try:
        cmds.renderer("Mitsuba", edit=True, unregisterRenderer=True)
    except:
        sys.stderr.write( "Failed to unregister renderer: Mitsuba\n" )

    try:
        mplugin.deregisterCommand( kPluginCmdName )

        # Unregister materials
        try:
            for materialNodeModule in materialNodeModules:
                mplugin.deregisterNode( materialNodeModule.kPluginNodeId )
        except:
                sys.stderr.write( "Failed to deregister node: %s\n" % materialNodeModule.kPluginNodeName )
                raise

        # Unregister general nodes
        try:
            for generalNodeModule in generalNodeModules:
                mplugin.deregisterNode( generalNodeModule.kPluginNodeId )
        except:
                sys.stderr.write( "Failed to deregister node: %s\n" % generalNodeModule.kPluginNodeName )
                raise

    except:
        sys.stderr.write( "Failed to unregister command: %s\n" % kPluginCmdName )

##################################################
