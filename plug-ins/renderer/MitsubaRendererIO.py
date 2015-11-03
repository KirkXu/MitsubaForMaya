import os
import struct

import maya.cmds as cmds
import maya.mel as mel
import maya.OpenMaya as OpenMaya
import maya.OpenMayaMPx as OpenMayaMPx

import pymel.core

# Will be populated as materials are registered with Maya
materialNodeTypes = []

#
# Formatted printing
#
def writeElementText(element, depth=0):
    #print( "element : %s" % str(element) )

    if element in [{}, None]:
        return ""

    if 'attributes' in element:
        attributes = element['attributes']
    else:
        attributes = {}
    if 'children' in element:
        children = element['children']
    else:
        children = []
    typeName = element['type']

    spacing = '\t'*depth

    elementText = ""
    elementText += spacing + "<%s" % typeName
    for key, value in attributes.iteritems():
        elementText += " %s=\"%s\"" % (key, value)
    if children:
        elementText += ">\n"
        for child in children:
            #print( "child : %s" % str(child) )
            elementText += writeElementText(child, depth+1)
            #element += "\n"
        elementText  += spacing + "</%s>\n" % typeName
    else:
        elementText += "/>\n"
    
    return elementText

# Other options to be provided later
def writeElement(outFile, element, depth=0):
    elementText = writeElementText(element, depth)
    outFile.write(elementText)

#
# IO functions
#
'''
Returns the surfaceShader node for a piece of geometry (geom)
'''
def getShader(geom):
    shapeNode = cmds.listRelatives(geom, children=True, shapes=True)[0]
    sg = cmds.listConnections(shapeNode, type="shadingEngine")[0]
    shader = cmds.listConnections(sg+".surfaceShader")
    if shader is None:
        shader = cmds.listConnections(sg+".volumeShader")
    return shader[0]

'''
Writes a homogeneous medium to a Mitsuba scene file (outFile)
tabbedSpace is a string of blank space to account for recursive xml
'''
def writeMedium(medium):
    sigmaAS = cmds.getAttr(medium+".sigmaAS")
    sigmaA = cmds.getAttr(medium+".sigmaA")
    sigmaS = cmds.getAttr(medium+".sigmaS")
    sigmaT = cmds.getAttr(medium+".sigmaT")
    albedo = cmds.getAttr(medium+".albedo")
    scale = cmds.getAttr(medium+".scale")    

    # Create a structure to be written
    elementDict = {'type':'medium'}
    elementDict['attributes'] = {'type':'homogeneous', 'name':'interior'}

    elementDict['children'] = []

    if sigmaAS:
        elementDict['children'].append( { 'type':'rgb', 
            'attributes':{ 'name':'sigmaA', 'value':str(sigmaA[0][0]) + " " + str(sigmaA[0][1]) + " " + str(sigmaA[0][2]) } } )
        elementDict['children'].append( { 'type':'rgb', 
            'attributes':{ 'name':'sigmaS', 'value':str(sigmaS[0][0]) + " " + str(sigmaS[0][1]) + " " + str(sigmaS[0][2]) } } )
    else:
        elementDict['children'].append( { 'type':'rgb', 
            'attributes':{ 'name':'sigmaT', 'value':str(sigmaT[0][0]) + " " + str(sigmaT[0][1]) + " " + str(sigmaT[0][2]) } } )
        elementDict['children'].append( { 'type':'rgb', 
            'attributes':{ 'name':'albedo', 'value':str(albedo[0][0]) + " " + str(albedo[0][1]) + " " + str(albedo[0][2]) } } )

    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'scale', 'value':str(scale) } } )

    return elementDict


def getTextureFile(material, connectionAttr):
    connections = cmds.listConnections(material, connections=True)
    fileTexture = None
    for i in range(len(connections)):
        if i%2==1:
            connection = connections[i]
            connectionType = cmds.nodeType(connection)
            if connectionType == "file" and connections[i-1]==(material+"."+connectionAttr):
                fileTexture = cmds.getAttr(connection+".fileTextureName")
                hasFile=True
                #print( "Found texture : %s" % fileTexture )
                animatedTexture = cmds.getAttr("%s.%s" % (connection, "useFrameExtension"))
                if animatedTexture:
                    textureFrameNumber = cmds.getAttr("%s.%s" % (connection, "frameExtension"))
                    # Should make this an option at some point
                    tokens = fileTexture.split('.')
                    tokens[-2] = str(textureFrameNumber).zfill(4)
                    fileTexture = '.'.join(tokens)
                    #print( "Animated texture path : %s" % fileTexture )
            #else:
            #    print "Source can only be an image file"

    return fileTexture

def writeShaderSmoothCoating(material, materialName):
    intIOR = cmds.getAttr(material+".intIOR")
    extIOR = cmds.getAttr(material+".extIOR")
    thickness = cmds.getAttr(material+".thickness")
    sigmaA = cmds.getAttr(material+".sigmaA")
    specularReflectance = cmds.getAttr(material+".specularReflectance")

    # Create a structure to be written
    elementDict = {'type':'bsdf'}
    elementDict['attributes'] = {'type':'coating', 'id':materialName}

    elementDict['children'] = []
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'intIOR', 'value':str(intIOR) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'extIOR', 'value':str(extIOR) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'thickness', 'value':str(thickness) } } )
    elementDict['children'].append( { 'type':'srgb', 
        'attributes':{ 'name':'sigmaA', 'value':str(sigmaA[0][0]) + " " + str(sigmaA[0][1]) + " " + str(sigmaA[0][2]) } } )
    elementDict['children'].append( { 'type':'srgb', 
        'attributes':{ 'name':'specularReflectance', 'value':str(specularReflectance[0][0]) + " " + str(specularReflectance[0][1]) + " " + str(specularReflectance[0][2]) } } )

    #Nested bsdf
    hasNestedBSDF = False
    connections = cmds.listConnections(material, connections=True)
    for i in range(len(connections)):
        if i%2==1:
            connection = connections[i]
            connectionType = cmds.nodeType(connection)
            if connectionType in materialNodeTypes and connections[i-1]==material+".bsdf":
                #We've found the nested bsdf, so write it
                shaderElement = writeShader(connection, connection)
                elementDict['children'].append(shaderElement)
                hasNestedBSDF = True

    if not hasNestedBSDF:
        bsdf = cmds.getAttr(material+".bsdf")
        nestedBSDFElement = {'type':'bsdf'}
        nestedBSDFElement['attributes'] = {'type':'diffuse'}

        nestedBSDFElement['children'] = []
        nestedBSDFElement['children'].append( { 'type':'srgb', 
            'attributes':{ 'name':'reflectance', 'value':str(bsdf[0][0]) + " " + str(bsdf[0][1]) + " " + str(bsdf[0][2]) } } )

        elementDict['children'].append( nestedBSDFElement )

    return elementDict

def writeShaderConductor(material, materialName):
    conductorMaterialUI = cmds.getAttr(material+".material", asString=True)
    extEta = cmds.getAttr(material+".extEta")

    conductorMaterialUIToPreset = {
        "100\% reflecting mirror" : "none",
        "Amorphous carbon" : "a-C",
        "Silver" : "Ag",
        "Aluminium" : "Al",
        "Cubic aluminium arsenide" : "AlAs",
        "Cubic aluminium antimonide" : "AlSb",
        "Gold" : "Au",
        "Polycrystalline beryllium" : "Be",
        "Chromium" : "Cr",
        "Cubic caesium iodide" : "CsI",
        "Copper" : "Cu",
        "Copper (I) oxide" : "Cu2O",
        "Copper (II) oxide" : "CuO",
        "Cubic diamond" : "d-C",
        "Mercury" : "Hg",
        "Mercury telluride" : "HgTe",
        "Iridium" : "Ir",
        "Polycrystalline potassium" : "K",
        "Lithium" : "Li",
        "Magnesium oxide" : "MgO",
        "Molybdenum" : "Mo",
        "Sodium" : "Na_palik",
        "Niobium" : "Nb",
        "Nickel" : "Ni_palik",
        "Rhodium" : "Rh",
        "Selenium" : "Se",
        "Hexagonal silicon carbide" : "SiC",
        "Tin telluride" : "SnTe",
        "Tantalum" : "Ta",
        "Trigonal tellurium" : "Te",
        "Polycryst. thorium (IV) fuoride" : "ThF4",
        "Polycrystalline titanium carbide" : "TiC",
        "Titanium nitride" : "TiN",
        "Tetragonal titan. dioxide" : "TiO2",
        "Vanadium carbide" : "VC",
        "Vanadium" : "V_palik",
        "Vanadium nitride" : "VN",
        "Tungsten" : "W",
    }

    if conductorMaterialUI in conductorMaterialUIToPreset:
        conductorMaterialPreset = conductorMaterialUIToPreset[conductorMaterialUI]
    else:
        # Default to a perfectly reflective mirror
        conductorMaterialPreset = "none"

    # Create a structure to be written
    elementDict = {'type':'bsdf'}
    elementDict['attributes'] = {'type':'conductor', 'id':materialName}

    elementDict['children'] = []
    elementDict['children'].append( { 'type':'string', 
        'attributes':{ 'name':'material', 'value':str(conductorMaterialPreset) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'extEta', 'value':str(extEta) } } )

    return elementDict

def writeShaderDielectric(material, materialName):
    #Get all of the required attributes
    intIOR = cmds.getAttr(material+".intIOR")
    extIOR = cmds.getAttr(material+".extIOR")

    # Create a structure to be written
    elementDict = {'type':'bsdf'}
    elementDict['attributes'] = {'type':'dielectric', 'id':materialName}

    elementDict['children'] = []
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'intIOR', 'value':str(intIOR) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'extIOR', 'value':str(extIOR) } } )

    return elementDict

def writeShaderDiffuseTransmitter(material, materialName):
    # Get values from the scene
    transmittance = cmds.getAttr(material+".reflectance")

    # Create a structure to be written
    elementDict = {'type':'bsdf'}
    elementDict['attributes'] = {'type':'diffuse', 'id':materialName}

    elementDict['children'] = []
    elementDict['children'].append( { 'type':'srgb', 
        'attributes':{ 'name':'reflectance', 'value':str(transmittance[0][0]) + " " + str(transmittance[0][1]) + " " + str(transmittance[0][2]) } } )

    return elementDict

def writeShaderDiffuse(material, materialName):
    # Get values from the scene
    #texture
    connectionAttr = "reflectance"
    fileTexture = getTextureFile(material, connectionAttr)
    if not fileTexture:
        reflectance = cmds.getAttr(material+".reflectance")

    # Create a structure to be written
    elementDict = {'type':'bsdf'}
    elementDict['attributes'] = {'type':'diffuse', 'id':materialName}

    elementDict['children'] = []
    if fileTexture:
        textureElementDict = {'type':'texture'}
        textureElementDict['attributes'] = {'type':'bitmap', 'name':'reflectance'}

        textureElementDict['children'] = []
        textureElementDict['children'].append( { 'type':'string', 
            'attributes':{ 'name':'filename', 'value':fileTexture } } )

        elementDict['children'].append( textureElementDict )
    else:
        elementDict['children'].append( { 'type':'srgb', 
            'attributes':{ 'name':'reflectance', 'value':str(reflectance[0][0]) + " " + str(reflectance[0][1]) + " " + str(reflectance[0][2]) } } )

    return elementDict

def writeShaderPhong(material, materialName):
    exponent = cmds.getAttr(material+".exponent")
    specularReflectance = cmds.getAttr(material+".specularReflectance")
    diffuseReflectance = cmds.getAttr(material+".diffuseReflectance")

    # Create a structure to be written
    elementDict = {'type':'bsdf'}
    elementDict['attributes'] = {'type':'phong', 'id':materialName}

    elementDict['children'] = []
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'exponent', 'value':str(exponent) } } )
    elementDict['children'].append( { 'type':'srgb', 
        'attributes':{ 'name':'specularReflectance', 'value':str(specularReflectance[0][0]) + " " + str(specularReflectance[0][1]) + " " + str(specularReflectance[0][2]) } } )
    elementDict['children'].append( { 'type':'srgb', 
        'attributes':{ 'name':'diffuseReflectance', 'value':str(diffuseReflectance[0][0]) + " " + str(diffuseReflectance[0][1]) + " " + str(diffuseReflectance[0][2]) } } )

    return elementDict


def writeShaderPlastic(material, materialName):
    intIOR = cmds.getAttr(material+".intIOR")
    extIOR = cmds.getAttr(material+".extIOR")
    specularReflectance = cmds.getAttr(material+".specularReflectance")
    diffuseReflectance = cmds.getAttr(material+".diffuseReflectance")

    # Create a structure to be written
    elementDict = {'type':'bsdf'}
    elementDict['attributes'] = {'type':'plastic', 'id':materialName}

    elementDict['children'] = []
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'intIOR', 'value':str(intIOR) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'extIOR', 'value':str(extIOR) } } )
    elementDict['children'].append( { 'type':'srgb', 
        'attributes':{ 'name':'specularReflectance', 'value':str(specularReflectance[0][0]) + " " + str(specularReflectance[0][1]) + " " + str(specularReflectance[0][2]) } } )
    elementDict['children'].append( { 'type':'srgb', 
        'attributes':{ 'name':'diffuseReflectance', 'value':str(diffuseReflectance[0][0]) + " " + str(diffuseReflectance[0][1]) + " " + str(diffuseReflectance[0][2]) } } )

    return elementDict

def writeShaderRoughCoating(material, materialName):
    distribution = cmds.getAttr(material+".distribution", asString=True)
    alpha = cmds.getAttr(material+".alpha")
    intIOR = cmds.getAttr(material+".intIOR")
    extIOR = cmds.getAttr(material+".extIOR")
    thickness = cmds.getAttr(material+".thickness")
    sigmaA = cmds.getAttr(material+".sigmaA")
    specularReflectance = cmds.getAttr(material+".specularReflectance")

    # Create a structure to be written
    elementDict = {'type':'bsdf'}
    elementDict['attributes'] = {'type':'coating', 'id':materialName}

    elementDict['children'] = []
    elementDict['children'].append( { 'type':'string', 
        'attributes':{ 'name':'distribution', 'value':str(distribution) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'alpha', 'value':str(alpha) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'intIOR', 'value':str(intIOR) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'extIOR', 'value':str(extIOR) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'thickness', 'value':str(thickness) } } )
    elementDict['children'].append( { 'type':'srgb', 
        'attributes':{ 'name':'sigmaA', 'value':str(sigmaA[0][0]) + " " + str(sigmaA[0][1]) + " " + str(sigmaA[0][2]) } } )
    elementDict['children'].append( { 'type':'srgb', 
        'attributes':{ 'name':'specularReflectance', 'value':str(specularReflectance[0][0]) + " " + str(specularReflectance[0][1]) + " " + str(specularReflectance[0][2]) } } )

    #Nested bsdf
    hasNestedBSDF = False
    connections = cmds.listConnections(material, connections=True)
    for i in range(len(connections)):
        if i%2==1:
            connection = connections[i]
            connectionType = cmds.nodeType(connection)
            if connectionType in materialNodeTypes and connections[i-1]==material+".bsdf":
                #We've found the nested bsdf, so write it
                shaderElement = writeShader(connection, connection)
                elementDict['children'].append(shaderElement)
                hasNestedBSDF = True

    if not hasNestedBSDF:
        bsdf = cmds.getAttr(material+".bsdf")
        nestedBSDFElement = {'type':'bsdf'}
        nestedBSDFElement['attributes'] = {'type':'diffuse'}

        nestedBSDFElement['children'] = []
        nestedBSDFElement['children'].append( { 'type':'srgb', 
            'attributes':{ 'name':'reflectance', 'value':str(bsdf[0][0]) + " " + str(bsdf[0][1]) + " " + str(bsdf[0][2]) } } )

        elementDict['children'].append( nestedBSDFElement )

    return elementDict


