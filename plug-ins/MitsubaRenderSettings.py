import os
import sys
import maya.OpenMaya as OpenMaya
import maya.OpenMayaMPx as OpenMayaMPx
import maya.cmds as cmds

kPluginNodeName = "MitsubaRenderSettings"
kPluginNodeId = OpenMaya.MTypeId(0x87021)

# Command
class MitsubaRenderSetting(OpenMayaMPx.MPxNode):
    # Class variables
    mMitsubaPath = OpenMaya.MObject()

    # Integrator variables
    mIntegrator = OpenMaya.MObject()

    # Sampler variables
    mSampler = OpenMaya.MObject()
    mSampleCount = OpenMaya.MObject()
    mSamplerDimension = OpenMaya.MObject()
    mSamplerScramble = OpenMaya.MObject()

    # Reconstruction Filter variables
    mReconstructionFilter = OpenMaya.MObject()

    # Overall controls
    mKeepTempFiles = OpenMaya.MObject()
    mVerbose = OpenMaya.MObject()

    # Integrator - Path Tracer variables
    mPathTracerUseInfiniteDepth = OpenMaya.MObject()
    mPathTracerMaxDepth = OpenMaya.MObject()
    mPathTracerRRDepth = OpenMaya.MObject()
    mPathTracerStrictNormals = OpenMaya.MObject()
    mPathTracerHideEmitters = OpenMaya.MObject()

    # Integrator - Bidirectional Path Tracer variables
    mBidrectionalPathTracerUseInfiniteDepth = OpenMaya.MObject()
    mBidrectionalPathTracerMaxDepth = OpenMaya.MObject()
    mBidrectionalPathTracerRRDepth = OpenMaya.MObject()
    mBidrectionalPathTracerLightImage = OpenMaya.MObject()
    mBidrectionalPathTracerSampleDirect = OpenMaya.MObject()

    # Integrator - Ambient Occlusion variables
    mAmbientOcclusionShadingSamples = OpenMaya.MObject()
    mAmbientOcclusionUseAutomaticRayLength = OpenMaya.MObject()
    mAmbientOcclusionRayLength = OpenMaya.MObject()

    # Integrator - Direct Illumination variables
    mDirectIlluminationShadingSamples = OpenMaya.MObject()
    mDirectIlluminationUseEmitterAndBSDFSamples = OpenMaya.MObject()
    mDirectIlluminationEmitterSamples = OpenMaya.MObject()
    mDirectIlluminationBSDFSamples = OpenMaya.MObject()
    mDirectIlluminationStrictNormals = OpenMaya.MObject()
    mDirectIlluminationHideEmitters = OpenMaya.MObject()

    # Integrator - Simple Volumetric Path Tracer variables
    mSimpleVolumetricPathTracerUseInfiniteDepth = OpenMaya.MObject()
    mSimpleVolumetricPathTracerMaxDepth = OpenMaya.MObject()
    mSimpleVolumetricPathTracerRRDepth = OpenMaya.MObject()
    mSimpleVolumetricPathTracerStrictNormals = OpenMaya.MObject()
    mSimpleVolumetricPathTracerHideEmitters = OpenMaya.MObject()

    # Integrator - Volumetric Path Tracer variables
    mVolumetricPathTracerUseInfiniteDepth = OpenMaya.MObject()
    mVolumetricPathTracerMaxDepth = OpenMaya.MObject()
    mVolumetricPathTracerRRDepth = OpenMaya.MObject()
    mVolumetricPathTracerStrictNormals = OpenMaya.MObject()
    mVolumetricPathTracerHideEmitters = OpenMaya.MObject()

    # Integrator - Photon Map variables
    mPhotonMapDirectSamples = OpenMaya.MObject()
    mPhotonMapGlossySamples = OpenMaya.MObject()
    mPhotonMapUseInfiniteDepth = OpenMaya.MObject()
    mPhotonMapMaxDepth = OpenMaya.MObject()
    mPhotonMapGlobalPhotons = OpenMaya.MObject()
    mPhotonMapCausticPhotons = OpenMaya.MObject()
    mPhotonMapVolumePhotons = OpenMaya.MObject()
    mPhotonMapGlobalLookupRadius = OpenMaya.MObject()
    mPhotonMapCausticLookupRadius = OpenMaya.MObject()
    mPhotonMapLookupSize = OpenMaya.MObject()
    mPhotonMapGranularity = OpenMaya.MObject()
    mPhotonMapHideEmitters = OpenMaya.MObject()
    mPhotonMapRRDepth = OpenMaya.MObject()

    # Integrator - Progressive Photon Map variables
    mProgressivePhotonMapUseInfiniteDepth = OpenMaya.MObject()
    mProgressivePhotonMapMaxDepth = OpenMaya.MObject()
    mProgressivePhotonMapPhotonCount = OpenMaya.MObject()
    mProgressivePhotonMapInitialRadius = OpenMaya.MObject()
    mProgressivePhotonMapAlpha = OpenMaya.MObject()
    mProgressivePhotonMapGranularity = OpenMaya.MObject()
    mProgressivePhotonMapRRDepth = OpenMaya.MObject()
    mProgressivePhotonMapMaxPasses = OpenMaya.MObject()

    # Integrator - Stochastic Progressive Photon Map variables
    mStochasticProgressivePhotonMapUseInfiniteDepth = OpenMaya.MObject()
    mStochasticProgressivePhotonMapMaxDepth = OpenMaya.MObject()
    mStochasticProgressivePhotonMapPhotonCount = OpenMaya.MObject()
    mStochasticProgressivePhotonMapInitialRadius = OpenMaya.MObject()
    mStochasticProgressivePhotonMapAlpha = OpenMaya.MObject()
    mStochasticProgressivePhotonMapGranularity = OpenMaya.MObject()
    mStochasticProgressivePhotonMapRRDepth = OpenMaya.MObject()
    mStochasticProgressivePhotonMapMaxPasses = OpenMaya.MObject()

    # Integrator - Primary Sample Space Metropolis Light Transport variables
    mPrimarySampleSpaceMetropolisLightTransportBidirectional = OpenMaya.MObject()
    mPrimarySampleSpaceMetropolisLightTransportUseInfiniteDepth = OpenMaya.MObject()
    mPrimarySampleSpaceMetropolisLightTransportMaxDepth = OpenMaya.MObject()
    mPrimarySampleSpaceMetropolisLightTransportDirectSamples = OpenMaya.MObject()
    mPrimarySampleSpaceMetropolisLightTransportRRDepth = OpenMaya.MObject()
    mPrimarySampleSpaceMetropolisLightTransportLuminanceSamples = OpenMaya.MObject()
    mPrimarySampleSpaceMetropolisLightTransportTwoStage = OpenMaya.MObject()
    mPrimarySampleSpaceMetropolisLightTransportPLarge = OpenMaya.MObject()

    def __init__(self):
        OpenMayaMPx.MPxNode.__init__(self)

    # Invoked when the command is evaluated.
    def compute(self, plug, block):
        print "Render Settings evaluate!"
        return OpenMaya.kUnknownParameter

    @staticmethod
    def addBooleanAttribute(nAttr, attribute, longName, shortName, defaultBoolean=True):
        setattr(MitsubaRenderSetting, attribute, nAttr.create(longName, shortName, OpenMaya.MFnNumericData.kBoolean, defaultBoolean) )
        nAttr.setStorable(1)
        nAttr.setWritable(1)
 
    @staticmethod
    def addIntegerAttribute(nAttr, attribute, longName, shortName, defaultInt=0):
        setattr(MitsubaRenderSetting, attribute, nAttr.create(longName, shortName, OpenMaya.MFnNumericData.kInt, defaultInt) )
        nAttr.setStorable(1)
        nAttr.setWritable(1)

    @staticmethod
    def addFloatAttribute(nAttr, attribute, longName, shortName, defaultFloat=0.0):
        setattr(MitsubaRenderSetting, attribute, nAttr.create(longName, shortName, OpenMaya.MFnNumericData.kFloat, defaultFloat) )
        nAttr.setStorable(1)
        nAttr.setWritable(1)

    @staticmethod
    def addColorAttribute(nAttr, attribute, longName, shortName, defaultRGB):
        setattr(MitsubaRenderSetting, attribute, nAttr.createColor(longName, shortName) )
        nAttr.setDefault(defaultRGB[0], defaultRGB[1], defaultRGB[2])
        nAttr.setStorable(1)
        nAttr.setWritable(1)

    @staticmethod
    def addStringAttribute(sAttr, attribute, longName, shortName, defaultString=""):
        stringFn = OpenMaya.MFnStringData()
        defaultText = stringFn.create(defaultString)
        setattr(MitsubaRenderSetting, attribute, sAttr.create(longName, shortName, OpenMaya.MFnData.kString, defaultText) )
        sAttr.setStorable(1)
        sAttr.setWritable(1)

