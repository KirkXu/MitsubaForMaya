import getpass
import inspect
import os
import re
import struct
import sys

import maya.cmds as cmds
import maya.mel as mel

##################################################

global renderSettings

##################################################

#Main render settings window
global renderSettingsWindow
global renderWindow
global renderedImage
#Handle to the active integrator
global integrator
global integratorMenu
#List of possible integrators (stored as frameLayouts)
global integratorFrames

global sampler
global samplerMenu
global samplerFrames

global sampleCount

global rfilter
global rfilterMenu

global renderButton
global fileNameField
global hideEmitters

def createIntegratorFrames():
    #Make the integrator specific settings
    global integratorFrames

    integratorFrames = []

    # Ambient Occlusion Settings
    aoSettings = cmds.frameLayout(label="Ambient Occlusion", cll=True, visible=False)

    existingShadingSamples = cmds.getAttr( "%s.%s" % (renderSettings, "iAmbientOcclusionShadingSamples"))
    existingUseAutomaticRayLength = cmds.getAttr( "%s.%s" % (renderSettings, "iAmbientOcclusionUseAutomaticRayLength"))
    existingRayLength = cmds.getAttr( "%s.%s" % (renderSettings, "iAmbientOcclusionRayLength"))

    ss = cmds.intFieldGrp(numberOfFields=1, label="Shading Samples", value1=existingShadingSamples,
        changeCommand=lambda (x): getIntFieldGroup(None, "iAmbientOcclusionShadingSamples", x))

    uarl = cmds.checkBox("Use Automatic Ray Length", value=existingUseAutomaticRayLength, 
        changeCommand=lambda (x): getCheckBox(None, "iAmbientOcclusionUseAutomaticRayLength", x))

    rl = cmds.floatFieldGrp(numberOfFields=1, label="Ray Length", value1=existingRayLength,
        changeCommand=lambda (x): getIntFieldGroup(None, "iAmbientOcclusionRayLength", x))

    cmds.setParent('..')

    # Direct Illumination Settings
    diSettings = cmds.frameLayout(label="Direct Illumination", cll=True, visible=False)

    iDirectIlluminationShadingSamples = cmds.getAttr("%s.%s" % (renderSettings, "iDirectIlluminationShadingSamples"))
    iDirectIlluminationUseEmitterAndBSDFSamples = cmds.getAttr("%s.%s" % (renderSettings, "iDirectIlluminationUseEmitterAndBSDFSamples"))
    iDirectIlluminationEmitterSamples = cmds.getAttr("%s.%s" % (renderSettings, "iDirectIlluminationEmitterSamples"))
    iDirectIlluminationBSDFSamples = cmds.getAttr("%s.%s" % (renderSettings, "iDirectIlluminationBSDFSamples"))
    iDirectIlluminationStrictNormals = cmds.getAttr("%s.%s" % (renderSettings, "iDirectIlluminationStrictNormals"))
    iDirectIlluminationHideEmitters = cmds.getAttr("%s.%s" % (renderSettings, "iDirectIlluminationHideEmitters"))

    ss = cmds.intFieldGrp(numberOfFields=1, label="Shading Samples", value1=iDirectIlluminationShadingSamples, 
        changeCommand=lambda (x): getIntFieldGroup(None, "iDirectIlluminationShadingSamples", x))

    uebs = cmds.checkBox(label = "Use Emitter and BSDF Samples", value=iDirectIlluminationUseEmitterAndBSDFSamples, 
        changeCommand=lambda (x): getCheckBox(None, "iDirectIlluminationUseEmitterAndBSDFSamples", x))

    es = cmds.intFieldGrp(numberOfFields=1, label="Emitter Samples", value1=iDirectIlluminationEmitterSamples, 
        changeCommand=lambda (x): getIntFieldGroup(None, "iDirectIlluminationEmitterSamples", x))

    bs = cmds.intFieldGrp(numberOfFields=1, label="BSDF Samples", value1=iDirectIlluminationBSDFSamples, 
        changeCommand=lambda (x): getIntFieldGroup(None, "iDirectIlluminationBSDFSamples", x))

    sn = cmds.checkBox(label = "Strict Normals", value=iDirectIlluminationStrictNormals, 
        changeCommand=lambda (x): getCheckBox(None, "iDirectIlluminationStrictNormals", x))

    he = cmds.checkBox(label = "Hide Visible Emitters", value=iDirectIlluminationStrictNormals, 
        changeCommand=lambda (x): getCheckBox(None, "iDirectIlluminationStrictNormals", x))    

    cmds.setParent('..')

    # Path Tracer settings
    pSettings = cmds.frameLayout(label="Path Tracer", cll=True)

    existingUseInfiniteDepth = cmds.getAttr( "%s.%s" % (renderSettings, "iPathTracerUseInfiniteDepth"))
    existingMaxDepth = cmds.getAttr( "%s.%s" % (renderSettings, "iPathTracerMaxDepth"))
    existingRRDepth = cmds.getAttr( "%s.%s" % (renderSettings, "iPathTracerRRDepth"))
    existingStrictNormals = cmds.getAttr( "%s.%s" % (renderSettings, "iPathTracerStrictNormals"))
    existingHideEmitters = cmds.getAttr( "%s.%s" % (renderSettings, "iPathTracerHideEmitters"))

    uid = cmds.checkBox("Use Infinite Depth", value=existingUseInfiniteDepth, 
        changeCommand=lambda (x): getCheckBox(None, "iPathTracerUseInfiniteDepth", x))

    md = cmds.intFieldGrp(numberOfFields=1, label="Max Depth", value1=existingMaxDepth, 
        changeCommand=lambda (x): getIntFieldGroup(None, "iPathTracerMaxDepth", x))

    rrd = cmds.intFieldGrp(numberOfFields=1, label="Russian Roulette Depth", value1=existingRRDepth, 
        changeCommand=lambda (x): getIntFieldGroup(None, "iPathTracerRRDepth", x))

    sn = cmds.checkBox(label = "Strict Normals", value=existingStrictNormals, 
        changeCommand=lambda (x): getCheckBox(None, "iPathTracerStrictNormals", x))

    he = cmds.checkBox(label = "Hide Visible Emitters", value=existingHideEmitters, 
        changeCommand=lambda (x): getCheckBox(None, "iPathTracerHideEmitters", x))    

    cmds.setParent('..')

    # Simple Volumetric Path Tracer settings
    vpsSettings = cmds.frameLayout(label="Simple Volumetric Path Tracer", cll=True, visible=False)

    existingUseInfiniteDepth = cmds.getAttr( "%s.%s" % (renderSettings, "iSimpleVolumetricPathTracerUseInfiniteDepth"))
    existingMaxDepth = cmds.getAttr( "%s.%s" % (renderSettings, "iSimpleVolumetricPathTracerMaxDepth"))
    existingRRDepth = cmds.getAttr( "%s.%s" % (renderSettings, "iSimpleVolumetricPathTracerRRDepth"))
    existingStrictNormals = cmds.getAttr( "%s.%s" % (renderSettings, "iSimpleVolumetricPathTracerStrictNormals"))
    existingHideEmitters = cmds.getAttr( "%s.%s" % (renderSettings, "iSimpleVolumetricPathTracerHideEmitters"))

    uid = cmds.checkBox("Use Infinite Depth", value=existingUseInfiniteDepth, 
        changeCommand=lambda (x): getCheckBox(None, "iSimpleVolumetricPathTracerUseInfiniteDepth", x))

    md = cmds.intFieldGrp(numberOfFields=1, label="Max Depth", value1=existingMaxDepth, 
        changeCommand=lambda (x): getIntFieldGroup(None, "iSimpleVolumetricPathTracerMaxDepth", x))

    rrd = cmds.intFieldGrp(numberOfFields=1, label="Russian Roulette Depth", value1=existingRRDepth, 
        changeCommand=lambda (x): getIntFieldGroup(None, "iSimpleVolumetricPathTracerRRDepth", x))

    sn = cmds.checkBox(label = "Strict Normals", value=existingStrictNormals, 
        changeCommand=lambda (x): getCheckBox(None, "iSimpleVolumetricPathTracerStrictNormals", x))

    he = cmds.checkBox(label = "Hide Visible Emitters", value=existingHideEmitters, 
        changeCommand=lambda (x): getCheckBox(None, "iSimpleVolumetricPathTracerHideEmitters", x))    

    cmds.setParent('..')

    # Volumetric Path Tracer settings
    vpSettings = cmds.frameLayout(label="Volumetric Path Tracer", cll=True, visible=False)

    existingUseInfiniteDepth = cmds.getAttr( "%s.%s" % (renderSettings, "iVolumetricPathTracerUseInfiniteDepth"))
    existingMaxDepth = cmds.getAttr( "%s.%s" % (renderSettings, "iVolumetricPathTracerMaxDepth"))
    existingRRDepth = cmds.getAttr( "%s.%s" % (renderSettings, "iVolumetricPathTracerRRDepth"))
    existingStrictNormals = cmds.getAttr( "%s.%s" % (renderSettings, "iVolumetricPathTracerStrictNormals"))
    existingHideEmitters = cmds.getAttr( "%s.%s" % (renderSettings, "iVolumetricPathTracerHideEmitters"))

    uid = cmds.checkBox("Use Infinite Depth", value=existingUseInfiniteDepth, 
        changeCommand=lambda (x): getCheckBox(None, "iVolumetricPathTracerUseInfiniteDepth", x))

    md = cmds.intFieldGrp(numberOfFields=1, label="Max Depth", value1=existingMaxDepth, 
        changeCommand=lambda (x): getIntFieldGroup(None, "iVolumetricPathTracerMaxDepth", x))

    rrd = cmds.intFieldGrp(numberOfFields=1, label="Russian Roulette Depth", value1=existingRRDepth, 
        changeCommand=lambda (x): getIntFieldGroup(None, "iVolumetricPathTracerRRDepth", x))

    sn = cmds.checkBox(label = "Strict Normals", value=existingStrictNormals, 
        changeCommand=lambda (x): getCheckBox(None, "iVolumetricPathTracerStrictNormals", x))

    he = cmds.checkBox(label = "Hide Visible Emitters", value=existingHideEmitters, 
        changeCommand=lambda (x): getCheckBox(None, "iVolumetricPathTracerHideEmitters", x))    

    cmds.setParent('..')

    # Bidirection Path Tracer Settings
    bdptSettings = cmds.frameLayout(label="Bidirectional Path Tracer", cll=True, visible=False)

    existingUseInfiniteDepth = cmds.getAttr( "%s.%s" % (renderSettings, "iBidrectionalPathTracerUseInfiniteDepth"))
    existingMaxDepth = cmds.getAttr( "%s.%s" % (renderSettings, "iBidrectionalPathTracerMaxDepth"))
    existingRRDepth = cmds.getAttr( "%s.%s" % (renderSettings, "iBidrectionalPathTracerRRDepth"))
    existingLightImage = cmds.getAttr( "%s.%s" % (renderSettings, "iBidrectionalPathTracerLightImage"))
    existingSampleDirect = cmds.getAttr( "%s.%s" % (renderSettings, "iBidrectionalPathTracerSampleDirect"))

    uid = cmds.checkBox("Use Infinite Depth", value=existingUseInfiniteDepth,
        changeCommand=lambda (x): getCheckBox(None, "iBidrectionalPathTracerUseInfiniteDepth", x))

    md = cmds.intFieldGrp(numberOfFields=1, label="Max Depth", value1=existingMaxDepth,
        changeCommand=lambda (x): getIntFieldGroup(None, "iBidrectionalPathTracerMaxDepth", x))

    sn = cmds.checkBox(label = "Use Light Images", value=existingLightImage,
        changeCommand=lambda (x): getCheckBox(None, "iBidrectionalPathTracerLightImage", x))  

    he = cmds.checkBox(label = "Enable direct sampling strategies", value=existingSampleDirect,
        changeCommand=lambda (x): getCheckBox(None, "iBidrectionalPathTracerSampleDirect", x))   

    rrd = cmds.intFieldGrp(numberOfFields=1, label="Russian Roulette Depth", value1=existingRRDepth,
        changeCommand=lambda (x): getIntFieldGroup(None, "iBidrectionalPathTracerRRDepth", x))

    cmds.setParent('..')

    pmSettings = cmds.frameLayout(label="Photon Map", cll=True, visible=False)

    iPhotonMapDirectSamples = cmds.getAttr( "%s.%s" % (renderSettings, "iPhotonMapDirectSamples"))
    iPhotonMapGlossySamples = cmds.getAttr( "%s.%s" % (renderSettings, "iPhotonMapGlossySamples"))
    iPhotonMapUseInfiniteDepth = cmds.getAttr( "%s.%s" % (renderSettings, "iPhotonMapUseInfiniteDepth"))
    iPhotonMapMaxDepth = cmds.getAttr( "%s.%s" % (renderSettings, "iPhotonMapMaxDepth"))
    iPhotonMapGlobalPhotons = cmds.getAttr( "%s.%s" % (renderSettings, "iPhotonMapGlobalPhotons"))
    iPhotonMapCausticPhotons = cmds.getAttr( "%s.%s" % (renderSettings, "iPhotonMapCausticPhotons"))
    iPhotonMapVolumePhotons = cmds.getAttr( "%s.%s" % (renderSettings, "iPhotonMapVolumePhotons"))
    iPhotonMapGlobalLookupRadius = cmds.getAttr( "%s.%s" % (renderSettings, "iPhotonMapGlobalLookupRadius"))
    iPhotonMapCausticLookupRadius = cmds.getAttr( "%s.%s" % (renderSettings, "iPhotonMapCausticLookupRadius"))
    iPhotonMapLookupSize = cmds.getAttr( "%s.%s" % (renderSettings, "iPhotonMapLookupSize"))
    iPhotonMapGranularity = cmds.getAttr( "%s.%s" % (renderSettings, "iPhotonMapGranularity"))
    iPhotonMapHideEmitters = cmds.getAttr( "%s.%s" % (renderSettings, "iPhotonMapHideEmitters"))
    iPhotonMapRRDepth = cmds.getAttr( "%s.%s" % (renderSettings, "iPhotonMapRRDepth"))

    cmds.intFieldGrp(numberOfFields=1, label="Direct Samples", value1=iPhotonMapDirectSamples,
        changeCommand=lambda (x): getIntFieldGroup(None, "iPhotonMapDirectSamples", x))

    cmds.intFieldGrp(numberOfFields=1, label="Glossy Samples", value1=iPhotonMapGlossySamples,
        changeCommand=lambda (x): getIntFieldGroup(None, "iPhotonMapGlossySamples", x))

    cmds.checkBox(label = "Use Infinite Depth", value=iPhotonMapUseInfiniteDepth,
        changeCommand=lambda (x): getCheckBox(None, "iPhotonMapUseInfiniteDepth", x))   

    cmds.intFieldGrp(numberOfFields=1, label="Max Depth", value1=iPhotonMapMaxDepth,
        changeCommand=lambda (x): getIntFieldGroup(None, "iPhotonMapMaxDepth", x))

    cmds.intFieldGrp(numberOfFields=1, label="Global Photons", value1=iPhotonMapGlobalPhotons,
        changeCommand=lambda (x): getIntFieldGroup(None, "iPhotonMapGlobalPhotons", x))

    cmds.intFieldGrp(numberOfFields=1, label="Caustic Photons", value1=iPhotonMapCausticPhotons,
        changeCommand=lambda (x): getIntFieldGroup(None, "iPhotonMapCausticPhotons", x))

    cmds.intFieldGrp(numberOfFields=1, label="Volume Photons", value1=iPhotonMapVolumePhotons,
        changeCommand=lambda (x): getIntFieldGroup(None, "iPhotonMapVolumePhotons", x))

    cmds.floatFieldGrp(numberOfFields=1, label="Global Lookup Radius", value1=iPhotonMapGlobalLookupRadius,
        changeCommand=lambda (x): getIntFieldGroup(None, "iPhotonMapGlobalLookupRadius", x))

    cmds.floatFieldGrp(numberOfFields=1, label="Caustic Lookup Radius", value1=iPhotonMapCausticLookupRadius,
        changeCommand=lambda (x): getIntFieldGroup(None, "iPhotonMapCausticLookupRadius", x))

    cmds.intFieldGrp(numberOfFields=1, label="Lookup Size", value1=iPhotonMapLookupSize,
        changeCommand=lambda (x): getIntFieldGroup(None, "iPhotonMapLookupSize", x))

    cmds.intFieldGrp(numberOfFields=1, label="Granularity", value1=iPhotonMapGranularity,
        changeCommand=lambda (x): getIntFieldGroup(None, "iPhotonMapGranularity", x))

    cmds.checkBox(label = "Hide Emitters", value=iPhotonMapHideEmitters,
        changeCommand=lambda (x): getCheckBox(None, "iPhotonMapHideEmitters", x))   

    cmds.intFieldGrp(numberOfFields=1, label="Russian Roulette Depth", value1=iPhotonMapRRDepth,
        changeCommand=lambda (x): getIntFieldGroup(None, "iPhotonMapRRDepth", x))

    cmds.setParent('..')

    ppmSettings = cmds.frameLayout(label="Progressive Photon Map", cll=True, visible=False)
    cmds.checkBox(label = "Use infinite depth", value=True)
    cmds.intFieldGrp(numberOfFields=1, label="maxDepth", value1=1)
    cmds.intFieldGrp(numberOfFields=1, label="photonCount", value1=250000)
    cmds.checkBox(label = "Automatically decide initialRadius")
    cmds.floatFieldGrp(numberOfFields=1, label="initialRadius", value1=0.0)
    cmds.floatFieldGrp(numberOfFields=1, label="alpha", value1=0.7)
    cmds.checkBox(label = "Use automatic granularity")
    cmds.intFieldGrp(numberOfFields=1, label="granularity", value1=0)
    cmds.checkBox(label = "hideEmitters")
    cmds.intFieldGrp(numberOfFields=1, label="rrDepth", value1=1)
    cmds.checkBox(label = "Use infinite maxPasses")
    cmds.intFieldGrp(numberOfFields=1, label="maxPasses", value1=1)
    cmds.setParent('..')

    sppmSettings = cmds.frameLayout(label="Stochastic Progressive Photon Map", cll=True, visible=False)
    cmds.checkBox(label = "Use infinite depth", value=True)
    cmds.intFieldGrp(numberOfFields=1, label="maxDepth", value1=1)
    cmds.intFieldGrp(numberOfFields=1, label="photonCount", value1=250000)
    cmds.checkBox(label = "Automatically decide initialRadius")
    cmds.floatFieldGrp(numberOfFields=1, label="initialRadius", value1=0.0)
    cmds.floatFieldGrp(numberOfFields=1, label="alpha", value1=0.7)
    cmds.checkBox(label = "Use automatic granularity")
    cmds.intFieldGrp(numberOfFields=1, label="granularity", value1=0)
    cmds.checkBox(label = "hideEmitters")
    cmds.intFieldGrp(numberOfFields=1, label="rrDepth", value1=1)
    cmds.checkBox(label = "Use infinite maxPasses")
    cmds.intFieldGrp(numberOfFields=1, label="maxPasses", value1=1)
    cmds.setParent('..')

    pssmltSettings = cmds.frameLayout(label="Primary Sample Space Metropolis Light Transport", cll=True, visible=False)
    cmds.checkBox(label = "bidirectional")
    cmds.checkBox(label = "Use infinite depth", value=True)
    cmds.intFieldGrp(numberOfFields=1, label="maxDepth", value1=1)
    cmds.checkBox(label = "Use automatic direct samples")
    cmds.intFieldGrp(numberOfFields=1, label="directSamples", value1=16)
    cmds.intFieldGrp(numberOfFields=1, label="luminanceSamples", value1=100000)
    cmds.checkBox(label = "twoStage", value=False)
    cmds.checkBox(label = "hideEmitters", value=True)
    cmds.intFieldGrp(numberOfFields=1, label="rrDepth", value1=5)
    cmds.floatFieldGrp(numberOfFields=1, label="pLarge", value1=0.3)
    cmds.setParent('..')

    mltSettings = cmds.frameLayout(label="Path Space Metropolis Light Transport", cll=True, visible=False)
    cmds.checkBox(label = "Use infinite depth", value=True)
    cmds.intFieldGrp(numberOfFields=1, label="maxDepth", value1=1)
    cmds.checkBox(label = "Use automatic direct samples")
    cmds.intFieldGrp(numberOfFields=1, label="directSamples", value1=16)
    cmds.intFieldGrp(numberOfFields=1, label="luminanceSamples", value1=100000)
    cmds.checkBox(label = "twoStage", value=False)
    cmds.checkBox(label = "bidirectionalMutation", value=True)
    cmds.checkBox(label = "lensPerturbation", value=True)
    cmds.checkBox(label = "multiChainPerturbation", value=True)
    cmds.checkBox(label = "causticPerturbation", value=True)
    cmds.checkBox(label = "manifoldPerturbation", value=False)
    cmds.checkBox(label = "hideEmitters", value=True)
    cmds.floatFieldGrp(numberOfFields=1, label="lambda", value1=0.3)
    cmds.setParent('..')

    erptSettings = cmds.frameLayout(label="Energy Redistribution Path Tracer", cll=True, visible=False)
    cmds.checkBox(label = "Use infinite depth", value=True)
    cmds.intFieldGrp(numberOfFields=1, label="maxDepth", value1=1)
    cmds.floatFieldGrp(numberOfFields=1, label="numChains", value1=1.0)
    cmds.checkBox(label = "Enable max chains", value=False)
    cmds.floatFieldGrp(numberOfFields=1, label="maxChains", value1=1.0)
    cmds.checkBox(label = "Use automatic direct samples", value=False)
    cmds.intFieldGrp(numberOfFields=1, label="directSamples", value1=16)
    cmds.checkBox(label = "lensPerturbation", value=True)
    cmds.checkBox(label = "multiChainPerturbation", value=True)
    cmds.checkBox(label = "causticPerturbation", value=True)
    cmds.checkBox(label = "manifoldPerturbation", value=False)
    cmds.checkBox(label = "hideEmitters", value=True)
    cmds.floatFieldGrp(numberOfFields=1, label="lambda", value1=50)
    cmds.setParent('..')

    ptrSettings = cmds.frameLayout(label="Adjoint Particle Tracer", cll=True, visible=False)
    cmds.checkBox(label = "Use infinite depth", value=True)
    cmds.intFieldGrp(numberOfFields=1, label="maxDepth", value1=1)
    cmds.intFieldGrp(numberOfFields=1, label="rrDepth", value1=5)
    cmds.intFieldGrp(numberOfFields=1, label="granularity", value1=200000)
    cmds.checkBox(label = "bruteForce", value=False)
    cmds.checkBox(label = "hideEmitters", value=True)
    cmds.setParent('..')

    integratorFrames.append(aoSettings)
    integratorFrames.append(diSettings)
    integratorFrames.append(pSettings)
    integratorFrames.append(vpsSettings)
    integratorFrames.append(vpSettings)
    integratorFrames.append(bdptSettings)
    integratorFrames.append(pmSettings)
    integratorFrames.append(ppmSettings)
    integratorFrames.append(sppmSettings)
    integratorFrames.append(pssmltSettings)
    integratorFrames.append(mltSettings)
    integratorFrames.append(erptSettings)
    integratorFrames.append(ptrSettings)