def writeShaderRoughConductor(material, materialName):
    distribution = cmds.getAttr(material+".distribution", asString=True)
    alphaUV = cmds.getAttr(material+".alphaUV")
    alpha = cmds.getAttr(material+".alpha")
    conductorMaterial = cmds.getAttr(material+".material")
    extEta = cmds.getAttr(material+"extEta")

    # Create a structure to be written
    elementDict = {'type':'bsdf'}
    elementDict['attributes'] = {'type':'roughconductor', 'id':materialName}

    elementDict['children'] = []

    elementDict['children'].append( { 'type':'string', 
        'attributes':{ 'name':'distribution', 'value':str(distribution) } } )
    if distribution == "as":
        elementDict['children'].append( { 'type':'float', 
            'attributes':{ 'name':'alphaU', 'value':str(alphaUV[0]) } } )
        elementDict['children'].append( { 'type':'float', 
            'attributes':{ 'name':'alphaV', 'value':str(alphaUV[1]) } } )
    else:
        elementDict['children'].append( { 'type':'float', 
            'attributes':{ 'name':'alpha', 'value':str(alpha) } } )

    elementDict['children'].append( { 'type':'string', 
        'attributes':{ 'name':'material', 'value':str(conductorMaterial) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'extEta', 'value':str(extEta) } } )

    return elementDict

def writeShaderRoughDielectric(material, materialName):
    #Get all of the required attributes
    intIOR = cmds.getAttr(material+".intIOR")
    extIOR = cmds.getAttr(material+".extIOR")
    specularReflectance = cmds.getAttr(material+".specularReflectance")
    specularTransmittance = cmds.getAttr(material+".specularTransmittance")
    distribution = cmds.getAttr(material+".distribution", asString=True)
    alphaUV = cmds.getAttr(material+".alphaUV")
    alpha = cmds.getAttr(material+".alpha")

    # Create a structure to be written
    elementDict = {'type':'bsdf'}
    elementDict['attributes'] = {'type':'roughdielectric', 'id':materialName}

    elementDict['children'] = []

    elementDict['children'].append( { 'type':'string', 
        'attributes':{ 'name':'distribution', 'value':str(distribution) } } )
    if distribution == "as":
        elementDict['children'].append( { 'type':'float', 
            'attributes':{ 'name':'alphaU', 'value':str(alphaUV[0]) } } )
        elementDict['children'].append( { 'type':'float', 
            'attributes':{ 'name':'alphaV', 'value':str(alphaUV[1]) } } )
    else:
        elementDict['children'].append( { 'type':'float', 
            'attributes':{ 'name':'alpha', 'value':str(alpha) } } )

    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'intIOR', 'value':str(intIOR) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'extIOR', 'value':str(extIOR) } } )
    elementDict['children'].append( { 'type':'srgb', 
        'attributes':{ 'name':'specularReflectance', 'value':str(specularReflectance[0][0]) + " " + str(specularReflectance[0][1]) + " " + str(specularReflectance[0][2]) } } )
    elementDict['children'].append( { 'type':'srgb', 
        'attributes':{ 'name':'specularTransmittance', 'value':str(specularTransmittance[0][0]) + " " + str(specularTransmittance[0][1]) + " " + str(specularTransmittance[0][2]) } } )

    return elementDict


def writeShaderRoughDiffuse(material, materialName):
    reflectance = cmds.getAttr(material+".reflectance")
    alpha = cmds.getAttr(material+".alpha")
    useFastApprox = cmds.getAttr(material+".useFastApprox")
    useFastApproxText = 'true' if useFastApprox else 'false'

    # Create a structure to be written
    elementDict = {'type':'bsdf'}
    elementDict['attributes'] = {'type':'roughdiffuse', 'id':materialName}

    elementDict['children'] = []
    elementDict['children'].append( { 'type':'srgb', 
        'attributes':{ 'name':'reflectance', 'value':str(specularReflectance[0][0]) + " " + str(specularReflectance[0][1]) + " " + str(specularReflectance[0][2]) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'alpha', 'value':str(alpha) } } )
    elementDict['children'].append( { 'type':'boolean', 
        'attributes':{ 'name':'useFastApprox', 'value':str(useFastApproxText) } } )

    return elementDict

def writeShaderRoughPlastic(material, materialName):
    distribution = cmds.getAttr(material+".distribution", asString=True)
    alpha = cmds.getAttr(material+".alpha")
    intIOR = cmds.getAttr(material+".intIOR")
    extIOR = cmds.getAttr(material+".extIOR")
    specularReflectance = cmds.getAttr(material+".specularReflectance")
    diffuseReflectance = cmds.getAttr(material+".diffuseReflectance")

    # Create a structure to be written
    elementDict = {'type':'bsdf'}
    elementDict['attributes'] = {'type':'roughplastic', 'id':materialName}

    elementDict['children'] = []
    elementDict['children'].append( { 'type':'string', 
        'attributes':{ 'name':'distribution', 'value':str(distribution) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'alpha', 'value':str(alpha) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'intIOR', 'value':str(intIOR) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'extIOR', 'value':str(extIOR) } } )
    elementDict['children'].append( { 'type':'srgb', 
        'attributes':{ 'name':'specularReflectance', 'value':str(specularReflectance[0][0]) + " " + str(specularReflectance[0][1]) + " " + str(specularReflectance[0][2]) } } )
    elementDict['children'].append( { 'type':'srgb', 
        'attributes':{ 'name':'diffuseReflectance', 'value':str(diffuseReflectance[0][0]) + " " + str(diffuseReflectance[0][1]) + " " + str(diffuseReflectance[0][2]) } } )

    return elementDict


def writeShaderThinDielectric(material, materialName):
    #Get all of the required attributes
    intIOR = cmds.getAttr(material+".intIOR")
    extIOR = cmds.getAttr(material+".extIOR")

    # Create a structure to be written
    elementDict = {'type':'bsdf'}
    elementDict['attributes'] = {'type':'thindielectric', 'id':materialName}

    elementDict['children'] = []
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'intIOR', 'value':str(intIOR) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'extIOR', 'value':str(extIOR) } } )

    return elementDict


def writeShaderWard(material, materialName):
    variant = cmds.getAttr(material+".variant", asString=True)
    alphaUV = cmds.getAttr(material+".alphaUV")
    specularReflectance = cmds.getAttr(material+".specularReflectance")
    diffuseReflectance = cmds.getAttr(material+".diffuseReflectance")

    # Create a structure to be written
    elementDict = {'type':'bsdf'}
    elementDict['attributes'] = {'type':'phong', 'id':materialName}

    elementDict['children'] = []
    elementDict['children'].append( { 'type':'string', 
        'attributes':{ 'name':'variant', 'value':str(variant) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'alphaU', 'value':str(alphaUV[0][0]) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'alphaV', 'value':str(alphaUV[0][1]) } } )
    elementDict['children'].append( { 'type':'srgb', 
        'attributes':{ 'name':'specularReflectance', 'value':str(specularReflectance[0][0]) + " " + str(specularReflectance[0][1]) + " " + str(specularReflectance[0][2]) } } )
    elementDict['children'].append( { 'type':'srgb', 
        'attributes':{ 'name':'diffuseReflectance', 'value':str(diffuseReflectance[0][0]) + " " + str(diffuseReflectance[0][1]) + " " + str(diffuseReflectance[0][2]) } } )

    return elementDict

def writeShaderIrawan(material, materialName):
    filename = cmds.getAttr(material+".filename", asString=True)
    repeatu = cmds.getAttr(material+".repeatu")
    repeatv = cmds.getAttr(material+".repeatv")
    warpkd = cmds.getAttr(material+".warpkd")
    warpks = cmds.getAttr(material+".warpks")
    weftkd = cmds.getAttr(material+".weftkd")
    weftks = cmds.getAttr(material+".weftks")

    # Create a structure to be written
    elementDict = {'type':'bsdf'}
    elementDict['attributes'] = {'type':'irawan', 'id':materialName}

    elementDict['children'] = []
    elementDict['children'].append( { 'type':'string', 
        'attributes':{ 'name':'filename', 'value':filename } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'repeatU', 'value':str(repeatu) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'repeatV', 'value':str(repeatv) } } )
    elementDict['children'].append( { 'type':'rgb', 
        'attributes':{ 'name':'warp_kd', 'value':str(warpkd[0][0]) + " " + str(warpkd[0][1]) + " " + str(warpkd[0][2]) } } )
    elementDict['children'].append( { 'type':'rgb', 
        'attributes':{ 'name':'warp_ks', 'value':str(warpks[0][0]) + " " + str(warpks[0][1]) + " " + str(warpks[0][2]) } } )
    elementDict['children'].append( { 'type':'rgb', 
        'attributes':{ 'name':'weft_kd', 'value':str(weftkd[0][0]) + " " + str(weftkd[0][1]) + " " + str(weftkd[0][2]) } } )
    elementDict['children'].append( { 'type':'rgb', 
        'attributes':{ 'name':'weft_ks', 'value':str(weftks[0][0]) + " " + str(weftks[0][1]) + " " + str(weftks[0][2]) } } )

    return elementDict


def writeShaderObjectAreaLight(material, materialName):
    color = cmds.getAttr(material+".radiance")
    samplingWeight = cmds.getAttr(material+".samplingWeight")

    # Create a structure to be written
    elementDict = {'type':'emitter'}
    elementDict['attributes'] = {'type':'area', 'id':materialName}

    elementDict['children'] = []
    elementDict['children'].append( { 'type':'rgb', 
        'attributes':{ 'name':'radiance', 'value':str(color[0][0]) + " " + str(color[0][1]) + " " + str(color[0][2]) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'samplingWeight', 'value':str(samplingWeight) } } )

    return elementDict

def writeShaderTwoSided(material, materialName):
    # Create a structure to be written
    elementDict = {'type':'bsdf'}
    elementDict['attributes'] = {'type':'twosided', 'id':materialName}

    elementDict['children'] = []

    #Nested bsdf
    connections = cmds.listConnections(material, connections=True)
    for i in range(len(connections)):
        if i%2==1:
            connection = connections[i]
            connectionType = cmds.nodeType(connection)
            if connectionType in materialNodeTypes and connections[i-1]==material+".bsdf":
                #We've found the nested bsdf, so write it
                childElement = writeShader(connection, connection)

                elementDict['children'].append( { 'type':'ref', 
                    'attributes':{ 'id':childElement['attributes']['id'] } } )

    return elementDict


'''
Write a surface material (material) to a Mitsuba scene file (outFile)
tabbedSpace is a string of blank space to account for recursive xml
'''
def writeShader(material, materialName):
    matType = cmds.nodeType(material)
    
    mayaMaterialTypeToShaderFunction = {
        "MitsubaSmoothCoatingShader" : writeShaderSmoothCoating,
        "MitsubaConductorShader" : writeShaderConductor,
        "MitsubaDielectricShader" : writeShaderDielectric,
        "MitsubaDiffuseTransmitterShader" : writeShaderDiffuseTransmitter,
        "MitsubaDiffuseShader" : writeShaderDiffuse,
        "writeShaderPhong" : writeShaderPhong,
        "MitsubaPlasticShader" : writeShaderPlastic,
        "MitsubaRoughCoatingShader" : writeShaderRoughCoating,
        "MitsubaRoughConductorShader" : writeShaderRoughConductor,
        "MitsubaRoughDielectricShader" : writeShaderRoughDielectric,
        "MitsubaRoughDiffuseShader" : writeShaderRoughDiffuse,
        "MitsubaRoughPlasticShader" : writeShaderRoughPlastic,
        "MitsubaThinDielectricShader" : writeShaderThinDielectric,
        "MitsubaWardShader" : writeShaderWard,
        "MitsubaIrawanShader" : writeShaderIrawan,
        "MitsubaObjectAreaLightShader" : writeShaderObjectAreaLight,
        "MitsubaTwoSidedShader" : writeShaderTwoSided,
    }

    # Need to support : MitsubaBumpShader, MitsubaMaskShader, MitsubaMixtureShader

    if matType in mayaMaterialTypeToShaderFunction:
        writeShaderFunction = mayaMaterialTypeToShaderFunction[matType]
    else:
        print( "Skipping unsupported material : %s." % matType)
        writeShaderFunction = None

    shaderElement = None
    if writeShaderFunction:
        shaderElement = writeShaderFunction(material, materialName)

    return shaderElement

'''
Write the appropriate integrator
'''
def writeIntegratorPathTracer(renderSettings, integratorMitsuba):
    attrPrefixes = { 
        "path" : "", 
        "volpath" : "Volumetric", 
        "volpath_simple" : "SimpleVolumetric"
    }
    attrPrefix = attrPrefixes[integratorMitsuba]

    # Get values from the scene
    iPathTracerUseInfiniteDepth = cmds.getAttr("%s.%s" % (renderSettings, "i%sPathTracerUseInfiniteDepth" % attrPrefix))
    iPathTracerMaxDepth = cmds.getAttr("%s.%s" % (renderSettings, "i%sPathTracerMaxDepth" % attrPrefix))
    iPathTracerRRDepth = cmds.getAttr("%s.%s" % (renderSettings, "i%sPathTracerRRDepth" % attrPrefix))
    iPathTracerStrictNormals = cmds.getAttr("%s.%s" % (renderSettings, "i%sPathTracerStrictNormals" % attrPrefix))
    iPathTracerHideEmitters = cmds.getAttr("%s.%s" % (renderSettings, "i%sPathTracerHideEmitters" % attrPrefix))

    iPathTracerMaxDepth = -1 if iPathTracerUseInfiniteDepth else iPathTracerMaxDepth
    iPathTracerStrictNormalsText = 'true' if iPathTracerStrictNormals else 'false'
    iPathTracerHideEmittersText = 'true' if iPathTracerHideEmitters else 'false'

    # Create a structure to be written
    elementDict = {'type':'integrator'}
    elementDict['attributes'] = {'type':integratorMitsuba}

    elementDict['children'] = []
    elementDict['children'].append( { 'type':'integer', 
        'attributes':{ 'name':'maxDepth', 'value':str(iPathTracerMaxDepth) } } )
    elementDict['children'].append( { 'type':'integer', 
        'attributes':{ 'name':'rrDepth', 'value':str(iPathTracerRRDepth) } } )
    elementDict['children'].append( { 'type':'boolean', 
        'attributes':{ 'name':'strictNormals', 'value':iPathTracerStrictNormalsText } } )
    elementDict['children'].append( { 'type':'boolean', 
        'attributes':{ 'name':'hideEmitters', 'value':iPathTracerHideEmittersText } } )

    return elementDict