def nodeCreator():
    return MitsubaRenderSetting()

def nodeInitializer():
    print "Render Settings initialize!"
    sAttr = OpenMaya.MFnTypedAttribute()
    nAttr = OpenMaya.MFnNumericAttribute()

    try:
        # Path to executable
        defaultMitsubaPath = os.getenv( "MITSUBA_PATH" )
        if not defaultMitsubaPath:
            defaultMitsubaPath = ""
        MitsubaRenderSetting.addStringAttribute(sAttr, "mMitsubaPath", "mitsubaPath", "mp", defaultMitsubaPath)

        # Integrator variables
        MitsubaRenderSetting.addStringAttribute(sAttr,  "mIntegrator", "integrator", "ig", "Path Tracer")

        # Sampler variables
        MitsubaRenderSetting.addStringAttribute(sAttr,  "mSampler", "sampler", "sm", "Independent Sampler")
        MitsubaRenderSetting.addIntegerAttribute(nAttr, "mSampleCount", "sampleCount", "sc", 8)
        MitsubaRenderSetting.addIntegerAttribute(nAttr, "mSamplerDimension", "samplerDimension", "sd", 4)
        MitsubaRenderSetting.addIntegerAttribute(nAttr, "mSamplerScramble", "samplerScramble", "ss", -1)

        # Reconstruction Filter variables
        MitsubaRenderSetting.addStringAttribute(sAttr,  "mReconstructionFilter", "reconstructionFilter", "rf", "Box filter")

        # Overall controls
        MitsubaRenderSetting.addBooleanAttribute(nAttr, "mKeepTempFiles", "keepTempFiles", "kt", False)
        MitsubaRenderSetting.addBooleanAttribute(nAttr, "mVerbose", "verbose", "vb", False)

        # Integrator - Path Tracer variables
        MitsubaRenderSetting.addBooleanAttribute(nAttr, "mPathTracerUseInfiniteDepth", "iPathTracerUseInfiniteDepth", "iptuid", True)
        MitsubaRenderSetting.addIntegerAttribute(nAttr, "mPathTracerMaxDepth", "iPathTracerMaxDepth", "iptmd", -1)
        MitsubaRenderSetting.addIntegerAttribute(nAttr, "mPathTracerRRDepth", "iPathTracerRRDepth", "iptrrd", 5)
        MitsubaRenderSetting.addBooleanAttribute(nAttr, "mPathTracerStrictNormals", "iPathTracerStrictNormals", "iptsn", False)
        MitsubaRenderSetting.addBooleanAttribute(nAttr, "mPathTracerHideEmitters", "iPathTracerHideEmitters", "ipthe", False)

        # Integrator - Bidirectional Path Tracer variables
        MitsubaRenderSetting.addBooleanAttribute(nAttr, "mBidrectionalPathTracerUseInfiniteDepth", "iBidrectionalPathTracerUseInfiniteDepth", "ibdptuid", True)
        MitsubaRenderSetting.addIntegerAttribute(nAttr, "mBidrectionalPathTracerMaxDepth", "iBidrectionalPathTracerMaxDepth", "ibdptmd", -1)
        MitsubaRenderSetting.addIntegerAttribute(nAttr, "mBidrectionalPathTracerRRDepth", "iBidrectionalPathTracerRRDepth", "ibdptrrd", 5)
        MitsubaRenderSetting.addBooleanAttribute(nAttr, "mBidrectionalPathTracerLightImage", "iBidrectionalPathTracerLightImage", "ibdptli", True)
        MitsubaRenderSetting.addBooleanAttribute(nAttr, "mBidrectionalPathTracerSampleDirect", "iBidrectionalPathTracerSampleDirect", "ibdptsd", True)

        # Integrator - Ambient Occlusion variables
        MitsubaRenderSetting.addIntegerAttribute(nAttr, "mAmbientOcclusionShadingSamples", "iAmbientOcclusionShadingSamples", "iaoss", 1)
        MitsubaRenderSetting.addBooleanAttribute(nAttr, "mAmbientOcclusionUseAutomaticRayLength", "iAmbientOcclusionUseAutomaticRayLength", "iaouarl", True)
        MitsubaRenderSetting.addFloatAttribute(nAttr,   "mAmbientOcclusionRayLength", "iAmbientOcclusionRayLength", "iaorl", -1)

        # Integrator - Direct Illumination variables
        MitsubaRenderSetting.addIntegerAttribute(nAttr, "mDirectIlluminationShadingSamples", "iDirectIlluminationShadingSamples", "idiss", 1)
        MitsubaRenderSetting.addBooleanAttribute(nAttr, "mDirectIlluminationUseEmitterAndBSDFSamples", "iDirectIlluminationUseEmitterAndBSDFSamples", "idiuebs", False)
        MitsubaRenderSetting.addIntegerAttribute(nAttr, "mDirectIlluminationEmitterSamples", "iDirectIlluminationEmitterSamples", "idies", 1)
        MitsubaRenderSetting.addIntegerAttribute(nAttr, "mDirectIlluminationBSDFSamples", "iDirectIlluminationBSDFSamples", "idibs", 1)
        MitsubaRenderSetting.addBooleanAttribute(nAttr, "mDirectIlluminationStrictNormals", "iDirectIlluminationStrictNormals", "idisn", False)
        MitsubaRenderSetting.addBooleanAttribute(nAttr, "mDirectIlluminationHideEmitters", "iDirectIlluminationHideEmitters", "idihe", False)

        # Integrator - Simple Volumetric Path Tracer variables
        MitsubaRenderSetting.addBooleanAttribute(nAttr, "mSimpleVolumetricPathTracerUseInfiniteDepth", "iSimpleVolumetricPathTracerUseInfiniteDepth", "isvptuid", True)
        MitsubaRenderSetting.addIntegerAttribute(nAttr, "mSimpleVolumetricPathTracerMaxDepth", "iSimpleVolumetricPathTracerMaxDepth", "isvptmd", -1)
        MitsubaRenderSetting.addIntegerAttribute(nAttr, "mSimpleVolumetricPathTracerRRDepth", "iSimpleVolumetricPathTracerRRDepth", "isvptrrd", 5)
        MitsubaRenderSetting.addBooleanAttribute(nAttr, "mSimpleVolumetricPathTracerStrictNormals", "iSimpleVolumetricPathTracerStrictNormals", "isvptsn", False)
        MitsubaRenderSetting.addBooleanAttribute(nAttr, "mSimpleVolumetricPathTracerHideEmitters", "iSimpleVolumetricPathTracerHideEmitters", "isvpthe", False)

        # Integrator - Volumetric Path Tracer variables
        MitsubaRenderSetting.addBooleanAttribute(nAttr, "mVolumetricPathTracerUseInfiniteDepth", "iVolumetricPathTracerUseInfiniteDepth", "ivptuid", True)
        MitsubaRenderSetting.addIntegerAttribute(nAttr, "mVolumetricPathTracerMaxDepth", "iVolumetricPathTracerMaxDepth", "ivptmd", -1)
        MitsubaRenderSetting.addIntegerAttribute(nAttr, "mVolumetricPathTracerRRDepth", "iVolumetricPathTracerRRDepth", "ivptrrd", 5)
        MitsubaRenderSetting.addBooleanAttribute(nAttr, "mVolumetricPathTracerStrictNormals", "iVolumetricPathTracerStrictNormals", "ivptsn", False)
        MitsubaRenderSetting.addBooleanAttribute(nAttr, "mVolumetricPathTracerHideEmitters", "iVolumetricPathTracerHideEmitters", "ivpthe", False)

        # Integrator - Photon Map variables
        MitsubaRenderSetting.addIntegerAttribute(nAttr, "mPhotonMapDirectSamples", "iPhotonMapDirectSamples", "ipmds", 16)
        MitsubaRenderSetting.addIntegerAttribute(nAttr, "mPhotonMapGlossySamples", "iPhotonMapGlossySamples", "ipmgs", 32)
        MitsubaRenderSetting.addBooleanAttribute(nAttr, "mPhotonMapUseInfiniteDepth", "iPhotonMapUseInfiniteDepth", "ipmuid", True)
        MitsubaRenderSetting.addIntegerAttribute(nAttr, "mPhotonMapMaxDepth", "iPhotonMapMaxDepth", "ipmmd", -1)
        MitsubaRenderSetting.addIntegerAttribute(nAttr, "mPhotonMapGlobalPhotons", "iPhotonMapGlobalPhotons", "ipmgp", 250000)
        MitsubaRenderSetting.addIntegerAttribute(nAttr, "mPhotonMapCausticPhotons", "iPhotonMapCausticPhotons", "ipmcp", 250000)
        MitsubaRenderSetting.addIntegerAttribute(nAttr, "mPhotonMapVolumePhotons", "iPhotonMapVolumePhotons", "ipmvp", 250000)
        MitsubaRenderSetting.addFloatAttribute(nAttr,   "mPhotonMapGlobalLookupRadius", "iPhotonMapGlobalLookupRadius", "ipmglr", 0.05)
        MitsubaRenderSetting.addFloatAttribute(nAttr,   "mPhotonMapCausticLookupRadius", "iPhotonMapCausticLookupRadius", "ipmclr", 0.0125)
        MitsubaRenderSetting.addIntegerAttribute(nAttr, "mPhotonMapLookupSize", "iPhotonMapLookupSize", "ipmls", 120)
        MitsubaRenderSetting.addIntegerAttribute(nAttr, "mPhotonMapGranularity", "iPhotonMapGranularity", "ipmg", 0)
        MitsubaRenderSetting.addBooleanAttribute(nAttr, "mPhotonMapHideEmitters", "iPhotonMapHideEmitters", "ipmhe", False)
        MitsubaRenderSetting.addIntegerAttribute(nAttr, "mPhotonMapRRDepth", "iPhotonMapRRDepth", "ipmrrd", 5)

        # Integrator - Progressive Photon Map variables
        MitsubaRenderSetting.addBooleanAttribute(nAttr, "mProgressivePhotonMapUseInfiniteDepth", "iProgressivePhotonMapUseInfiniteDepth", "ippmuid", True)
        MitsubaRenderSetting.addIntegerAttribute(nAttr, "mProgressivePhotonMapMaxDepth", "iProgressivePhotonMapMaxDepth", "ippmmd", -1)
        MitsubaRenderSetting.addIntegerAttribute(nAttr, "mProgressivePhotonMapPhotonCount", "iProgressivePhotonMapPhotonCount", "ippmpc", 250000)
        MitsubaRenderSetting.addFloatAttribute(nAttr,   "mProgressivePhotonMapInitialRadius", "iProgressivePhotonMapInitialRadius", "ippmir", 0)
        MitsubaRenderSetting.addFloatAttribute(nAttr,   "mProgressivePhotonMapAlpha", "iProgressivePhotonMapAlpha", "ippma", 0.7)
        MitsubaRenderSetting.addIntegerAttribute(nAttr, "mProgressivePhotonMapGranularity", "iProgressivePhotonMapGranularity", "ippmg", 0)
        MitsubaRenderSetting.addIntegerAttribute(nAttr, "mProgressivePhotonMapRRDepth", "iProgressivePhotonMapRRDepth", "ippmrrd", 5)
        MitsubaRenderSetting.addIntegerAttribute(nAttr, "mProgressivePhotonMapMaxPasses", "iProgressivePhotonMapMaxPasses", "ippmmp", 10)

        # Integrator - Stochastic Progressive Photon Map variables
        MitsubaRenderSetting.addBooleanAttribute(nAttr, "mStochasticProgressivePhotonMapUseInfiniteDepth", "iStochasticProgressivePhotonMapUseInfiniteDepth", "isppmuid", True)
        MitsubaRenderSetting.addIntegerAttribute(nAttr, "mStochasticProgressivePhotonMapMaxDepth", "iStochasticProgressivePhotonMapMaxDepth", "isppmmd", -1)
        MitsubaRenderSetting.addIntegerAttribute(nAttr, "mStochasticProgressivePhotonMapPhotonCount", "iStochasticProgressivePhotonMapPhotonCount", "isppmpc", 250000)
        MitsubaRenderSetting.addFloatAttribute(nAttr,   "mStochasticProgressivePhotonMapInitialRadius", "iStochasticProgressivePhotonMapInitialRadius", "isppmir", 0)
        MitsubaRenderSetting.addFloatAttribute(nAttr,   "mStochasticProgressivePhotonMapAlpha", "iStochasticProgressivePhotonMapAlpha", "isppma", 0.7)
        MitsubaRenderSetting.addIntegerAttribute(nAttr, "mStochasticProgressivePhotonMapGranularity", "iStochasticProgressivePhotonMapGranularity", "isppmg", 0)
        MitsubaRenderSetting.addIntegerAttribute(nAttr, "mStochasticProgressivePhotonMapRRDepth", "iStochasticProgressivePhotonMapRRDepth", "isppmrrd", 5)
        MitsubaRenderSetting.addIntegerAttribute(nAttr, "mStochasticProgressivePhotonMapMaxPasses", "iStochasticProgressivePhotonMapMaxPasses", "isppmmp", 10)


        # Integrator - Primary Sample Space Metropolis Light Transport variables
        MitsubaRenderSetting.addBooleanAttribute(nAttr, "mPrimarySampleSpaceMetropolisLightTransportBidirectional", "iPrimarySampleSpaceMetropolisLightTransportBidirectional", "ipssmltb", True)
        MitsubaRenderSetting.addBooleanAttribute(nAttr, "mPrimarySampleSpaceMetropolisLightTransportUseInfiniteDepth", "iPrimarySampleSpaceMetropolisLightTransportUseInfiniteDepth", "ipssmltuid", True)
        MitsubaRenderSetting.addIntegerAttribute(nAttr, "mPrimarySampleSpaceMetropolisLightTransportMaxDepth", "iPrimarySampleSpaceMetropolisLightTransportMaxDepth", "ipssmltmd", -1)
        MitsubaRenderSetting.addIntegerAttribute(nAttr, "mPrimarySampleSpaceMetropolisLightTransportDirectSamples", "iPrimarySampleSpaceMetropolisLightTransportDirectSamples", "ipssmltds", 16)
        MitsubaRenderSetting.addIntegerAttribute(nAttr, "mPrimarySampleSpaceMetropolisLightTransportRRDepth", "iPrimarySampleSpaceMetropolisLightTransportRRDepth", "ipssmltrrd", 5)
        MitsubaRenderSetting.addIntegerAttribute(nAttr, "mPrimarySampleSpaceMetropolisLightTransportLuminanceSamples", "iPrimarySampleSpaceMetropolisLightTransportLuminanceSamples", "ipssmltls", 100000)
        MitsubaRenderSetting.addBooleanAttribute(nAttr, "mPrimarySampleSpaceMetropolisLightTransportTwoStage", "iPrimarySampleSpaceMetropolisLightTransportTwoStage", "ipssmltts", False)
        MitsubaRenderSetting.addFloatAttribute(nAttr,   "mPrimarySampleSpaceMetropolisLightTransportPLarge", "iPrimarySampleSpaceMetropolisLightTransportPLarge", "ipssmltpl", 0.3)

    except:
        sys.stderr.write("Failed to create and add attributes\n")
        raise

    try:
        # Path to executable
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mMitsubaPath)

        # Integrator variables
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mIntegrator)

        # Sampler variables
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mSampler)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mSampleCount)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mSamplerDimension)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mSamplerScramble)

        # Reconstruction Filter variables
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mReconstructionFilter)

        # Overall controls
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mKeepTempFiles)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mVerbose)

        # Integrator - Path Tracer variables
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mPathTracerUseInfiniteDepth)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mPathTracerMaxDepth)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mPathTracerRRDepth)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mPathTracerStrictNormals)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mPathTracerHideEmitters)

        # Integrator - Bidirectional Path Tracer variables
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mBidrectionalPathTracerUseInfiniteDepth)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mBidrectionalPathTracerMaxDepth)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mBidrectionalPathTracerRRDepth)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mBidrectionalPathTracerLightImage)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mBidrectionalPathTracerSampleDirect)

        # Integrator - Ambient Occlusion variables
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mAmbientOcclusionShadingSamples)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mAmbientOcclusionUseAutomaticRayLength)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mAmbientOcclusionRayLength)

        # Integrator - Direct Illumination variables
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mDirectIlluminationShadingSamples)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mDirectIlluminationUseEmitterAndBSDFSamples)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mDirectIlluminationEmitterSamples)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mDirectIlluminationBSDFSamples)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mDirectIlluminationStrictNormals)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mDirectIlluminationHideEmitters)

        # Integrator - Simple Volumetric Path Tracer variables
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mSimpleVolumetricPathTracerUseInfiniteDepth)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mSimpleVolumetricPathTracerMaxDepth)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mSimpleVolumetricPathTracerRRDepth)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mSimpleVolumetricPathTracerStrictNormals)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mSimpleVolumetricPathTracerHideEmitters)

        # Integrator - Volumetric Path Tracer variables
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mVolumetricPathTracerUseInfiniteDepth)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mVolumetricPathTracerMaxDepth)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mVolumetricPathTracerRRDepth)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mVolumetricPathTracerStrictNormals)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mVolumetricPathTracerHideEmitters)

        # Integrator - Photon Map variables
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mPhotonMapDirectSamples)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mPhotonMapGlossySamples)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mPhotonMapUseInfiniteDepth)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mPhotonMapMaxDepth)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mPhotonMapGlobalPhotons)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mPhotonMapCausticPhotons)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mPhotonMapVolumePhotons)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mPhotonMapGlobalLookupRadius)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mPhotonMapCausticLookupRadius)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mPhotonMapLookupSize)        
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mPhotonMapGranularity)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mPhotonMapHideEmitters)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mPhotonMapRRDepth)

        # Integrator - Progressive Photon Map variables
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mProgressivePhotonMapUseInfiniteDepth)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mProgressivePhotonMapMaxDepth)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mProgressivePhotonMapPhotonCount)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mProgressivePhotonMapInitialRadius)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mProgressivePhotonMapAlpha)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mProgressivePhotonMapGranularity)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mProgressivePhotonMapRRDepth)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mProgressivePhotonMapMaxPasses)

        # Integrator - Stochastic Progressive Photon Map variables
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mStochasticProgressivePhotonMapUseInfiniteDepth)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mStochasticProgressivePhotonMapMaxDepth)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mStochasticProgressivePhotonMapPhotonCount)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mStochasticProgressivePhotonMapInitialRadius)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mStochasticProgressivePhotonMapAlpha)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mStochasticProgressivePhotonMapGranularity)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mStochasticProgressivePhotonMapRRDepth)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mStochasticProgressivePhotonMapMaxPasses)

        # Integrator - Primary Sample Space Metropolis Light Transport variables
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mPrimarySampleSpaceMetropolisLightTransportBidirectional)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mPrimarySampleSpaceMetropolisLightTransportUseInfiniteDepth)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mPrimarySampleSpaceMetropolisLightTransportMaxDepth)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mPrimarySampleSpaceMetropolisLightTransportDirectSamples)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mPrimarySampleSpaceMetropolisLightTransportRRDepth)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mPrimarySampleSpaceMetropolisLightTransportLuminanceSamples)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mPrimarySampleSpaceMetropolisLightTransportTwoStage)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mPrimarySampleSpaceMetropolisLightTransportPLarge)

    except:
        sys.stderr.write("Failed to add attributes\n")
        raise
        
# initialize the script plug-in
def initializePlugin(mobject):
    mplugin = OpenMayaMPx.MFnPlugin(mobject)
    try:
        mplugin.registerNode( kPluginNodeName, 
                              kPluginNodeId, 
                              nodeCreator, 
                              nodeInitializer, 
                              OpenMayaMPx.MPxNode.kDependNode )
    except:
        sys.stderr.write( "Failed to register node: %s" % kPluginNodeName )
        raise

# uninitialize the script plug-in
def uninitializePlugin(mobject):
    mplugin = OpenMayaMPx.MFnPlugin(mobject)
    try:
        mplugin.deregisterNode( kPluginNodeId )
    except:
        sys.stderr.write( "Failed to deregister node: %s" % kPluginNodeName )
        raise
                