def createSamplerFrames():
    global samplerFrames

    samplerFrames = []

    existingSampleCount = cmds.getAttr( "%s.%s" % (renderSettings, "sampleCount"))
    existingSamplerDimension = cmds.getAttr( "%s.%s" % (renderSettings, "samplerDimension"))
    existingSamplerScramble = cmds.getAttr( "%s.%s" % (renderSettings, "samplerScramble"))

    changeSampleCount = lambda (x): getIntFieldGroup(None, "sampleCount", x)
    changeSamplerDimension = lambda (x): getIntFieldGroup(None, "samplerDimension", x)
    changeSamplerScramble = lambda (x): getIntFieldGroup(None, "samplerScramble", x)

    #print( "Existing Sample Count : %s" % existingSampleCount)

    indSettings = cmds.frameLayout(label="Independent Sampler", cll=False, visible=True)
    cmds.setParent('..')

    stratSettings = cmds.frameLayout(label="Stratified Sampler", cll=True, visible=False)
    stratSamplerDimension = cmds.intFieldGrp(numberOfFields=1, label="dimension", value1=existingSamplerDimension)
    cmds.intFieldGrp(stratSamplerDimension, edit=1, changeCommand=changeSamplerDimension)    
    cmds.setParent('..')

    ldSettings = cmds.frameLayout(label="Low Discrepancy Sampler", cll=True, visible=False)
    ldSamplerDimension = cmds.intFieldGrp(numberOfFields=1, label="dimension", value1=existingSamplerDimension)
    cmds.intFieldGrp(ldSamplerDimension, edit=1, changeCommand=changeSamplerDimension)    
    cmds.setParent('..')

    halSettings = cmds.frameLayout(label="Halton QMC Sampler", cll=True, visible=False)
    halSamplerScramble = cmds.intFieldGrp(numberOfFields=1, label="scramble", value1=existingSamplerScramble)
    cmds.intFieldGrp(halSamplerScramble, edit=1, changeCommand=changeSamplerScramble)    
    cmds.setParent('..')

    hamSettings = cmds.frameLayout(label="Hammersley QMC Sampler", cll=True, visible=False)
    hamSamplerScramble = cmds.intFieldGrp(numberOfFields=1, label="scramble", value1=existingSamplerScramble)
    cmds.intFieldGrp(hamSamplerScramble, edit=1, changeCommand=changeSamplerScramble)    
    cmds.setParent('..')

    sobSettings = cmds.frameLayout(label="Sobol QMC Sampler", cll=True, visible=False)
    sobSamplerScramble = cmds.intFieldGrp(numberOfFields=1, label="scramble", value1=existingSamplerScramble)
    cmds.intFieldGrp(sobSamplerScramble, edit=1, changeCommand=changeSamplerScramble)    
    cmds.setParent('..')

    samplerFrames.append(indSettings)
    samplerFrames.append(stratSettings)
    samplerFrames.append(ldSettings)
    samplerFrames.append(halSettings)
    samplerFrames.append(hamSettings)
    samplerFrames.append(sobSettings)