def writeIntegratorBidirectionalPathTracer(renderSettings, integratorMitsuba):
    # Get values from the scene
    iBidrectionalPathTracerUseInfiniteDepth = cmds.getAttr("%s.%s" % (renderSettings, "iBidrectionalPathTracerUseInfiniteDepth"))
    iBidrectionalPathTracerMaxDepth = cmds.getAttr("%s.%s" % (renderSettings, "iBidrectionalPathTracerMaxDepth"))
    iBidrectionalPathTracerRRDepth = cmds.getAttr("%s.%s" % (renderSettings, "iBidrectionalPathTracerRRDepth"))
    iBidrectionalPathTracerLightImage = cmds.getAttr("%s.%s" % (renderSettings, "iBidrectionalPathTracerLightImage"))
    iBidrectionalPathTracerSampleDirect = cmds.getAttr("%s.%s" % (renderSettings, "iBidrectionalPathTracerSampleDirect"))

    iBidrectionalPathTracerMaxDepth = -1 if iBidrectionalPathTracerUseInfiniteDepth else iBidrectionalPathTracerMaxDepth
    iBidrectionalPathTracerLightImageText = 'true' if iBidrectionalPathTracerLightImage else 'false'
    iBidrectionalPathTracerSampleDirectText = 'true' if iBidrectionalPathTracerSampleDirect else 'false'

    # Create a structure to be written
    elementDict = {'type':'integrator'}
    elementDict['attributes'] = {'type':integratorMitsuba}

    elementDict['children'] = []
    elementDict['children'].append( { 'type':'integer', 
        'attributes':{ 'name':'maxDepth', 'value':str(iBidrectionalPathTracerMaxDepth) } } )
    elementDict['children'].append( { 'type':'integer', 
        'attributes':{ 'name':'rrDepth', 'value':str(iBidrectionalPathTracerRRDepth) } } )
    elementDict['children'].append( { 'type':'boolean', 
        'attributes':{ 'name':'lightImage', 'value':iBidrectionalPathTracerLightImageText } } )
    elementDict['children'].append( { 'type':'boolean', 
        'attributes':{ 'name':'sampleDirect', 'value':iBidrectionalPathTracerSampleDirectText } } )

    return elementDict


def writeIntegratorAmbientOcclusion(renderSettings, integratorMitsuba):
    # Get values from the scene
    iAmbientOcclusionShadingSamples = cmds.getAttr("%s.%s" % (renderSettings, "iAmbientOcclusionShadingSamples"))
    iAmbientOcclusionUseAutomaticRayLength = cmds.getAttr("%s.%s" % (renderSettings, "iAmbientOcclusionUseAutomaticRayLength"))
    iAmbientOcclusionRayLength = cmds.getAttr("%s.%s" % (renderSettings, "iAmbientOcclusionRayLength"))

    iAmbientOcclusionRayLength = -1 if iAmbientOcclusionUseAutomaticRayLength else iAmbientOcclusionRayLength

    # Create a structure to be written
    elementDict = {'type':'integrator'}
    elementDict['attributes'] = {'type':integratorMitsuba}

    elementDict['children'] = []
    elementDict['children'].append( { 'type':'integer', 
        'attributes':{ 'name':'shadingSamples', 'value':str(iAmbientOcclusionShadingSamples) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'rayLength', 'value':str(iAmbientOcclusionRayLength) } } )

    return elementDict


def writeIntegratorDirectIllumination(renderSettings, integratorMitsuba):
    # Get values from the scene
    iDirectIlluminationShadingSamples = cmds.getAttr("%s.%s" % (renderSettings, "iDirectIlluminationShadingSamples"))
    iDirectIlluminationUseEmitterAndBSDFSamples = cmds.getAttr("%s.%s" % (renderSettings, "iDirectIlluminationUseEmitterAndBSDFSamples"))
    iDirectIlluminationEmitterSamples = cmds.getAttr("%s.%s" % (renderSettings, "iDirectIlluminationEmitterSamples"))
    iDirectIlluminationBSDFSamples = cmds.getAttr("%s.%s" % (renderSettings, "iDirectIlluminationBSDFSamples"))
    iDirectIlluminationStrictNormals = cmds.getAttr("%s.%s" % (renderSettings, "iDirectIlluminationStrictNormals"))
    iDirectIlluminationHideEmitters = cmds.getAttr("%s.%s" % (renderSettings, "iDirectIlluminationHideEmitters"))

    iDirectIlluminationStrictNormalsText = 'true' if iDirectIlluminationStrictNormals else 'false'
    iDirectIlluminationHideEmittersText = 'true' if iDirectIlluminationHideEmitters else 'false'

    # Create a structure to be written
    elementDict = {'type':'integrator'}
    elementDict['attributes'] = {'type':integratorMitsuba}

    elementDict['children'] = []
    if iDirectIlluminationUseEmitterAndBSDFSamples:
        elementDict['children'].append( { 'type':'integer', 
            'attributes':{ 'name':'emitterSamples', 'value':str(iDirectIlluminationEmitterSamples) } } )
        elementDict['children'].append( { 'type':'integer', 
            'attributes':{ 'name':'bsdfSamples', 'value':str(iDirectIlluminationBSDFSamples) } } )
    else:
        elementDict['children'].append( { 'type':'integer', 
            'attributes':{ 'name':'shadingSamples', 'value':str(iDirectIlluminationShadingSamples) } } )

    elementDict['children'].append( { 'type':'boolean', 
        'attributes':{ 'name':'strictNormals', 'value':str(iDirectIlluminationStrictNormalsText) } } )
    elementDict['children'].append( { 'type':'boolean', 
        'attributes':{ 'name':'hideEmitters', 'value':str(iDirectIlluminationHideEmittersText) } } )

    return elementDict


def writeIntegratorPhotonMap(renderSettings, integratorMitsuba):
    # Get values from the scene
    iPhotonMapDirectSamples = cmds.getAttr("%s.%s" % (renderSettings, "iPhotonMapDirectSamples"))
    iPhotonMapGlossySamples = cmds.getAttr("%s.%s" % (renderSettings, "iPhotonMapGlossySamples"))
    iPhotonMapUseInfiniteDepth = cmds.getAttr("%s.%s" % (renderSettings, "iPhotonMapUseInfiniteDepth"))
    iPhotonMapMaxDepth = cmds.getAttr("%s.%s" % (renderSettings, "iPhotonMapMaxDepth"))
    iPhotonMapGlobalPhotons = cmds.getAttr("%s.%s" % (renderSettings, "iPhotonMapGlobalPhotons"))
    iPhotonMapCausticPhotons = cmds.getAttr("%s.%s" % (renderSettings, "iPhotonMapCausticPhotons"))
    iPhotonMapVolumePhotons = cmds.getAttr("%s.%s" % (renderSettings, "iPhotonMapVolumePhotons"))
    iPhotonMapGlobalLookupRadius = cmds.getAttr("%s.%s" % (renderSettings, "iPhotonMapGlobalLookupRadius"))
    iPhotonMapCausticLookupRadius = cmds.getAttr("%s.%s" % (renderSettings, "iPhotonMapCausticLookupRadius"))
    iPhotonMapLookupSize = cmds.getAttr("%s.%s" % (renderSettings, "iPhotonMapLookupSize"))
    iPhotonMapGranularity = cmds.getAttr("%s.%s" % (renderSettings, "iPhotonMapGranularity"))
    iPhotonMapHideEmitters = cmds.getAttr("%s.%s" % (renderSettings, "iPhotonMapHideEmitters"))
    iPhotonMapRRDepth = cmds.getAttr("%s.%s" % (renderSettings, "iPhotonMapRRDepth"))

    iPhotonMapMaxDepth = -1 if iPhotonMapUseInfiniteDepth else iPhotonMapMaxDepth
    iPhotonMapHideEmittersText = "true" if iPhotonMapHideEmitters else "false"

    # Create a structure to be written
    elementDict = {'type':'integrator'}
    elementDict['attributes'] = {'type':integratorMitsuba}

    elementDict['children'] = []

    elementDict['children'].append( { 'type':'integer', 
        'attributes':{ 'name':'directSamples', 'value':str(iPhotonMapDirectSamples) } } )
    elementDict['children'].append( { 'type':'integer', 
        'attributes':{ 'name':'glossySamples', 'value':str(iPhotonMapGlossySamples) } } )

    elementDict['children'].append( { 'type':'integer', 
        'attributes':{ 'name':'maxDepth', 'value':str(iPhotonMapMaxDepth) } } )

    elementDict['children'].append( { 'type':'integer', 
        'attributes':{ 'name':'globalPhotons', 'value':str(iPhotonMapGlobalPhotons) } } )
    elementDict['children'].append( { 'type':'integer', 
        'attributes':{ 'name':'causticPhotons', 'value':str(iPhotonMapCausticPhotons) } } )
    elementDict['children'].append( { 'type':'integer', 
        'attributes':{ 'name':'volumePhotons', 'value':str(iPhotonMapVolumePhotons) } } )

    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'globalLookupRadius', 'value':str(iPhotonMapGlobalLookupRadius) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'causticLookupRadius', 'value':str(iPhotonMapCausticLookupRadius) } } )

    elementDict['children'].append( { 'type':'integer', 
        'attributes':{ 'name':'lookupSize', 'value':str(iPhotonMapLookupSize) } } )
    elementDict['children'].append( { 'type':'integer', 
        'attributes':{ 'name':'granularity', 'value':str(iPhotonMapGranularity) } } )

    elementDict['children'].append( { 'type':'boolean', 
        'attributes':{ 'name':'hideEmitters', 'value':str(iPhotonMapHideEmittersText) } } )
    elementDict['children'].append( { 'type':'integer', 
        'attributes':{ 'name':'rrDepth', 'value':str(iPhotonMapRRDepth) } } )

    return elementDict


def writeIntegratorProgressivePhotonMap(renderSettings, integratorMitsuba):
    # Get values from the scene
    attrPrefixes = { 
        "ppm" : "", 
        "sppm" : "Stochastic", 
    }
    attrPrefix = attrPrefixes[integratorMitsuba]

    iProgressivePhotonMapUseInfiniteDepth = cmds.getAttr("%s.%s" % (renderSettings, "i%sProgressivePhotonMapUseInfiniteDepth" % attrPrefix))
    iProgressivePhotonMapMaxDepth = cmds.getAttr("%s.%s" % (renderSettings, "i%sProgressivePhotonMapMaxDepth" % attrPrefix))
    iProgressivePhotonMapPhotonCount = cmds.getAttr("%s.%s" % (renderSettings, "i%sProgressivePhotonMapPhotonCount" % attrPrefix))
    iProgressivePhotonMapInitialRadius = cmds.getAttr("%s.%s" % (renderSettings, "i%sProgressivePhotonMapInitialRadius" % attrPrefix))
    iProgressivePhotonMapAlpha = cmds.getAttr("%s.%s" % (renderSettings, "i%sProgressivePhotonMapAlpha" % attrPrefix))
    iProgressivePhotonMapGranularity = cmds.getAttr("%s.%s" % (renderSettings, "i%sProgressivePhotonMapGranularity" % attrPrefix))
    iProgressivePhotonMapRRDepth = cmds.getAttr("%s.%s" % (renderSettings, "i%sProgressivePhotonMapRRDepth" % attrPrefix))
    iProgressivePhotonMapMaxPasses = cmds.getAttr("%s.%s" % (renderSettings, "i%sProgressivePhotonMapMaxPasses" % attrPrefix))

    iProgressivePhotonMapMaxDepth = -1 if iProgressivePhotonMapUseInfiniteDepth else iProgressivePhotonMapMaxDepth

    # Create a structure to be written
    elementDict = {'type':'integrator'}
    elementDict['attributes'] = {'type':integratorMitsuba}

    elementDict['children'] = []

    elementDict['children'].append( { 'type':'integer', 
        'attributes':{ 'name':'maxDepth', 'value':str(iProgressivePhotonMapMaxDepth) } } )
    elementDict['children'].append( { 'type':'integer', 
        'attributes':{ 'name':'photonCount', 'value':str(iProgressivePhotonMapPhotonCount) } } )

    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'initialRadius', 'value':str(iProgressivePhotonMapInitialRadius) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'alpha', 'value':str(iProgressivePhotonMapAlpha) } } )

    elementDict['children'].append( { 'type':'integer', 
        'attributes':{ 'name':'granularity', 'value':str(iProgressivePhotonMapGranularity) } } )
    elementDict['children'].append( { 'type':'integer', 
        'attributes':{ 'name':'rrDepth', 'value':str(iProgressivePhotonMapRRDepth) } } )
    elementDict['children'].append( { 'type':'integer', 
        'attributes':{ 'name':'maxPasses', 'value':str(iProgressivePhotonMapMaxPasses) } } )

    return elementDict


