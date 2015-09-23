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

    mIntegrator = OpenMaya.MObject()

    mPathTracerUseInfiniteDepth = OpenMaya.MObject()
    mPathTracerMaxDepth = OpenMaya.MObject()
    mPathTracerRRDepth = OpenMaya.MObject()
    mPathTracerStrictNormals = OpenMaya.MObject()
    mPathTracerHideEmitters = OpenMaya.MObject()

    mSampler = OpenMaya.MObject()
    mSampleCount = OpenMaya.MObject()
    mSamplerDimension = OpenMaya.MObject()
    mSamplerScramble = OpenMaya.MObject()

    mReconstructionFilter = OpenMaya.MObject()

    mKeepTempFiles = OpenMaya.MObject()
    mVerbose = OpenMaya.MObject()

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
        nAttr.setReadable(1)

    @staticmethod
    def addIntegerAttribute(nAttr, attribute, longName, shortName, defaultInt=0):
        setattr(MitsubaRenderSetting, attribute, nAttr.create(longName, shortName, OpenMaya.MFnNumericData.kInt, defaultInt) )
        nAttr.setStorable(1)
        nAttr.setReadable(1)

    @staticmethod
    def addFloatAttribute(nAttr, attribute, longName, shortName, defaultFloat=0.0):
        setattr(MitsubaRenderSetting, attribute, nAttr.create(longName, shortName, OpenMaya.MFnNumericData.kFloat, defaultFloat) )
        nAttr.setStorable(1)
        nAttr.setReadable(1)

    @staticmethod
    def addColorAttribute(nAttr, attribute, longName, shortName, defaultRGB):
        setattr(MitsubaRenderSetting, attribute, nAttr.createColor(longName, shortName) )
        nAttr.setDefault(defaultRGB[0], defaultRGB[1], defaultRGB[2])
        nAttr.setStorable(1)
        nAttr.setReadable(1)

    @staticmethod
    def addStringAttribute(sAttr, attribute, longName, shortName, defaultString=""):
        stringFn = OpenMaya.MFnStringData()
        defaultText = stringFn.create(defaultString)
        setattr(MitsubaRenderSetting, attribute, sAttr.create(longName, shortName, OpenMaya.MFnData.kString, defaultText) )
        sAttr.setStorable(1)
        sAttr.setReadable(1)

def nodeCreator():
    return MitsubaRenderSetting()

def nodeInitializer():
    print "Render Settings initialize!"
    sAttr = OpenMaya.MFnTypedAttribute()
    nAttr = OpenMaya.MFnNumericAttribute()

    try:
        # Path to executable
        MitsubaRenderSetting.addStringAttribute(sAttr, "mMitsubaPath", "mitsubaPath", "mp")

        # Integrator variables
        MitsubaRenderSetting.addStringAttribute(sAttr, "mIntegrator", "integrator", "ig", "Path Tracer")

        # Integrator - Path Tracer variables
        MitsubaRenderSetting.addBooleanAttribute(nAttr, "mPathTracerUseInfiniteDepth", "iPathTracerUseInfiniteDepth", "iptuid", True)
        MitsubaRenderSetting.addIntegerAttribute(nAttr, "mPathTracerMaxDepth", "iPathTracerMaxDepth", "iptmd", 1)
        MitsubaRenderSetting.addIntegerAttribute(nAttr, "mPathTracerRRDepth", "iPathTracerRRDepth", "iptrrd", 1)
        MitsubaRenderSetting.addBooleanAttribute(nAttr, "mPathTracerStrictNormals", "iPathTracerStrictNormals", "iptsn", False)
        MitsubaRenderSetting.addBooleanAttribute(nAttr, "mPathTracerHideEmitters", "iPathTracerHideEmitters", "ipthe", False)

        # Sampler variables
        MitsubaRenderSetting.addStringAttribute(sAttr, "mSampler", "sampler", "sm", "Independent Sampler")
        MitsubaRenderSetting.addIntegerAttribute(nAttr, "mSampleCount", "sampleCount", "sc", 8)
        MitsubaRenderSetting.addIntegerAttribute(nAttr, "mSamplerDimension", "samplerDimension", "sd", 4)
        MitsubaRenderSetting.addIntegerAttribute(nAttr, "mSamplerScramble", "samplerScramble", "ss", -1)

        # Overall controls
        MitsubaRenderSetting.addStringAttribute(sAttr, "mReconstructionFilter", "reconstructionFilter", "rf", "Box filter")

        MitsubaRenderSetting.addBooleanAttribute(nAttr, "mKeepTempFiles", "keepTempFiles", "kt", False)
        MitsubaRenderSetting.addBooleanAttribute(nAttr, "mVerbose", "verbose", "vb", False)
    except:
        sys.stderr.write("Failed to create and add attributes\n")
        raise

    try:
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mMitsubaPath)

        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mIntegrator)

        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mPathTracerUseInfiniteDepth)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mPathTracerMaxDepth)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mPathTracerRRDepth)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mPathTracerStrictNormals)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mPathTracerHideEmitters)

        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mSampler)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mSampleCount)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mSamplerDimension)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mSamplerScramble)

        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mReconstructionFilter)

        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mKeepTempFiles)
        MitsubaRenderSetting.addAttribute(MitsubaRenderSetting.mVerbose)
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
                