def getRenderSettingsPath(name, renderSettingsAttribute=None):
    global renderSettings

    path = cmds.fileDialog2(fileMode=1, fileFilter="*")
    if path not in [None, []]:
        strPath = str(path[0])
        cmds.textFieldButtonGrp(name, e=1, text=strPath)
        if renderSettingsAttribute:
            cmds.setAttr("%s.%s" % (renderSettings, renderSettingsAttribute), strPath, type="string")

def getCheckBox(name, renderSettingsAttribute=None, value=None):
    global renderSettings

    if renderSettingsAttribute:
        attr = "%s.%s" % (renderSettings, renderSettingsAttribute)
        cmds.setAttr(attr, value)

def getIntFieldGroup(name, renderSettingsAttribute=None, value=None):
    global renderSettings

    if renderSettingsAttribute:
        attr = "%s.%s" % (renderSettings, renderSettingsAttribute)
        cmds.setAttr(attr, value)

def getOptionMenu(name, renderSettingsAttribute=None, value=None):
    global renderSettings

    if renderSettingsAttribute:
        attr = "%s.%s" % (renderSettings, renderSettingsAttribute)
        cmds.setAttr(attr, value, type="string")

'''
This function creates the render settings window.
This includes the integrator, sample generator, image filter,
and film type.
'''
def createRenderSettingsUI():
    global renderSettings

    global renderSettingsWindow
    global integrator
    global integratorMenu
    global sampler
    global samplerMenu
    global rfilter
    global rfilterMenu
    global renderButton

    print( "\n\n\nMitsuba Render Settings - Create UI - Python\n\n\n" )

    #renderSettingsWindow = cmds.window(title="Mitsuba Render Settings", iconName="MTS", widthHeight=(100,250), retain=True, resizeToFitChildren=True)
    cmds.columnLayout(adjustableColumn=True)

    # Path to executable
    mitsubaPathGroup = cmds.textFieldButtonGrp(label="Mitsuba", 
        buttonLabel="Open", buttonCommand="browseFiles")
    # Get default
    existingMitsubaPath = cmds.getAttr( "%s.%s" % (renderSettings, "mitsubaPath"))
    if existingMitsubaPath not in ["", None]:
        cmds.textFieldButtonGrp(mitsubaPathGroup, e=1, text=existingMitsubaPath)
    cmds.textFieldButtonGrp(mitsubaPathGroup, e=1, 
        buttonCommand=lambda: getRenderSettingsPath(mitsubaPathGroup, "mitsubaPath"))

    #Create integrator selection drop down menu
    existingIntegrator = cmds.getAttr( "%s.%s" % (renderSettings, "integrator"))
    #print( "Existing Integrator : %s" % existingIntegrator)

    integratorMenu = cmds.optionMenu(label="Integrator", changeCommand=changeIntegrator)
    cmds.menuItem('Ambient Occlusion')
    cmds.menuItem('Direct Illumination')
    cmds.menuItem('Path Tracer')
    cmds.menuItem('Volumetric Path Tracer')
    cmds.menuItem('Simple Volumetric Path Tracer')
    cmds.menuItem('Bidirectional Path Tracer')
    cmds.menuItem('Photon Map')
    cmds.menuItem('Progressive Photon Map')
    cmds.menuItem('Stochastic Progressive Photon Map')
    cmds.menuItem('Primary Sample Space Metropolis Light Transport')
    cmds.menuItem('Path Space Metropolis Light Transport')
    cmds.menuItem('Energy Redistribution Path Tracer')
    cmds.menuItem('Adjoint Particle Tracer')
    cmds.menuItem('Virtual Point Lights')

    createIntegratorFrames()
    if existingIntegrator not in ["", None]:
        cmds.optionMenu(integratorMenu, edit=True, value=existingIntegrator)
        integrator = existingIntegrator
    else:
        cmds.optionMenu(integratorMenu, edit=True, select=3)
        integrator = "Path Tracer"

    changeIntegrator(integrator)

    existingSampler = cmds.getAttr( "%s.%s" % (renderSettings, "sampler"))
    #print( "Existing Sampler : %s" % existingSampler)

    samplerMenu = cmds.optionMenu(label="Image Sampler", changeCommand=changeSampler)
    cmds.menuItem('Independent Sampler')
    cmds.menuItem('Stratified Sampler')
    cmds.menuItem('Low Discrepancy Sampler')
    cmds.menuItem('Halton QMC Sampler')
    cmds.menuItem('Hammersley QMC Sampler')
    cmds.menuItem('Sobol QMC Sampler')

    createSamplerFrames()
    if existingSampler not in ["", None]:
        cmds.optionMenu(samplerMenu, edit=True, value=existingSampler)
        sampler = existingSampler
    else:
        cmds.optionMenu(samplerMenu, edit=True, select=1)
        sampler = "Independent Sampler"

    changeSampler(sampler)

    existingSampleCount = cmds.getAttr( "%s.%s" % (renderSettings, "sampleCount"))
    changeSampleCount = lambda (x): getIntFieldGroup(None, "sampleCount", x)
    sampleCountGroup = cmds.intFieldGrp(numberOfFields=1, label="sampleCount", value1=existingSampleCount)
    cmds.intFieldGrp(sampleCountGroup, edit=1, changeCommand=changeSampleCount)    

    existingReconstructionFilter = cmds.getAttr( "%s.%s" % (renderSettings, "reconstructionFilter"))
    #print( "Existing Reconstruction Filter : %s" % existingReconstructionFilter)

    rfilterMenu = cmds.optionMenu(label="Film Reconstruction Filter", 
        changeCommand=lambda (x): getOptionMenu(None, "reconstructionFilter", x))
    cmds.menuItem("Box filter")
    cmds.menuItem("Tent filter")
    cmds.menuItem("Gaussian filter")
    cmds.menuItem("Mitchell-Netravali filter")
    cmds.menuItem("Catmull-Rom filter")
    cmds.menuItem("Lanczos filter")

    if existingReconstructionFilter not in ["", None]:
        cmds.optionMenu(rfilterMenu, edit=True, value=existingReconstructionFilter)
        rfilter = existingReconstructionFilter
    else:
        cmds.optionMenu(rfilterMenu, edit=True, select=1)
        rfilter = "Box filter"

    existingKeepTempFiles = cmds.getAttr( "%s.%s" % (renderSettings, "keepTempFiles"))
    keepTempFiles = cmds.checkBox(label="keepTempFiles", value=existingKeepTempFiles)
    cmds.checkBox(keepTempFiles, edit=1,
        changeCommand=lambda (x): getCheckBox(keepTempFiles, "keepTempFiles", x))

    existingVerbose = cmds.getAttr( "%s.%s" % (renderSettings, "verbose"))
    verbose = cmds.checkBox(label="verbose", value=existingVerbose)
    cmds.checkBox(verbose, edit=1,
        changeCommand=lambda (x): getCheckBox(verbose, "verbose", x))