def writeIntegratorPrimarySampleSpaceMetropolisLightTransport(renderSettings, integratorMitsuba):
    # Get values from the scene
    iPrimarySampleSpaceMetropolisLightTransportBidirectional = cmds.getAttr("%s.%s" % (renderSettings, "iPrimarySampleSpaceMetropolisLightTransportBidirectional"))
    iPrimarySampleSpaceMetropolisLightTransportUseInfiniteDepth = cmds.getAttr("%s.%s" % (renderSettings, "iPrimarySampleSpaceMetropolisLightTransportUseInfiniteDepth"))
    iPrimarySampleSpaceMetropolisLightTransportMaxDepth = cmds.getAttr("%s.%s" % (renderSettings, "iPrimarySampleSpaceMetropolisLightTransportMaxDepth"))
    iPrimarySampleSpaceMetropolisLightTransportDirectSamples = cmds.getAttr("%s.%s" % (renderSettings, "iPrimarySampleSpaceMetropolisLightTransportDirectSamples"))
    iPrimarySampleSpaceMetropolisLightTransportRRDepth = cmds.getAttr("%s.%s" % (renderSettings, "iPrimarySampleSpaceMetropolisLightTransportRRDepth"))
    iPrimarySampleSpaceMetropolisLightTransportLuminanceSamples = cmds.getAttr("%s.%s" % (renderSettings, "iPrimarySampleSpaceMetropolisLightTransportLuminanceSamples"))
    iPrimarySampleSpaceMetropolisLightTransportTwoStage = cmds.getAttr("%s.%s" % (renderSettings, "iPrimarySampleSpaceMetropolisLightTransportTwoStage"))
    iPrimarySampleSpaceMetropolisLightTransportPLarge = cmds.getAttr("%s.%s" % (renderSettings, "iPrimarySampleSpaceMetropolisLightTransportPLarge"))

    iPrimarySampleSpaceMetropolisLightTransportMaxDepth = -1 if iPrimarySampleSpaceMetropolisLightTransportUseInfiniteDepth else iPrimarySampleSpaceMetropolisLightTransportMaxDepth
    iPrimarySampleSpaceMetropolisLightTransportBidirectionalText = 'true' if iPrimarySampleSpaceMetropolisLightTransportBidirectional else 'false'
    iPrimarySampleSpaceMetropolisLightTransportTwoStageText = 'true' if iPrimarySampleSpaceMetropolisLightTransportTwoStage else 'false'

    # Create a structure to be written
    elementDict = {'type':'integrator'}
    elementDict['attributes'] = {'type':integratorMitsuba}

    elementDict['children'] = []

    elementDict['children'].append( { 'type':'boolean', 
        'attributes':{ 'name':'bidirectional', 'value':str(iPrimarySampleSpaceMetropolisLightTransportBidirectionalText) } } )
    elementDict['children'].append( { 'type':'integer', 
        'attributes':{ 'name':'maxDepth', 'value':str(iPrimarySampleSpaceMetropolisLightTransportMaxDepth) } } )
    elementDict['children'].append( { 'type':'integer', 
        'attributes':{ 'name':'directSamples', 'value':str(iPrimarySampleSpaceMetropolisLightTransportDirectSamples) } } )
    elementDict['children'].append( { 'type':'integer', 
        'attributes':{ 'name':'rrDepth', 'value':str(iPrimarySampleSpaceMetropolisLightTransportRRDepth) } } )
    elementDict['children'].append( { 'type':'integer', 
        'attributes':{ 'name':'luminanceSamples', 'value':str(iPrimarySampleSpaceMetropolisLightTransportLuminanceSamples) } } )
    elementDict['children'].append( { 'type':'boolean', 
        'attributes':{ 'name':'twoStage', 'value':str(iPrimarySampleSpaceMetropolisLightTransportTwoStageText) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'pLarge', 'value':str(iPrimarySampleSpaceMetropolisLightTransportPLarge) } } )

    return elementDict


def writeIntegratorPathSpaceMetropolisLightTransport(renderSettings, integratorMitsuba):
    # Get values from the scene
    iPathSpaceMetropolisLightTransportUseInfiniteDepth = cmds.getAttr("%s.%s" % (renderSettings, "iPathSpaceMetropolisLightTransportUseInfiniteDepth"))
    iPathSpaceMetropolisLightTransportMaxDepth = cmds.getAttr("%s.%s" % (renderSettings, "iPathSpaceMetropolisLightTransportMaxDepth"))
    iPathSpaceMetropolisLightTransportDirectSamples = cmds.getAttr("%s.%s" % (renderSettings, "iPathSpaceMetropolisLightTransportDirectSamples"))
    iPathSpaceMetropolisLightTransportLuminanceSamples = cmds.getAttr("%s.%s" % (renderSettings, "iPathSpaceMetropolisLightTransportLuminanceSamples"))
    iPathSpaceMetropolisLightTransportTwoStage = cmds.getAttr("%s.%s" % (renderSettings, "iPathSpaceMetropolisLightTransportTwoStage"))
    iPathSpaceMetropolisLightTransportBidirectionalMutation = cmds.getAttr("%s.%s" % (renderSettings, "iPathSpaceMetropolisLightTransportBidirectionalMutation"))
    iPathSpaceMetropolisLightTransportLensPurturbation = cmds.getAttr("%s.%s" % (renderSettings, "iPathSpaceMetropolisLightTransportLensPurturbation"))
    iPathSpaceMetropolisLightTransportMultiChainPurturbation = cmds.getAttr("%s.%s" % (renderSettings, "iPathSpaceMetropolisLightTransportMultiChainPurturbation"))
    iPathSpaceMetropolisLightTransportCausticPurturbation = cmds.getAttr("%s.%s" % (renderSettings, "iPathSpaceMetropolisLightTransportCausticPurturbation"))
    iPathSpaceMetropolisLightTransportManifoldPurturbation = cmds.getAttr("%s.%s" % (renderSettings, "iPathSpaceMetropolisLightTransportManifoldPurturbation"))
    iPathSpaceMetropolisLightTransportLambda = cmds.getAttr("%s.%s" % (renderSettings, "iPathSpaceMetropolisLightTransportLambda"))

    iPathSpaceMetropolisLightTransportMaxDepth = -1 if iPathSpaceMetropolisLightTransportUseInfiniteDepth else iPathSpaceMetropolisLightTransportMaxDepth

    iPathSpaceMetropolisLightTransportTwoStageText = 'true' if iPathSpaceMetropolisLightTransportTwoStage else 'false'
    iPathSpaceMetropolisLightTransportBidirectionalMutationText = 'true' if iPathSpaceMetropolisLightTransportBidirectionalMutation else 'false'
    iPathSpaceMetropolisLightTransportLensPurturbationText = 'true' if iPathSpaceMetropolisLightTransportLensPurturbation else 'false'
    iPathSpaceMetropolisLightTransportMultiChainPurturbationText = 'true' if iPathSpaceMetropolisLightTransportMultiChainPurturbation else 'false'
    iPathSpaceMetropolisLightTransportCausticPurturbationText = 'true' if iPathSpaceMetropolisLightTransportCausticPurturbation else 'false'
    iPathSpaceMetropolisLightTransportManifoldPurturbationText = 'true' if iPathSpaceMetropolisLightTransportManifoldPurturbation else 'false'

    # Create a structure to be written
    elementDict = {'type':'integrator'}
    elementDict['attributes'] = {'type':integratorMitsuba}

    elementDict['children'] = []

    elementDict['children'].append( { 'type':'integer', 
        'attributes':{ 'name':'maxDepth', 'value':str(iPathSpaceMetropolisLightTransportMaxDepth) } } )
    elementDict['children'].append( { 'type':'integer', 
        'attributes':{ 'name':'directSamples', 'value':str(iPathSpaceMetropolisLightTransportDirectSamples) } } )
    elementDict['children'].append( { 'type':'integer', 
        'attributes':{ 'name':'luminanceSamples', 'value':str(iPathSpaceMetropolisLightTransportLuminanceSamples) } } )
    elementDict['children'].append( { 'type':'boolean', 
        'attributes':{ 'name':'twoStage', 'value':str(iPathSpaceMetropolisLightTransportTwoStageText) } } )
    elementDict['children'].append( { 'type':'boolean', 
        'attributes':{ 'name':'bidirectionalMutation', 'value':str(iPathSpaceMetropolisLightTransportBidirectionalMutationText) } } )
    elementDict['children'].append( { 'type':'boolean', 
        'attributes':{ 'name':'lensPerturbation', 'value':str(iPathSpaceMetropolisLightTransportLensPurturbationText) } } )
    elementDict['children'].append( { 'type':'boolean', 
        'attributes':{ 'name':'multiChainPerturbation', 'value':str(iPathSpaceMetropolisLightTransportMultiChainPurturbationText) } } )
    elementDict['children'].append( { 'type':'boolean', 
        'attributes':{ 'name':'causticPerturbation', 'value':str(iPathSpaceMetropolisLightTransportCausticPurturbationText) } } )
    elementDict['children'].append( { 'type':'boolean', 
        'attributes':{ 'name':'manifoldPerturbation', 'value':str(iPathSpaceMetropolisLightTransportManifoldPurturbationText) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'lambda', 'value':str(iPathSpaceMetropolisLightTransportLambda) } } )

    return elementDict


def writeIntegratorEnergyRedistributionPathTracing(renderSettings, integratorMitsuba):
    # Get values from the scene
    iEnergyRedistributionPathTracingUseInfiniteDepth = cmds.getAttr("%s.%s" % (renderSettings, "iEnergyRedistributionPathTracingUseInfiniteDepth"))
    iEnergyRedistributionPathTracingMaxDepth = cmds.getAttr("%s.%s" % (renderSettings, "iEnergyRedistributionPathTracingMaxDepth"))
    iEnergyRedistributionPathTracingNumChains = cmds.getAttr("%s.%s" % (renderSettings, "iEnergyRedistributionPathTracingNumChains"))
    iEnergyRedistributionPathTracingMaxChains = cmds.getAttr("%s.%s" % (renderSettings, "iEnergyRedistributionPathTracingMaxChains"))
    iEnergyRedistributionPathTracingChainLength = cmds.getAttr("%s.%s" % (renderSettings, "iEnergyRedistributionPathTracingChainLength"))
    iEnergyRedistributionPathTracingDirectSamples = cmds.getAttr("%s.%s" % (renderSettings, "iEnergyRedistributionPathTracingDirectSamples"))
    iEnergyRedistributionPathTracingLensPerturbation = cmds.getAttr("%s.%s" % (renderSettings, "iEnergyRedistributionPathTracingLensPerturbation"))
    iEnergyRedistributionPathTracingMultiChainPerturbation = cmds.getAttr("%s.%s" % (renderSettings, "iEnergyRedistributionPathTracingMultiChainPerturbation"))
    iEnergyRedistributionPathTracingCausticPerturbation = cmds.getAttr("%s.%s" % (renderSettings, "iEnergyRedistributionPathTracingCausticPerturbation"))
    iEnergyRedistributionPathTracingManifoldPerturbation = cmds.getAttr("%s.%s" % (renderSettings, "iEnergyRedistributionPathTracingManifoldPerturbation"))
    iEnergyRedistributionPathTracingLambda = cmds.getAttr("%s.%s" % (renderSettings, "iEnergyRedistributionPathTracingLambda"))

    iEnergyRedistributionPathTracingMaxDepth = -1 if iEnergyRedistributionPathTracingUseInfiniteDepth else iEnergyRedistributionPathTracingMaxDepth

    iEnergyRedistributionPathTracingLensPerturbationText = 'true' if iEnergyRedistributionPathTracingLensPerturbation else 'false'
    iEnergyRedistributionPathTracingMultiChainPerturbationText = 'true' if iEnergyRedistributionPathTracingMultiChainPerturbation else 'false'
    iEnergyRedistributionPathTracingCausticPerturbationText = 'true' if iEnergyRedistributionPathTracingCausticPerturbation else 'false'
    iEnergyRedistributionPathTracingManifoldPerturbationText = 'true' if iEnergyRedistributionPathTracingManifoldPerturbation else 'false'

    # Create a structure to be written
    elementDict = {'type':'integrator'}
    elementDict['attributes'] = {'type':integratorMitsuba}

    elementDict['children'] = []

    elementDict['children'].append( { 'type':'integer', 
        'attributes':{ 'name':'maxDepth', 'value':str(iEnergyRedistributionPathTracingMaxDepth) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'numChains', 'value':str(iEnergyRedistributionPathTracingNumChains) } } )
    elementDict['children'].append( { 'type':'integer', 
        'attributes':{ 'name':'maxChains', 'value':str(iEnergyRedistributionPathTracingMaxChains) } } )
    elementDict['children'].append( { 'type':'integer', 
        'attributes':{ 'name':'directSamples', 'value':str(iEnergyRedistributionPathTracingDirectSamples) } } )
    elementDict['children'].append( { 'type':'integer', 
        'attributes':{ 'name':'chainLength', 'value':str(iEnergyRedistributionPathTracingChainLength) } } )
    elementDict['children'].append( { 'type':'boolean', 
        'attributes':{ 'name':'lensPerturbation', 'value':str(iEnergyRedistributionPathTracingLensPerturbationText) } } )
    elementDict['children'].append( { 'type':'boolean', 
        'attributes':{ 'name':'multiChainPerturbation', 'value':str(iEnergyRedistributionPathTracingMultiChainPerturbationText) } } )
    elementDict['children'].append( { 'type':'boolean', 
        'attributes':{ 'name':'causticPerturbation', 'value':str(iEnergyRedistributionPathTracingCausticPerturbationText) } } )
    elementDict['children'].append( { 'type':'boolean', 
        'attributes':{ 'name':'manifoldPerturbation', 'value':str(iEnergyRedistributionPathTracingManifoldPerturbationText) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'lambda', 'value':str(iEnergyRedistributionPathTracingLambda) } } )

    return elementDict

def writeIntegratorAdjointParticleTracer(renderSettings, integratorMitsuba):
    # Get values from the scene
    iAdjointParticleTracerUseInfiniteDepth = cmds.getAttr("%s.%s" % (renderSettings, "iAdjointParticleTracerUseInfiniteDepth"))
    iAdjointParticleTracerMaxDepth = cmds.getAttr("%s.%s" % (renderSettings, "iAdjointParticleTracerMaxDepth"))
    iAdjointParticleTracerRRDepth = cmds.getAttr("%s.%s" % (renderSettings, "iAdjointParticleTracerRRDepth"))
    iAdjointParticleTracerGranularity = cmds.getAttr("%s.%s" % (renderSettings, "iAdjointParticleTracerGranularity"))
    iAdjointParticleTracerBruteForce = cmds.getAttr("%s.%s" % (renderSettings, "iAdjointParticleTracerBruteForce"))

    iAdjointParticleTracerMaxDepth = -1 if iAdjointParticleTracerUseInfiniteDepth else iAdjointParticleTracerMaxDepth
    iAdjointParticleTracerBruteForceText = 'true' if iAdjointParticleTracerBruteForce else 'false'

    # Create a structure to be written
    elementDict = {'type':'integrator'}
    elementDict['attributes'] = {'type':integratorMitsuba}

    elementDict['children'] = []

    elementDict['children'].append( { 'type':'integer', 
        'attributes':{ 'name':'maxDepth', 'value':str(iAdjointParticleTracerMaxDepth) } } )
    elementDict['children'].append( { 'type':'integer', 
        'attributes':{ 'name':'rrDepth', 'value':str(iAdjointParticleTracerRRDepth) } } )
    elementDict['children'].append( { 'type':'integer', 
        'attributes':{ 'name':'granularity', 'value':str(iAdjointParticleTracerGranularity) } } )
    elementDict['children'].append( { 'type':'boolean', 
        'attributes':{ 'name':'bruteForce', 'value':str(iAdjointParticleTracerBruteForceText) } } )

    return elementDict