def createRenderSettingsNode():
    global renderSettings
    print( "\n\n\nMitsuba Render Settings - Create Node - Python\n\n\n" )

    existingSettings = cmds.ls(type='MitsubaRenderSettings')
    if existingSettings != []:
        # Just use the first one?
        renderSettings = existingSettings[0]
        print( "Using existing Mitsuba settings node : %s" % renderSettings)
    else:
        renderSettings = cmds.createNode('MitsubaRenderSettings', name='defaultMitsubaRenderGlobals')
        print( "Creating new Mitsuba settings node : %s" % renderSettings)

def createRenderSettings():
    createRenderSettingsNode()
    createRenderSettingsUI()

def updateRenderSettings():
    global renderSettings
    print( "\n\n\nMitsuba Render Settings - Update - Python\n\n\n" )

def createRenderWindow():
    global renderWindow
    global renderedImage

    renderWindow = cmds.window("Mitsuba Rendered Image", retain=True, resizeToFitChildren=True)
    cmds.paneLayout()
    renderedImage = cmds.image()

#Make the render settings window visible
def showRenderSettings(self):
    global renderSettingsWindow

    cmds.showWindow(renderSettingsWindow)

def getRenderWindowPanel():
    renderPanels = cmds.getPanel(scriptType="renderWindowPanel")

    if renderPanels == []: 
        renderPanel = cmds.scriptedPanel(type="renderWindowPanel", unParent=True) 
        #cmds.scriptedPanel(e=True, label=`interToUI $renderPanel` $renderPanel; 
    else: 
        renderPanel = renderPanels[0] 

    return renderPanel

def showRender(fileName):
    renderWindowName = getRenderWindowPanel()
    cmds.renderWindowEditor(renderWindowName, edit=True, loadImage=fileName)

#Make the render window visible
def showRenderWindow(filename):
    global renderWindow

    imageWidth = cmds.getAttr("defaultResolution.width")
    imageHeight = cmds.getAttr("defaultResolution.height")
    cmds.window(renderWindow, edit=True, widthHeight=(imageWidth, imageHeight))
    cmds.showWindow(renderWindow)
    cmds.renderWindowEditor()

#Mel command to render with Mitsuba
def callMitsuba(self):
    cmds.mitsuba()

'''
Since we have a number of integrators that each have a number of properties,
we need to have a number of GUI widgets.  However we only want to show
the settings for the active integrator
'''
def changeIntegrator(selectedIntegrator):
    global integratorMenu
    global integratorFrames
    global integrator

    #print( "selectedIntegrator : %s" % selectedIntegrator )

    #Query the integrator drop down menu to find the active integrator
    selectedIntegrator = cmds.optionMenu(integratorMenu, query=True, value=True)
    #Set all other integrator frameLayout to be invisible
    for frame in integratorFrames:
        currentIntegrator = cmds.frameLayout(frame, query=True, label=True)
        currentIntegratorUnderscore = currentIntegrator.replace(" ", "_")
        if currentIntegrator == selectedIntegrator or currentIntegratorUnderscore == selectedIntegrator:
            cmds.frameLayout(frame, edit=True, visible=True)
        else:
            cmds.frameLayout(frame, edit=True, visible=False) 

    integrator = selectedIntegrator
    getOptionMenu(None, "integrator", selectedIntegrator)

def changeSampler(selectedSampler):
    global samplerMenu
    global samplerFrames
    global sample

    #print( "selectedSampler : %s" % selectedSampler )

    #Query the sampler drop down menu to find the active sampler
    selectedSampler = cmds.optionMenu(samplerMenu, query=True, value=True)
    #Set all other sampler frameLayout to be invisible
    for frame in samplerFrames:
        currentSampler = cmds.frameLayout(frame, query=True, label=True)
        currentSamplerUnderscore = currentSampler.replace(" ", "_")
        if currentSampler == selectedSampler or currentSamplerUnderscore == selectedSampler:
            cmds.frameLayout(frame, edit=True, visible=True)
        else:
            cmds.frameLayout(frame, edit=True, visible=False)

    sampler = selectedSampler
    getOptionMenu(None, "sampler", selectedSampler)