def writeIntegratorVirtualPointLight(renderSettings, integratorMitsuba):
    # Get values from the scene
    iVirtualPointLightUseInfiniteDepth = cmds.getAttr("%s.%s" % (renderSettings, "iVirtualPointLightUseInfiniteDepth"))
    iVirtualPointLightMaxDepth = cmds.getAttr("%s.%s" % (renderSettings, "iVirtualPointLightMaxDepth"))
    iVirtualPointLightShadowMapResolution = cmds.getAttr("%s.%s" % (renderSettings, "iVirtualPointLightShadowMapResolution"))
    iVirtualPointLightClamping = cmds.getAttr("%s.%s" % (renderSettings, "iVirtualPointLightClamping"))

    iVirtualPointLightMaxDepth = -1 if iVirtualPointLightUseInfiniteDepth else iVirtualPointLightMaxDepth

    # Create a structure to be written
    elementDict = {'type':'integrator'}
    elementDict['attributes'] = {'type':integratorMitsuba}

    elementDict['children'] = []

    elementDict['children'].append( { 'type':'integer', 
        'attributes':{ 'name':'maxDepth', 'value':str(iVirtualPointLightMaxDepth) } } )
    elementDict['children'].append( { 'type':'integer', 
        'attributes':{ 'name':'shadowMapResolution', 'value':str(iVirtualPointLightShadowMapResolution) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'clamping', 'value':str(iVirtualPointLightClamping) } } )

    return elementDict


def writeIntegratorAdaptive(renderSettings, integratorMitsuba, subIntegrator):
    miAdaptiveMaxError = cmds.getAttr("%s.%s" % (renderSettings, "miAdaptiveMaxError"))
    miAdaptivePValue = cmds.getAttr("%s.%s" % (renderSettings, "miAdaptivePValue"))
    miAdaptiveMaxSampleFactor = cmds.getAttr("%s.%s" % (renderSettings, "miAdaptiveMaxSampleFactor"))

    # Create a structure to be written
    elementDict = {'type':'integrator'}
    elementDict['attributes'] = {'type':integratorMitsuba}

    elementDict['children'] = []

    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'maxError', 'value':str(miAdaptiveMaxError/100.0) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'pValue', 'value':str(miAdaptivePValue/100.0) } } )
    elementDict['children'].append( { 'type':'integer', 
        'attributes':{ 'name':'maxSampleFactor', 'value':str(miAdaptiveMaxSampleFactor) } } )

    elementDict['children'].append( subIntegrator )

    return elementDict

def writeIntegratorIrradianceCache(renderSettings, integratorMitsuba, subIntegrator):
    miIrradianceCacheResolution = cmds.getAttr("%s.%s" % (renderSettings, "miIrradianceCacheResolution"))
    miIrradianceCacheQuality = cmds.getAttr("%s.%s" % (renderSettings, "miIrradianceCacheQuality"))
    miIrradianceCacheGradients = cmds.getAttr("%s.%s" % (renderSettings, "miIrradianceCacheGradients"))
    miIrradianceCacheClampNeighbor = cmds.getAttr("%s.%s" % (renderSettings, "miIrradianceCacheClampNeighbor"))
    miIrradianceCacheClampScreen = cmds.getAttr("%s.%s" % (renderSettings, "miIrradianceCacheClampScreen"))
    miIrradianceCacheOverture = cmds.getAttr("%s.%s" % (renderSettings, "miIrradianceCacheOverture"))
    miIrradianceCacheQualityAdjustment = cmds.getAttr("%s.%s" % (renderSettings, "miIrradianceCacheQualityAdjustment"))
    miIrradianceCacheIndirectOnly = cmds.getAttr("%s.%s" % (renderSettings, "miIrradianceCacheIndirectOnly"))
    miIrradianceCacheDebug = cmds.getAttr("%s.%s" % (renderSettings, "miIrradianceCacheDebug"))

    miIrradianceCacheGradientsText = "true" if miIrradianceCacheGradients else "false"
    miIrradianceCacheClampNeighborText = "true" if miIrradianceCacheClampNeighbor else "false"
    miIrradianceCacheClampScreenText = "true" if miIrradianceCacheClampScreen else "false"
    miIrradianceCacheOvertureText = "true" if miIrradianceCacheOverture else "false"
    miIrradianceCacheIndirectOnlyText = "true" if miIrradianceCacheIndirectOnly else "false"
    miIrradianceCacheDebug = "true" if miIrradianceCacheDebug else "false"

    # Create a structure to be written
    elementDict = {'type':'integrator'}
    elementDict['attributes'] = {'type':integratorMitsuba}

    elementDict['children'] = []

    elementDict['children'].append( { 'type':'integer', 
        'attributes':{ 'name':'resolution', 'value':str(miIrradianceCacheResolution) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'quality', 'value':str(miIrradianceCacheQuality) } } )
    elementDict['children'].append( { 'type':'boolean', 
        'attributes':{ 'name':'gradients', 'value':miIrradianceCacheGradientsText } } )
    elementDict['children'].append( { 'type':'boolean', 
        'attributes':{ 'name':'clampNeighbor', 'value':miIrradianceCacheClampNeighborText } } )
    elementDict['children'].append( { 'type':'boolean', 
        'attributes':{ 'name':'clampScreen', 'value':miIrradianceCacheClampScreenText } } )
    elementDict['children'].append( { 'type':'boolean', 
        'attributes':{ 'name':'overture', 'value':miIrradianceCacheOvertureText } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'qualityAdjustment', 'value':str(miIrradianceCacheQualityAdjustment) } } )
    elementDict['children'].append( { 'type':'boolean', 
        'attributes':{ 'name':'indirectOnly', 'value':miIrradianceCacheIndirectOnlyText } } )
    elementDict['children'].append( { 'type':'boolean', 
        'attributes':{ 'name':'debug', 'value':miIrradianceCacheDebug } } )

    elementDict['children'].append( subIntegrator )

    return elementDict

def writeMetaIntegrator(renderSettings, metaIntegratorMaya, subIntegrator):
    mayaMetaIntegratorUINameToMitsubaName = {
        "Adaptive" : "adaptive",
        "Irradiance Cache" : "irrcache"
    }

    if metaIntegratorMaya in mayaMetaIntegratorUINameToMitsubaName:
        metaIntegratorMitsuba = mayaMetaIntegratorUINameToMitsubaName[metaIntegratorMaya]
    else:
        metaIntegratorMitsuba = None

    mayaMetaIntegratorUINameToIntegratorFunction = {
        "Adaptive" : writeIntegratorAdaptive,
        "Irradiance Cache" : writeIntegratorIrradianceCache
    }

    if metaIntegratorMitsuba:
        writeMetaIntegratorFunction = mayaMetaIntegratorUINameToIntegratorFunction[metaIntegratorMaya]
        integratorElement = writeMetaIntegratorFunction(renderSettings, metaIntegratorMitsuba, subIntegrator)
    else:
        integratorElement = subIntegrator

    return integratorElement

def writeIntegratorField(value):
    elementDict = {'type':'integrator'}
    elementDict['attributes'] = {'type':'field'}

    elementDict['children'] = []
    elementDict['children'].append( { 'type':'string', 
        'attributes':{ 'name':'field', 'value':value } } )

    return elementDict

def writeIntegratorMultichannel(renderSettings, subIntegrator):
    multichannelPosition = cmds.getAttr("%s.%s" % (renderSettings, "multichannelPosition"))
    multichannelRelPosition = cmds.getAttr("%s.%s" % (renderSettings, "multichannelRelPosition"))
    multichannelDistance = cmds.getAttr("%s.%s" % (renderSettings, "multichannelDistance"))
    multichannelGeoNormal = cmds.getAttr("%s.%s" % (renderSettings, "multichannelGeoNormal"))
    multichannelShadingNormal = cmds.getAttr("%s.%s" % (renderSettings, "multichannelShadingNormal"))
    multichannelUV = cmds.getAttr("%s.%s" % (renderSettings, "multichannelUV"))
    multichannelAlbedo = cmds.getAttr("%s.%s" % (renderSettings, "multichannelAlbedo"))
    multichannelShapeIndex = cmds.getAttr("%s.%s" % (renderSettings, "multichannelShapeIndex"))
    multichannelPrimIndex = cmds.getAttr("%s.%s" % (renderSettings, "multichannelPrimIndex"))

    # Create a structure to be written
    elementDict = {'type':'integrator'}
    elementDict['attributes'] = {'type':'multichannel'}

    elementDict['children'] = []
    elementDict['children'].append( subIntegrator )
    if multichannelPosition: elementDict['children'].append( writeIntegratorField("position") )
    if multichannelRelPosition: elementDict['children'].append( writeIntegratorField("relPosition") )
    if multichannelDistance: elementDict['children'].append( writeIntegratorField("distance") )
    if multichannelGeoNormal: elementDict['children'].append( writeIntegratorField("geoNormal") )
    if multichannelShadingNormal: elementDict['children'].append( writeIntegratorField("shNormal") )
    if multichannelUV: elementDict['children'].append( writeIntegratorField("uv") )
    if multichannelAlbedo: elementDict['children'].append( writeIntegratorField("albedo") )
    if multichannelShapeIndex: elementDict['children'].append( writeIntegratorField("shapeIndex") )
    if multichannelPrimIndex: elementDict['children'].append( writeIntegratorField("primIndex") )

    return elementDict

def writeIntegrator(renderSettings):
    # Create base integrator
    integratorMaya = cmds.getAttr("%s.%s" % (renderSettings, "integrator")).replace('_', ' ')

    mayaUINameToMitsubaName = {
        "Ambient Occlusion" : "ao",
        "Direct Illumination" : "direct",
        "Path Tracer" : "path",
        "Volumetric Path Tracer" : "volpath",
        "Simple Volumetric Path Tracer" : "volpath_simple",
        "Bidirectional Path Tracer" : "bdpt",
        "Photon Map" : "photonmapper",
        "Progressive Photon Map" : "ppm",
        "Stochastic Progressive Photon Map" : "sppm",
        "Primary Sample Space Metropolis Light Transport" : "pssmlt",
        "Path Space Metropolis Light Transport" : "mlt",
        "Energy Redistribution Path Tracer" : "erpt",
        "Adjoint Particle Tracer" : "ptracer",
        "Virtual Point Lights" : "vpl"
    }

    if integratorMaya in mayaUINameToMitsubaName:
        integratorMitsuba = mayaUINameToMitsubaName[integratorMaya]
    else:
        integratorMitsuba = "path"

    mayaUINameToIntegratorFunction = {
        "Ambient Occlusion" : writeIntegratorAmbientOcclusion,
        "Direct Illumination" : writeIntegratorDirectIllumination,
        "Path Tracer" : writeIntegratorPathTracer,
        "Volumetric Path Tracer" : writeIntegratorPathTracer,
        "Simple Volumetric Path Tracer" : writeIntegratorPathTracer,
        "Bidirectional Path Tracer" : writeIntegratorBidirectionalPathTracer,
        "Photon Map" : writeIntegratorPhotonMap,
        "Progressive Photon Map" : writeIntegratorProgressivePhotonMap,
        "Stochastic Progressive Photon Map" : writeIntegratorProgressivePhotonMap,
        "Primary Sample Space Metropolis Light Transport" : writeIntegratorPrimarySampleSpaceMetropolisLightTransport,
        "Path Space Metropolis Light Transport" : writeIntegratorPathSpaceMetropolisLightTransport,
        "Energy Redistribution Path Tracer" : writeIntegratorEnergyRedistributionPathTracing,
        "Adjoint Particle Tracer" : writeIntegratorAdjointParticleTracer,
        "Virtual Point Lights" : writeIntegratorVirtualPointLight
    }

    if integratorMaya in mayaUINameToIntegratorFunction:
        writeIntegratorFunction = mayaUINameToIntegratorFunction[integratorMaya]
    else:
        print( "Unsupported Integrator : %s. Using Path Tracer" % integratorMaya)
        writeIntegratorFunction = writeIntegratorPathTracer

    integratorElement = writeIntegratorFunction(renderSettings, integratorMitsuba)

    # Create meta integrator
    metaIntegratorMaya = cmds.getAttr("%s.%s" % (renderSettings, "metaIntegrator")).replace('_', ' ')
    if metaIntegratorMaya != "None":
        integratorElement = writeMetaIntegrator(renderSettings, metaIntegratorMaya, integratorElement)

    # Create multichannel integrator
    multichannel = cmds.getAttr("%s.%s" % (renderSettings, "multichannel"))

    if multichannel:
        integratorElement = writeIntegratorMultichannel(renderSettings, integratorElement)

    return integratorElement

'''
Write image sample generator
'''
def writeSampler(frameNumber, renderSettings):
    samplerMaya = cmds.getAttr("%s.%s" % (renderSettings, "sampler")).replace('_', ' ')
    sampleCount = cmds.getAttr("%s.%s" % (renderSettings, "sampleCount"))
    samplerDimension = cmds.getAttr("%s.%s" % (renderSettings, "samplerDimension"))
    samplerScramble = cmds.getAttr("%s.%s" % (renderSettings, "samplerScramble"))
    if samplerScramble == -1:
        samplerScramble = frameNumber

    mayaUINameToMitsubaName = {
        "Independent Sampler"  : "independent",
        "Stratified Sampler" : "stratified",
        "Low Discrepancy Sampler" : "ldsampler",
        "Halton QMC Sampler" : "halton",
        "Hammersley QMC Sampler" : "hammersley",
        "Sobol QMC Sampler" : "sobol"
    }

    if samplerMaya in mayaUINameToMitsubaName:
        samplerMitsuba = mayaUINameToMitsubaName[samplerMaya]
    else:
        samplerMitsuba = "independent"

    elementDict = {'type':'sampler'}
    elementDict['attributes'] = {'type':samplerMitsuba}

    elementDict['children'] = []
    elementDict['children'].append( { 'type':'integer', 'attributes':{ 'name':'sampleCount', 'value':str(sampleCount) } } )

    if( samplerMaya == "Stratified Sampler" or
        samplerMaya == "Low Discrepancy Sampler" ):
        elementDict['children'].append( { 'type':'integer', 'attributes':{ 'name':'dimension', 'value':str(samplerDimension) } } )

    elif( samplerMaya == "Halton QMC Sampler" or
        samplerMaya == "Hammersley QMC Sampler" or
        samplerMaya == "Sobol QMC Sampler" ):
        elementDict['children'].append( { 'type':'integer', 'attributes':{ 'name':'scramble', 'value':str(samplerScramble) } } )

    return elementDict

def filmAddMultichannelAttributes(renderSettings, elementDict):
    multichannelPosition = cmds.getAttr("%s.%s" % (renderSettings, "multichannelPosition"))
    multichannelRelPosition = cmds.getAttr("%s.%s" % (renderSettings, "multichannelRelPosition"))
    multichannelDistance = cmds.getAttr("%s.%s" % (renderSettings, "multichannelDistance"))
    multichannelGeoNormal = cmds.getAttr("%s.%s" % (renderSettings, "multichannelGeoNormal"))
    multichannelShadingNormal = cmds.getAttr("%s.%s" % (renderSettings, "multichannelShadingNormal"))
    multichannelUV = cmds.getAttr("%s.%s" % (renderSettings, "multichannelUV"))
    multichannelAlbedo = cmds.getAttr("%s.%s" % (renderSettings, "multichannelAlbedo"))
    multichannelShapeIndex = cmds.getAttr("%s.%s" % (renderSettings, "multichannelShapeIndex"))
    multichannelPrimIndex = cmds.getAttr("%s.%s" % (renderSettings, "multichannelPrimIndex"))

    pixelFormat = "rgba"
    channelNames = "rgba"

    if multichannelPosition:
        pixelFormat  += ", rgb"
        channelNames += ", position"
    if multichannelRelPosition:
        pixelFormat  += ", rgb"
        channelNames += ", relPosition"
    if multichannelDistance:
        pixelFormat  += ", luminance"
        channelNames += ", distance"
    if multichannelGeoNormal:
        pixelFormat  += ", rgb"
        channelNames += ", geoNormal"
    if multichannelShadingNormal:
        pixelFormat  += ", rgb"
        channelNames += ", shadingNormal"
    if multichannelUV:
        pixelFormat  += ", rgb"
        channelNames += ", uv"
    if multichannelAlbedo:
        pixelFormat  += ", rgb"
        channelNames += ", albedo"
    if multichannelShapeIndex:
        pixelFormat  += ", luminance"
        channelNames += ", shapeIndex"
    if multichannelPrimIndex:
        pixelFormat  += ", luminance"
        channelNames += ", primitiveIndex"

    pixelFormatChild = None
    for child in elementDict['children']:
        attributes = child['attributes']
        if 'name' in attributes and attributes['name'] == 'pixelFormat':
            pixelFormatChild = child
            break

    if pixelFormatChild:
        elementDict['children'].remove( pixelFormatChild )

    elementDict['children'].append( { 'type':'string', 'attributes':{ 'name':'pixelFormat', 'value':pixelFormat } } )
    elementDict['children'].append( { 'type':'string', 'attributes':{ 'name':'channelNames', 'value':channelNames } } )

    return elementDict

def writeReconstructionFilter(renderSettings):
    #Filter
    reconstructionFilterMaya = cmds.getAttr("%s.%s" % (renderSettings, "reconstructionFilter")).replace('_' ,' ')
    mayaUINameToMitsubaName = {
        "Box filter"  : "box",
        "Tent filter" : "tent",
        "Gaussian filter" : "gaussian",
        "Catmull-Rom filter" : "catmullrom",
        "Lanczos filter" : "lanczos",
        "Mitchell-Netravali filter" : "mitchell"
    }

    if reconstructionFilterMaya in mayaUINameToMitsubaName:
        reconstructionFilterMitsuba = mayaUINameToMitsubaName[reconstructionFilterMaya]
    else:
        reconstructionFilterMitsuba = "box"

    rfilterElement = { 'type':'rfilter', 'attributes':{ 'type':reconstructionFilterMitsuba } }

    return rfilterElement

def booleanToMisubaText(b):
    if b:
        return "true"
    else:
        return "false"

def writeFilmHDR(renderSettings, filmMitsuba):
    fHDRFilmFileFormat = cmds.getAttr("%s.%s" % (renderSettings, "fHDRFilmFileFormat"))
    fHDRFilmPixelFormat = cmds.getAttr("%s.%s" % (renderSettings, "fHDRFilmPixelFormat"))
    fHDRFilmComponentFormat = cmds.getAttr("%s.%s" % (renderSettings, "fHDRFilmComponentFormat"))
    fHDRFilmAttachLog = cmds.getAttr("%s.%s" % (renderSettings, "fHDRFilmAttachLog"))
    fHDRFilmBanner = cmds.getAttr("%s.%s" % (renderSettings, "fHDRFilmBanner"))
    fHDRFilmHighQualityEdges = cmds.getAttr("%s.%s" % (renderSettings, "fHDRFilmHighQualityEdges"))

    mayaFileFormatUINameToMitsubaName = {
        "OpenEXR (.exr)"  : "openexr",
        "RGBE (.hdr)" : "rgbe",
        "Portable Float Map (.pfm)"  : "pfm"
    }

    if fHDRFilmFileFormat in mayaFileFormatUINameToMitsubaName:
        fHDRFilmFileFormatMitsuba = mayaFileFormatUINameToMitsubaName[fHDRFilmFileFormat]
    else:
        print( "Unsupported file format : %s. Using OpenEXR (.exr)" % fHDRFilmFileFormat)
        fHDRFilmFileFormatMitsuba = "openexr"

    mayaPixelFormatUINameToMitsubaName = {
        'Luminance' : 'luminance',
        'Luminance Alpha' : 'luminanceAlpha',
        'RGB' : 'rgb',
        'RGBA' : 'rgba',
        'XYZ' : 'xyz',
        'XYZA' : 'xyza',
        'Spectrum' : 'spectrum',
        'Spectrum Alpha' : 'spectrumAlpha'
    }

    if fHDRFilmPixelFormat in mayaPixelFormatUINameToMitsubaName:
        fHDRFilmPixelFormatMitsuba = mayaPixelFormatUINameToMitsubaName[fHDRFilmPixelFormat]
    else:
        print( "Unsupported pixel format : %s. Using RGB" % fHDRFilmPixelFormat)
        fHDRFilmPixelFormatMitsuba = "rgb"

    mayaComponentFormatUINameToMitsubaName = {
        'Float 16' : 'float16',
        'Float 32' : 'float32',
        'UInt 32' : 'uint32',
    }

    if fHDRFilmComponentFormat in mayaComponentFormatUINameToMitsubaName:
        fHDRFilmComponentFormatMitsuba = mayaComponentFormatUINameToMitsubaName[fHDRFilmComponentFormat]
    else:
        print( "Unsupported component format : %s. Using Float 16" % fHDRFilmComponentFormat)
        fHDRFilmComponentFormatMitsuba = "float16"

    elementDict = {'type':'film'}
    elementDict['attributes'] = {'type':filmMitsuba}

    elementDict['children'] = []
    elementDict['children'].append( { 'type':'string', 
        'attributes':{ 'name':'fileFormat', 'value':fHDRFilmFileFormatMitsuba } } )
    if fHDRFilmFileFormatMitsuba == "openexr":
        elementDict['children'].append( { 'type':'string', 
            'attributes':{ 'name':'pixelFormat', 'value':fHDRFilmPixelFormatMitsuba } } )
    elementDict['children'].append( { 'type':'string', 
        'attributes':{ 'name':'componentFormat', 'value':fHDRFilmComponentFormatMitsuba } } )
    elementDict['children'].append( { 'type':'boolean', 
        'attributes':{ 'name':'attachLog', 'value':booleanToMisubaText(fHDRFilmAttachLog) } } )
    elementDict['children'].append( { 'type':'boolean', 
        'attributes':{ 'name':'banner', 'value':booleanToMisubaText(fHDRFilmBanner) } } )
    elementDict['children'].append( { 'type':'boolean', 
        'attributes':{ 'name':'highQualityEdges', 'value':booleanToMisubaText(fHDRFilmHighQualityEdges) } } )

    return elementDict

def writeFilmHDRTiled(renderSettings, filmMitsuba):
    fTiledHDRFilmPixelFormat = cmds.getAttr("%s.%s" % (renderSettings, "fTiledHDRFilmPixelFormat"))
    fTiledHDRFilmComponentFormat = cmds.getAttr("%s.%s" % (renderSettings, "fTiledHDRFilmComponentFormat"))

    mayaPixelFormatUINameToMitsubaName = {
        'Luminance' : 'luminance',
        'Luminance Alpha' : 'luminanceAlpha',
        'RGB' : 'rgb',
        'RGBA' : 'rgba',
        'XYZ' : 'xyz',
        'XYZA' : 'xyza',
        'Spectrum' : 'spectrum',
        'Spectrum Alpha' : 'spectrumAlpha'
    }

    if fTiledHDRFilmPixelFormat in mayaPixelFormatUINameToMitsubaName:
        fTiledHDRFilmPixelFormatMitsuba = mayaPixelFormatUINameToMitsubaName[fTiledHDRFilmPixelFormat]
    else:
        print( "Unsupported pixel format : %s. Using RGB" % fTiledHDRFilmPixelFormat)
        fTiledHDRFilmPixelFormatMitsuba = "rgb"

    mayaComponentFormatUINameToMitsubaName = {
        'Float 16' : 'float16',
        'Float 32' : 'float32',
        'UInt 32' : 'uint32',
    }

    if fTiledHDRFilmComponentFormat in mayaComponentFormatUINameToMitsubaName:
        fTiledHDRFilmComponentFormatMitsuba = mayaComponentFormatUINameToMitsubaName[fTiledHDRFilmComponentFormat]
    else:
        print( "Unsupported component format : %s. Using Float 16" % fTiledHDRFilmComponentFormat)
        fTiledHDRFilmComponentFormatMitsuba = "float16"

    elementDict = {'type':'film'}
    elementDict['attributes'] = {'type':filmMitsuba}

    elementDict['children'] = []
    elementDict['children'].append( { 'type':'string', 
        'attributes':{ 'name':'pixelFormat', 'value':fTiledHDRFilmPixelFormatMitsuba } } )
    elementDict['children'].append( { 'type':'string', 
        'attributes':{ 'name':'componentFormat', 'value':fTiledHDRFilmComponentFormatMitsuba } } )

    return elementDict

def writeFilmLDR(renderSettings, filmMitsuba):
    fLDRFilmFileFormat = cmds.getAttr("%s.%s" % (renderSettings, "fLDRFilmFileFormat"))
    fLDRFilmPixelFormat = cmds.getAttr("%s.%s" % (renderSettings, "fLDRFilmPixelFormat"))
    fLDRFilmTonemapMethod = cmds.getAttr("%s.%s" % (renderSettings, "fLDRFilmTonemapMethod"))
    fLDRFilmGamma = cmds.getAttr("%s.%s" % (renderSettings, "fLDRFilmGamma"))
    fLDRFilmExposure = cmds.getAttr("%s.%s" % (renderSettings, "fLDRFilmExposure"))
    fLDRFilmKey = cmds.getAttr("%s.%s" % (renderSettings, "fLDRFilmKey"))
    fLDRFilmBurn = cmds.getAttr("%s.%s" % (renderSettings, "fLDRFilmBurn"))
    fLDRFilmBanner = cmds.getAttr("%s.%s" % (renderSettings, "fLDRFilmBanner"))
    fLDRFilmHighQualityEdges = cmds.getAttr("%s.%s" % (renderSettings, "fLDRFilmHighQualityEdges"))

    mayaFileFormatUINameToMitsubaName = {
        "PNG (.png)"  : "png",
        "JPEG (.jpg)" : "jpeg"
    }

    if fLDRFilmFileFormat in mayaFileFormatUINameToMitsubaName:
        fLDRFilmFileFormatMitsuba = mayaFileFormatUINameToMitsubaName[fLDRFilmFileFormat]
    else:
        print( "Unsupported file format : %s. Using PNG (.png)" % fLDRFilmFileFormat)
        fLDRFilmFileFormatMitsuba = "png"

    mayaPixelFormatUINameToMitsubaName = {
        'Luminance' : 'luminance',
        'Luminance Alpha' : 'luminanceAlpha',
        'RGB' : 'rgb',
        'RGBA' : 'rgba'
    }

    if fLDRFilmPixelFormat in mayaPixelFormatUINameToMitsubaName:
        fLDRFilmPixelFormatMitsuba = mayaPixelFormatUINameToMitsubaName[fLDRFilmPixelFormat]
    else:
        print( "Unsupported pixel format : %s. Using RGB" % fLDRFilmPixelFormat)
        fLDRFilmPixelFormatMitsuba = "rgb"

    mayaTonemapMethodUINameToMitsubaName = {
        'Gamma' : 'gamma',
        'Reinhard' : 'reinhard'
    }

    if fLDRFilmTonemapMethod in mayaTonemapMethodUINameToMitsubaName:
        fLDRFilmTonemapMethodMitsuba = mayaTonemapMethodUINameToMitsubaName[fLDRFilmTonemapMethod]
    else:
        print( "Unsupported tonemap method : %s. Using Gamma" % fLDRFilmTonemapMethod)
        fLDRFilmTonemapMethodMitsuba = "gamma"

    elementDict = {'type':'film'}
    elementDict['attributes'] = {'type':filmMitsuba}

    elementDict['children'] = []
    elementDict['children'].append( { 'type':'string', 
        'attributes':{ 'name':'fileFormat', 'value':fLDRFilmFileFormatMitsuba } } )
    elementDict['children'].append( { 'type':'string', 
        'attributes':{ 'name':'pixelFormat', 'value':fLDRFilmPixelFormatMitsuba } } )
    elementDict['children'].append( { 'type':'string', 
        'attributes':{ 'name':'tonemapMethod', 'value':fLDRFilmTonemapMethodMitsuba } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'gamma', 'value':str(fLDRFilmGamma) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'exposure', 'value':str(fLDRFilmExposure) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'key', 'value':str(fLDRFilmKey) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'burn', 'value':str(fLDRFilmBurn) } } )
    elementDict['children'].append( { 'type':'boolean', 
        'attributes':{ 'name':'banner', 'value':booleanToMisubaText(fLDRFilmBanner) } } )
    elementDict['children'].append( { 'type':'boolean', 
        'attributes':{ 'name':'highQualityEdges', 'value':booleanToMisubaText(fLDRFilmHighQualityEdges) } } )

    return elementDict

def writeFilmMath(renderSettings, filmMitsuba):
    fMathFilmFileFormat = cmds.getAttr("%s.%s" % (renderSettings, "fMathFilmFileFormat"))
    fMathFilmPixelFormat = cmds.getAttr("%s.%s" % (renderSettings, "fMathFilmPixelFormat"))
    fMathFilmDigits = cmds.getAttr("%s.%s" % (renderSettings, "fMathFilmDigits"))
    fMathFilmVariable = cmds.getAttr("%s.%s" % (renderSettings, "fMathFilmVariable"))
    fMathFilmHighQualityEdges = cmds.getAttr("%s.%s" % (renderSettings, "fMathFilmHighQualityEdges"))

    mayaFileFormatUINameToMitsubaName = {
        "Matlab (.m)"  : "matlab",
        "Mathematica (.m)" : "mathematica",
        "NumPy (.npy)" : "numpy"
    }

    if fMathFilmFileFormat in mayaFileFormatUINameToMitsubaName:
        fMathFilmFileFormatMitsuba = mayaFileFormatUINameToMitsubaName[fMathFilmFileFormat]
    else:
        print( "Unsupported file format : %s. Using Matlab (.m)" % fMathFilmFileFormat)
        fMathFilmFileFormatMitsuba = "matlab"

    mayaPixelFormatUINameToMitsubaName = {
        'Luminance' : 'luminance',
        'Luminance Alpha' : 'luminanceAlpha',
        'RGB' : 'rgb',
        'RGBA' : 'rgba',
        'Spectrum' : 'spectrum',
        'Spectrum Alpha' : 'spectrumAlpha'
    }

    if fMathFilmPixelFormat in mayaPixelFormatUINameToMitsubaName:
        fMathFilmPixelFormatMitsuba = mayaPixelFormatUINameToMitsubaName[fMathFilmPixelFormat]
    else:
        print( "Unsupported pixel format : %s. Using RGB" % fMathFilmPixelFormat)
        fMathFilmPixelFormatMitsuba = "rgb"

    elementDict = {'type':'film'}
    elementDict['attributes'] = {'type':filmMitsuba}

    elementDict['children'] = []
    elementDict['children'].append( { 'type':'string', 
        'attributes':{ 'name':'fileFormat', 'value':fMathFilmFileFormatMitsuba } } )
    elementDict['children'].append( { 'type':'string', 
        'attributes':{ 'name':'pixelFormat', 'value':fMathFilmPixelFormatMitsuba } } )
    elementDict['children'].append( { 'type':'integer', 
        'attributes':{ 'name':'digits', 'value':str(fMathFilmDigits) } } )
    elementDict['children'].append( { 'type':'string', 
        'attributes':{ 'name':'variable', 'value':fMathFilmVariable } } )
    elementDict['children'].append( { 'type':'boolean', 
        'attributes':{ 'name':'highQualityEdges', 'value':booleanToMisubaText(fMathFilmHighQualityEdges) } } )

    return elementDict

def writeFilm(frameNumber, renderSettings):
    #Resolution
    imageWidth = cmds.getAttr("defaultResolution.width")
    imageHeight = cmds.getAttr("defaultResolution.height")

    # Film
    filmMaya = cmds.getAttr("%s.%s" % (renderSettings, "film"))
    mayaFilmUINameToMitsubaName = {
        "HDR Film"  : "hdrfilm",
        "LDR Film" : "ldrfilm",
        "HDR Film - Tiled"  : "tiledhdrfilm",
        "Math Film"  : "mfilm",
    }
    if filmMaya in mayaFilmUINameToMitsubaName:
        filmMitsuba = mayaFilmUINameToMitsubaName[filmMaya]
    else:
        filmMitsuba = "hdrfilm"

    mayaUINameToFilmFunction = {
        "HDR Film" : writeFilmHDR,
        "LDR Film" : writeFilmLDR,
        "HDR Film - Tiled" : writeFilmHDRTiled,
        "Math Film" : writeFilmMath
    }

    if filmMaya in mayaUINameToFilmFunction:
        writeFilmFunction = mayaUINameToFilmFunction[filmMaya]
    else:
        print( "Unsupported Film : %s. Using HDR" % filmMaya)
        writeFilmFunction = writeFilmHDR

    filmElement = writeFilmFunction(renderSettings, filmMitsuba)

    rfilterElement = writeReconstructionFilter(renderSettings)

    #elementDict = {'type':'film'}
    #elementDict['attributes'] = {'type':filmMitsuba}

    #elementDict['children'] = []
    #elementDict['children'].append( { 'type':'boolean', 'attributes':{ 'name':'banner', 'value':'false' } } )

    filmElement['children'].append( { 'type':'integer', 
        'attributes':{ 'name':'height', 'value':str(imageHeight) } } )
    filmElement['children'].append( { 'type':'integer', 
        'attributes':{ 'name':'width', 'value':str(imageWidth) } } )
    filmElement['children'].append( rfilterElement )

    multichannel = cmds.getAttr("%s.%s" % (renderSettings, "multichannel"))
    if multichannel and filmMitsuba in ["hdrfilm", "tiledhdrfilm"]:
        filmElement = filmAddMultichannelAttributes(renderSettings, filmElement)

    return filmElement

'''
Write sensor, which include camera, image sampler, and film
'''
def getRenderableCamera():
    cams = cmds.ls(type="camera")
    rCamShape = ""
    for cam in cams:
        isRenderable = cmds.getAttr(cam+".renderable")
        if isRenderable:
            print( "Render Settings - Camera          : %s" % cam )
            rCamShape = cam
            break

    if rCamShape == "":
        print( "No renderable camera found. Rendering with first camera : %s" % cams[0] )
        rCamShape = cams[0]

    return rCamShape

def writeSensor(frameNumber, renderSettings):
    # Find renderable camera
    rCamShape = getRenderableCamera()

    # Type
    camType = "perspective"
    if cmds.getAttr(rCamShape+".orthographic"):
        camType = "orthographic"
    elif cmds.getAttr(rCamShape+".depthOfField"):
        camType = "thinlens"

    sensorOverride = cmds.getAttr("%s.sensorOverride" % renderSettings)
    mayaUINameToMistubaSensor = { 
        "Spherical" : "spherical",
        "Telecentric" : "telecentric",
        "Radiance Meter" : "radiancemeter",
        "Fluence Meter" : "fluencemeter",
        "Perspective Pinhole Camera with Radial Distortion" : "perspective_rdist"
    }
    #"Irradiance Meter" : "irradiancemeter",

    if sensorOverride != "None":
        camType = mayaUINameToMistubaSensor[sensorOverride]
        print( "\n\n\nSensor Override : %s - %s\n\n\n" % (sensorOverride, camType) )

    # Orientation    
    camera = pymel.core.PyNode(rCamShape)
    camAim = camera.getWorldCenterOfInterest()
    camPos = camera.getEyePoint('world')
    camUp = camera.getWorldUp()

    # DoF
    apertureRadius = 1
    focusDistance = 1
    if camType == "thinlens":
        apertureRadius = cmds.getAttr(rCamShape+".focusRegionScale")
        focusDistance = cmds.getAttr(rCamShape+".focusDistance")

    # FoV
    fov = cmds.camera(rCamShape, query=True, horizontalFieldOfView=True)

    # Orthographic
    orthographicWidth = cmds.getAttr( rCamShape + ".orthographicWidth")
    orthographicWidth /= 2.0

    # Near Clip Plane
    nearClip = cmds.getAttr(rCamShape+".nearClipPlane")

    # Radial distortion
    perspectiveRdistKc2 = cmds.getAttr("%s.sPerspectiveRdistKc2" % renderSettings)
    perspectiveRdistKc4 = cmds.getAttr("%s.sPerspectiveRdistKc4" % renderSettings)

    # Write Camera
    elementDict = {'type':'sensor'}
    elementDict['attributes'] = {'type':camType}

    elementDict['children'] = []

    if camType in ["thinlens", "perspective"]:
        elementDict['children'].append( { 'type':'float', 
            'attributes':{ 'name':'fov', 'value':str(fov) } } )
        elementDict['children'].append( { 'type':'string', 
            'attributes':{ 'name':'fovAxis', 'value':'x' } } )

    if camType in ["thinlens", "perspective", "orthographic", "telecentric"]:
        elementDict['children'].append( { 'type':'float', 
            'attributes':{ 'name':'nearClip', 'value':str(nearClip) } } )

    if camType in ["thinlens", "telecentric"]:
        elementDict['children'].append( { 'type':'float', 
            'attributes':{ 'name':'apertureRadius', 'value':str(apertureRadius) } } )
        elementDict['children'].append( { 'type':'float', 
            'attributes':{ 'name':'focusDistance', 'value':str(focusDistance) } } )

    if camType in ["perspective_rdist"]:
        elementDict['children'].append( { 'type':'string', 
            'attributes':{ 'name':'kc', 'value':str(perspectiveRdistKc2) + ", " + str(perspectiveRdistKc4)} } )

    # Generate transform
    transformDict = {'type':'transform'}
    transformDict['attributes'] = {'name':'toWorld'}
    transformDict['children'] = []
    if camType == "orthographic":
        transformDict['children'].append( { 'type':'scale', 
            'attributes':{ 'x':str(orthographicWidth), 'y':str(orthographicWidth) } } )
    transformDict['children'].append( { 'type':'lookat', 
        'attributes':{ 'target':str(camAim[0]) + " " + str(camAim[1]) + " " + str(camAim[2]), 
            'origin':str(camPos[0]) + " " + str(camPos[1]) + " " + str(camPos[2]),
             'up':str(camUp[0]) + " " + str(camUp[1]) + " " + str(camUp[2])} } )

    elementDict['children'].append(transformDict)

    # Write Sampler
    samplerDict = writeSampler(frameNumber, renderSettings)
    elementDict['children'].append(samplerDict)

    # Write Film
    filmDict = writeFilm(frameNumber, renderSettings)
    elementDict['children'].append(filmDict)

    return elementDict

def writeLightDirectional(light):
    intensity = cmds.getAttr(light+".intensity")
    color = cmds.getAttr(light+".color")[0]
    irradiance = [0,0,0]
    for i in range(3):
        irradiance[i] = intensity*color[i]

    matrix = cmds.getAttr(light+".worldMatrix")
    lightDir = [-matrix[8],-matrix[9],-matrix[10]]

    # Create a structure to be written
    elementDict = {'type':'emitter'}
    elementDict['attributes'] = {'type':'directional'}

    elementDict['children'] = []

    elementDict['children'].append( { 'type':'srgb', 
        'attributes':{ 'name':'irradiance', 'value':str(irradiance[0]) + " " + str(irradiance[1]) + " " + str(irradiance[2]) } } )
    elementDict['children'].append( { 'type':'vector', 
        'attributes':{ 'name':'direction', 'x':str(lightDir[0]), 'y':str(lightDir[1]), 'z':str(lightDir[2]) } } )

    return elementDict

def writeLightPoint(light):
    intensity = cmds.getAttr(light+".intensity")
    color = cmds.getAttr(light+".color")[0]
    irradiance = [0,0,0]
    for i in range(3):
        irradiance[i] = intensity*color[i]

    matrix = cmds.getAttr(light+".worldMatrix")
    position = [matrix[12],matrix[13],matrix[14]]

    # Create a structure to be written
    elementDict = {'type':'emitter'}
    elementDict['attributes'] = {'type':'point'}

    elementDict['children'] = []

    elementDict['children'].append( { 'type':'srgb', 
        'attributes':{ 'name':'intensity', 'value':str(irradiance[0]) + " " + str(irradiance[1]) + " " + str(irradiance[2]) } } )
    elementDict['children'].append( { 'type':'point', 
        'attributes':{ 'name':'position', 'x':str(position[0]), 'y':str(position[1]), 'z':str(position[2]) } } )

    return elementDict


def writeLightSpot(light):
    intensity = cmds.getAttr(light+".intensity")
    color = cmds.getAttr(light+".color")[0]
    irradiance = [0,0,0]
    for i in range(3):
        irradiance[i] = intensity*color[i]

    coneAngle = float(cmds.getAttr(light+".coneAngle"))/2.0
    penumbraAngle = float(cmds.getAttr(light+".penumbraAngle"))

    matrix = cmds.getAttr(light+".worldMatrix")
    position = [matrix[12],matrix[13],matrix[14]]

    transform = cmds.listRelatives( light, parent=True )[0]
    rotation = cmds.getAttr(transform+".rotate")[0]

    # Create a structure to be written
    elementDict = {'type':'emitter'}
    elementDict['attributes'] = {'type':'spot'}

    elementDict['children'] = []

    elementDict['children'].append( { 'type':'rgb', 
        'attributes':{ 'name':'intensity', 'value':str(irradiance[0]) + " " + str(irradiance[1]) + " " + str(irradiance[2]) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'cutoffAngle', 'value':str(coneAngle + penumbraAngle) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'beamWidth', 'value':str(coneAngle) } } )

    transformDict = {'type':'transform'}
    transformDict['attributes'] = {'name':'toWorld'}

    transformDict['children'] = []

    transformDict['children'].append( { 'type':'rotate', 
        'attributes':{ 'y':str(1), 'angle':str(180.0) } } )
    if rotation[0] != 0.0:
        transformDict['children'].append( { 'type':'rotate', 
            'attributes':{ 'x':str(1), 'angle':str(rotation[0]) } } )
    if rotation[1] != 0.0:
        transformDict['children'].append( { 'type':'rotate', 
            'attributes':{ 'y':str(1), 'angle':str(rotation[1]) } } )
    if rotation[2] != 0.0:
        transformDict['children'].append( { 'type':'rotate', 
            'attributes':{ 'z':str(1), 'angle':str(rotation[2]) } } )
    transformDict['children'].append( { 'type':'translate', 
        'attributes':{ 'x':str(position[0]), 'y':str(position[1]), 'z':str(position[2]) } } )

    elementDict['children'].append( transformDict )

    return elementDict


def writeLightSunSky(sunsky):
    sun = cmds.getAttr(sunsky+".useSun")
    sky = cmds.getAttr(sunsky+".useSky")
    if sun and sky:
        emitterType = 'sunsky'
    elif sun:
        emitterType = 'sun'
    elif sky:
        emitterType = 'sky'
    else:
        print "Must use either sun or sky, defaulting to sunsky"
        emitterType = 'sunsky'

    turbidity = cmds.getAttr(sunsky+".turbidity")
    albedo = cmds.getAttr(sunsky+".albedo")
    date = cmds.getAttr(sunsky+".date")
    time = cmds.getAttr(sunsky+".time")
    latitude = cmds.getAttr(sunsky+".latitude")
    longitude = cmds.getAttr(sunsky+".longitude")
    timezone = cmds.getAttr(sunsky+".timezone")
    stretch = cmds.getAttr(sunsky+".stretch")
    resolution = cmds.getAttr(sunsky+".resolution")
    sunScale = cmds.getAttr(sunsky+".sunScale")
    skyScale = cmds.getAttr(sunsky+".skyScale")
    sunRadiusScale = cmds.getAttr(sunsky+".sunRadiusScale")

    # Create a structure to be written
    elementDict = {'type':'emitter'}
    elementDict['attributes'] = {'type':emitterType}

    elementDict['children'] = []

    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'turbidity', 'value':str(turbidity) } } )
    elementDict['children'].append( { 'type':'srgb', 
        'attributes':{ 'name':'albedo', 'value':str(albedo[0][0]) + " " + str(albedo[0][1]) + " " + str(albedo[0][2]) } } )

    elementDict['children'].append( { 'type':'integer', 
        'attributes':{ 'name':'year', 'value':str(date[0][0]) } } )
    elementDict['children'].append( { 'type':'integer', 
        'attributes':{ 'name':'month', 'value':str(date[0][1]) } } )
    elementDict['children'].append( { 'type':'integer', 
        'attributes':{ 'name':'day', 'value':str(date[0][2]) } } )

    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'hour', 'value':str(time[0][0]) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'minute', 'value':str(time[0][1]) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'second', 'value':str(time[0][2]) } } )

    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'latitude', 'value':str(latitude) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'longitude', 'value':str(longitude) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'timezone', 'value':str(timezone) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'stretch', 'value':str(stretch) } } )

    elementDict['children'].append( { 'type':'integer', 
        'attributes':{ 'name':'resolutionX', 'value':str(resolution[0][0]) } } )
    elementDict['children'].append( { 'type':'integer', 
        'attributes':{ 'name':'resolutionY', 'value':str(resolution[0][1]) } } )

    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'sunScale', 'value':str(sunScale) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'skyScale', 'value':str(skyScale) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'sunRadiusScale', 'value':str(sunRadiusScale) } } )

    return elementDict

def writeLightEnvMap(envmap):
    connections = cmds.listConnections(envmap, plugs=False, c=True)
    fileName = ""
    hasFile = False
    correctFormat = True

    if connections:
        connectionAttr = "source"
        fileName = getTextureFile(envmap, connectionAttr)

        if fileName:
            extension = fileName[len(fileName)-3:len(fileName)]
            if extension == "hdr" or extension == "exr":
                hasFile = True
            else:
                print "file must be hdr or exr"
                correctFormat = False
        else:
            print "Please supply a fileName if you plan to use an environment map"
            correctFormat = False
    
    if correctFormat:
        if hasFile:
            scale = cmds.getAttr(envmap+".scale")
            gamma = cmds.getAttr(envmap+".gamma")
            cache = cmds.getAttr(envmap+".cache")

            samplingWeight = cmds.getAttr(envmap+".samplingWeight")
            rotate = cmds.getAttr(envmap+".rotate")[0]

            cacheText = 'true' if cache else 'false'

            # Create a structure to be written
            elementDict = {'type':'emitter'}
            elementDict['attributes'] = {'type':'envmap'}

            elementDict['children'] = []

            elementDict['children'].append( { 'type':'string', 
                'attributes':{ 'name':'filename', 'value':fileName } } )
            elementDict['children'].append( { 'type':'float', 
                'attributes':{ 'name':'scale', 'value':str(scale) } } )
            elementDict['children'].append( { 'type':'float', 
                'attributes':{ 'name':'gamma', 'value':str(gamma) } } )
            elementDict['children'].append( { 'type':'boolean', 
                'attributes':{ 'name':'cache', 'value':cacheText } } )
            elementDict['children'].append( { 'type':'float', 
                'attributes':{ 'name':'samplingWeight', 'value':str(samplingWeight) } } )

            transformDict = {'type':'transform'}
            transformDict['attributes'] = {'name':'toWorld'}

            transformDict['children'] = []
            transformDict['children'].append( { 'type':'rotate', 
                'attributes':{ 'x':str(1), 'angle':str(rotate[0]) } } )
            transformDict['children'].append( { 'type':'rotate', 
                'attributes':{ 'y':str(1), 'angle':str(rotate[1]) } } )
            transformDict['children'].append( { 'type':'rotate', 
                'attributes':{ 'z':str(1), 'angle':str(rotate[2]) } } )

            elementDict['children'].append( transformDict )

            return elementDict

        else:
            radiance = cmds.getAttr(envmap+".source")
            samplingWeight = cmds.getAttr(envmap+".samplingWeight")

            # Create a structure to be written
            elementDict = {'type':'emitter'}
            elementDict['attributes'] = {'type':'constant'}

            elementDict['children'] = []

            elementDict['children'].append( { 'type':'srgb', 
                'attributes':{ 'name':'radiance', 'value':str(radiance[0]) + " " + str(radiance[1]) + " " + str(radiance[2]) } } )
            elementDict['children'].append( { 'type':'float', 
                'attributes':{ 'name':'samplingWeight', 'value':str(samplingWeight) } } )

            return elementDict


'''
Write lights
'''
def writeLights():
    lights = cmds.ls(type="light")
    sunskyLights = cmds.ls(type="MitsubaSunsky")
    envLights = cmds.ls(type="MitsubaEnvironmentLight")

    if sunskyLights and envLights or sunskyLights and len(sunskyLights)>1 or envLights and len(envLights)>1:
        print "Cannot specify more than one environment light (MitsubaSunsky and MitsubaEnvironmentLight)"
        # print "Defaulting to constant environment emitter"
        # outFile.write(" <emitter type=\"constant\"/>\n")

    lightElements = []

    # Gather element definitions for standard lights
    for light in lights:
        lightType = cmds.nodeType(light)
        if lightType == "directionalLight":
            lightElements.append( writeLightDirectional(light) )
        elif lightType == "pointLight":
            lightElements.append( writeLightPoint(light) )
        elif lightType == "spotLight":
            lightElements.append( writeLightSpot(light) )

    # Gather element definitions for Sun and Sky lights
    if sunskyLights:
        sunsky = sunskyLights[0]
        lightElements.append( writeLightSunSky(sunsky) )

    # Gather element definitions for Environment lights
    if envLights:
        envmap = envLights[0]
        lightElements.append( writeLightEnvMap(envmap) )

    return lightElements

def getRenderableGeometry():
    # Build list of visible geometry
    transforms = cmds.ls(type="transform")
    geoms = []

    for transform in transforms:
        rels = cmds.listRelatives(transform)
        if rels:
            for rel in rels:
                if cmds.nodeType(rel)=="mesh":
                    visible = cmds.getAttr(transform+".visibility")
                    if cmds.attributeQuery("intermediateObject", node=transform, exists=True):
                        visible = visible and not cmds.getAttr(transform+".intermediateObject")
                    if cmds.attributeQuery("overrideEnabled", node=transform, exists=True):
                        visible = visible and cmds.getAttr(transform+".overrideVisibility")
                    if visible:
                        geoms.append(transform)

    return geoms

def writeMaterials(geoms):
    writtenMaterials = []
    materialElements = []

    #Write the material for each piece of geometry in the scene
    for geom in geoms:
        material = getShader(geom)          #Gets the user define names of the shader
        materialType = cmds.nodeType(material)
        if materialType in materialNodeTypes:
            if material not in writtenMaterials:
                if "twosided" in cmds.listAttr(material) and cmds.getAttr(material+".twosided"):
                    # Create a structure to be written
                    elementDict = {'type':'bsdf'}
                    elementDict['attributes'] = {'type':'twosided', 'id':material}

                    elementDict['children'] = []

                    childElement = writeShader(material, material+"InnerMaterial")
                    elementDict['children'].append(childElement)
                    
                    materialElements.append(elementDict)
                else:
                    if materialType != "MitsubaObjectAreaLightShader":
                        materialElement = writeShader(material, material)
                        materialElements.append( materialElement )

                writtenMaterials.append(material)
        
    return writtenMaterials, materialElements

def exportGeometry(geom, renderDir):
    output = os.path.join(renderDir, geom + ".obj")
    cmds.select(geom)
    objFile = cmds.file(output, op=True, typ="OBJexport", options="groups=1;ptgroups=1;materials=0;smoothing=1;normals=1", exportSelected=True, force=True)
    return objFile

def findAndWriteMedium(geom, shader):
    #check for a homogeneous material
    #this checks if there is a homogeneous medium, and returns the attribute that it
    #is connected to if there is one
    connections = cmds.listConnections(shader, type="HomogeneousParticipatingMedium", connections=True)
    #We want to make sure it is connected to the ".material" attribute
    hasMedium = False
    medium = ""
    if connections and connections[0]==shader+".material":
        hasMedium = True
        medium = connections[1]

    if hasMedium:
        mediumElement = writeMedium(medium)
    else:
        mediumElement = None

    return mediumElement

def writeShape(geom, shader, renderDir):
    shapeDict = {'type':'shape'}
    shapeDict['attributes'] = {'type':'obj'}

    shapeDict['children'] = []
    shapeDict['children'].append( { 'type':'string', 
        'attributes':{ 'name':'filename', 'value':geom + ".obj" } } )

    if cmds.nodeType(shader) in materialNodeTypes:
        # Check for area lights
        if cmds.nodeType(shader) == "MitsubaObjectAreaLightShader":
            shaderElement = writeShader(shader, shader)
            shapeDict['children'].append(shaderElement)

        # Otherwise refer to the already written material
        else:
            refDict = {'type':'ref'}
            refDict['attributes'] = {'id':shader}
            shapeDict['children'].append(refDict)

        # Write volume definition, if one exists
        mediumDict = findAndWriteMedium(geom, shader)
        if mediumDict:
            shapeDict['children'].append(mediumDict)

    elif cmds.nodeType(shader) == "MitsubaVolume":
        volumeElement = writeVolume(renderDir, shader, geom)
        if volumeElement:
            shapeDict['children'].append(volumeElement)
    
    return shapeDict


def writeGeometryAndMaterials(renderDir):
    geoms = getRenderableGeometry()

    writtenMaterials, materialElements = writeMaterials(geoms)

    geoFiles = []
    shapeElements = []

    #Write each piece of geometry with references to materials
    for geom in geoms:
        shader = getShader(geom)

        exportedGeo = exportGeometry(geom, renderDir)
        geoFiles.append( exportedGeo )

        shapeElement = writeShape(geom, shader, renderDir)
        shapeElements.append(shapeElement)

    return (geoFiles, shapeElements, materialElements)

def getVtxPos(shapeNode):
    vtxWorldPosition = []    # will contain positions un space of all object vertex
    vtxIndexList = cmds.getAttr( shapeNode+".vrts", multiIndices=True )
    for i in vtxIndexList :
        curPointPosition = cmds.xform( str(shapeNode)+".pnts["+str(i)+"]", query=True, translation=True, worldSpace=True )    # [1.1269192869360154, 4.5408735275268555, 1.3387055339628269]
        vtxWorldPosition.append( curPointPosition )
    return vtxWorldPosition

#
# Needs to be generalized
#
def writeVolume(renderDir, material, geom):
    #sourceFileName = "smoke_source\\text\\smoke_test_"
    hasFile = False
    fileTexture = ""
    connections = cmds.listConnections(material, connections=True)
    for i in range(len(connections)):
        if i%2==1:
            connection = connections[i]
            connectionType = cmds.nodeType(connection)
            if connectionType == "file" and connections[i-1]==material+".sourceFile":
                inFileName = cmds.getAttr(connection+".fileTextureName")
                hasFile=True

    if not hasFile:
        print "please supply a file for the mitsuba volume"
        return None

    sourceFile = open(inFileName, 'r')

    volFileName = os.path.join(renderDir, "temp.vol")
    volFile = open(volFileName, 'wb+')

    #grid dimensions
    gd = cmds.getAttr(material+".gridDimensions")[0]
    height = int(gd[0])
    width  = int(gd[1])
    depth  = int(gd[2])
    #I only use color, but you could send data that had n components
    chans  = 1

    vtxPos = getVtxPos(geom)

    maxV = [-1000,-1000,-1000]
    minV = [ 1000, 1000, 1000]


    for vtx in vtxPos:
        if vtx[0] > maxV[0]:
            maxV[0] = vtx[0]
        elif vtx[0] < minV[0]:
            minV[0] = vtx[0]
        if vtx[1] > maxV[1]:
            maxV[1] = vtx[1]
        elif vtx[1] < minV[1]:
            minV[1] = vtx[1]
        if vtx[2] > maxV[2]:
            maxV[2] = vtx[2]
        elif vtx[2] < minV[2]:
            minV[2] = vtx[2]
    #Mitsuba requires you to define an AABB for the volume data
    xmin = minV[0]
    ymin = minV[1]
    zmin = minV[2]
    xmax = maxV[0]
    ymax = maxV[1]
    zmax = maxV[2]

    #Pre-package the data from 563 data files to send to Mitsuba
    data = [0 for i in range(int(depth*width*height*chans))]

    for i in range(width):
        for j in range(height):
            for k in range(depth):
                temp = sourceFile.readline()
                tempFloat = 0
                try:
                    tempFloat = float(temp)
                except:
                    tempFloat = 0
                data[((k*height+j)*width+i)] = tempFloat


    #VOL
    volFile.write('VOL')
    #version number
    volFile.write(struct.pack('<b', 3))

    #encoding id
    volFile.write(struct.pack('<i', 1))

    #x,y,z dimensions
    volFile.write(struct.pack('<i', height))
    volFile.write(struct.pack('<i', width))
    volFile.write(struct.pack('<i', depth))

    #number of channels
    volFile.write(struct.pack('<i', 1))

    #AABB (xmin,ymin,zmin, xmax,ymax,zmax)
    volFile.write(struct.pack('<f', xmin))
    volFile.write(struct.pack('<f', ymin))
    volFile.write(struct.pack('<f', zmin))

    volFile.write(struct.pack('<f', xmax))
    volFile.write(struct.pack('<f', ymax))
    volFile.write(struct.pack('<f', zmax))

    #Smoke densities
    for i in range(depth*width*height*chans):
        density = data[i]
        volFile.write(struct.pack('<f', density))

    volFile.close()
    sourceFile.close()

    # Create a structure to be written
    mediumDict = {'type':'medium'}
    mediumDict['attributes'] = {'type':'heterogeneous', 'name':'interior'}

    mediumDict['children'] = []
    mediumDict['children'].append( { 'type':'string', 
        'attributes':{ 'name':'method', 'value':'woodcock' } } )

    volume1Dict = {'type':'volume'}
    volume1Dict['attributes'] = {'type':'gridvolume', 'name':'density'}

    volume1Dict['children'] = []
    volume1Dict['children'].append( { 'type':'string', 
        'attributes':{ 'name':'filename', 'value':volFileName } } )

    volume2Dict = {'type':'volume'}
    volume2Dict['attributes'] = {'type':'constvolume', 'name':'albedo'}

    volume2Dict['children'] = []
    volume2Dict['children'].append( { 'type':'spectrum', 
        'attributes':{ 'name':'value', 'value':str(0.9) } } )

    mediumDict['children'].append(volume1Dict)
    mediumDict['children'].append(volume2Dict)

    return mediumDict

def writeScene(outFileName, renderDir, renderSettings):
    outFile = open(outFileName, 'w+')

    #Scene stuff
    outFile.write("<?xml version=\'1.0\' encoding=\'utf-8\'?>\n")

    sceneElement = {'type':'scene'}
    sceneElement['attributes'] = {'version':'0.5.0'}
    sceneElement['children'] = []

    #Get integrator
    integratorElement = writeIntegrator(renderSettings)
    sceneElement['children'].append(integratorElement)

    #Get sensor : camera, sampler, and film
    frameNumber = int(cmds.currentTime(query=True))
    sensorElement = writeSensor(frameNumber, renderSettings)
    sceneElement['children'].append(sensorElement)

    #Get lights
    lightElements = writeLights()
    if lightElements:
        sceneElement['children'].extend(lightElements)

    #Get geom and material assignments
    (exportedGeometryFiles, shapeElements, materialElements) = writeGeometryAndMaterials(renderDir)
    if materialElements:
        sceneElement['children'].extend(materialElements)

    if shapeElements:
        sceneElement['children'].extend(shapeElements)

    # Write the structure to disk
    writeElement(outFile, sceneElement)

    outFile.close()

    return exportedGeometryFiles
