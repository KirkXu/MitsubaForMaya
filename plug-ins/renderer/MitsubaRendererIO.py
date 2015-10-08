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

    element = ""
    element += spacing + "<%s" % typeName
    for key, value in attributes.iteritems():
        element += " %s=\"%s\"" % (key, value)
    if children:
        element += ">\n"
        for child in children:
            #print( "child : %s" % str(child) )
            element += writeElementText(child, depth+1)
            #element += "\n"
        element  += spacing + "</%s>\n" % typeName
    else:
        element += "/>\n"
    
    return element

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
def writeMedium(medium, outFile, tabbedSpace="     ", depth=1):
    sigmaAS = cmds.getAttr(medium+".sigmaAS")
    sigmaA = cmds.getAttr(medium+".sigmaA")
    sigmaS = cmds.getAttr(medium+".sigmaS")
    sigmaT = cmds.getAttr(medium+".sigmaT")
    albedo = cmds.getAttr(medium+".albedo")
    scale = cmds.getAttr(medium+".scale")    

    '''
    outFile.write(tabbedSpace + " <medium type=\"homogeneous\" name=\"interior\">\n")
    
    #check if we want to use sigmaA and sigmaT or sigmaT and albedo
    if sigmaAS:
        outFile.write(tabbedSpace + "      <rgb name=\"sigmaA\" value=\"" + str(sigmaA[0][0]) + " " + str(sigmaA[0][1]) + " " + str(sigmaA[0][2]) + "\"/>\n")
        outFile.write(tabbedSpace + "      <rgb name=\"sigmaS\" value=\"" + str(sigmaS[0][0]) + " " + str(sigmaS[0][1]) + " " + str(sigmaS[0][2]) + "\"/>\n")
    else:
        outFile.write(tabbedSpace + "      <rgb name=\"sigmaT\" value=\"" + str(sigmaT[0][0]) + " " + str(sigmaT[0][1]) + " " + str(sigmaT[0][2]) + "\"/>\n")
        outFile.write(tabbedSpace + "      <rgb name=\"albedo\" value=\"" + str(albedo[0][0]) + " " + str(albedo[0][1]) + " " + str(albedo[0][2]) + "\"/>\n")

    outFile.write(tabbedSpace + "      <float name=\"scale\" value=\"" + str(scale) + "\"/>\n")
    outFile.write(tabbedSpace + " </medium>\n")
    '''

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

    # Write structure
    #writeElement(outFile, elementDict, depth)

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

def writeShaderSmoothCoating(material, materialName, outFile, tabbedSpace="     ", depth=1):
    intIOR = cmds.getAttr(material+".intIOR")
    extIOR = cmds.getAttr(material+".extIOR")
    thickness = cmds.getAttr(material+".thickness")
    sigmaA = cmds.getAttr(material+".sigmaA")
    specularReflectance = cmds.getAttr(material+".specularReflectance")

    '''
    outFile.write(tabbedSpace + " <bsdf type=\"coating\" id=\"" + materialName + "\">\n")
    outFile.write(tabbedSpace + "     <float name=\"intIOR\" value=\"" + str(intIOR) + "\"/>\n")
    outFile.write(tabbedSpace + "     <float name=\"extIOR\" value=\"" + str(extIOR) + "\"/>\n")
    outFile.write(tabbedSpace + "     <float name=\"thickness\" value=\"" + str(thickness) + "\"/>\n")
    outFile.write(tabbedSpace + "     <srgb name=\"sigmaA\" value=\"" + str(sigmaA[0][0]) + " " + str(sigmaA[0][1]) + " " + str(sigmaA[0][2]) + "\"/>\n")
    outFile.write(tabbedSpace + "     <srgb name=\"specularReflectance\" value=\"" + str(specularReflectance[0][0]) + " " + str(specularReflectance[0][1]) + " " + str(specularReflectance[0][2]) + "\"/>\n")
    
    #Nested bsdf
    hasNestedBSDF = False
    connections = cmds.listConnections(material, connections=True)
    for i in range(len(connections)):
        if i%2==1:
            connection = connections[i]
            connectionType = cmds.nodeType(connection)
            if connectionType in materialNodeTypes and connections[i-1]==material+".bsdf":
                #We've found the nested bsdf, so write it
                writeShader(connection, connection, outFile, tabbedSpace+"    ", depth+1)
                hasNestedBSDF = True

    if not hasNestedBSDF:
        #Write a basic diffuse using the bsdf attribute
        bsdf = cmds.getAttr(material+".bsdf")
        outFile.write(tabbedSpace + "     <bsdf type=\"diffuse\">\n")
        outFile.write(tabbedSpace + "          <srgb name=\"reflectance\" value=\"" + str(bsdf[0][0]) + " " + str(bsdf[0][1]) + " " + str(bsdf[0][2]) + "\"/>\n")
        outFile.write(tabbedSpace + "     </bsdf>\n")

    outFile.write(tabbedSpace + " </bsdf>\n")
    '''

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
                shaderElement = writeShader(connection, connection, outFile, tabbedSpace+"    ", depth+1)
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

def writeShaderConductor(material, materialName, outFile, tabbedSpace="     ", depth=1):
    conductorMaterial = cmds.getAttr(material+".material", asString=True)
    extEta = cmds.getAttr(material+".extEta")

    '''
    outFile.write(tabbedSpace + " <bsdf type=\"conductor\"   id=\"" + materialName + "\">\n")
    outFile.write(tabbedSpace + "     <string name=\"material\" value=\"" + str(conductorMaterial) + "\"/>\n")
    outFile.write(tabbedSpace + "     <float name=\"extEta\" value=\"" + str(extEta) + "\"/>\n")
    outFile.write(tabbedSpace + " </bsdf>\n")
    '''

    # Create a structure to be written
    elementDict = {'type':'bsdf'}
    elementDict['attributes'] = {'type':'conductor', 'id':materialName}

    elementDict['children'] = []
    elementDict['children'].append( { 'type':'string', 
        'attributes':{ 'name':'material', 'value':str(conductorMaterial) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'extEta', 'value':str(extEta) } } )

    # Write structure
    #writeElement(outFile, elementDict, depth)

    return elementDict

def writeShaderDielectric(material, materialName, outFile, tabbedSpace="     ", depth=1):
    #Get all of the required attributes
    intIOR = cmds.getAttr(material+".intIOR")
    extIOR = cmds.getAttr(material+".extIOR")

    '''
    #Write material
    outFile.write(tabbedSpace + " <bsdf type=\"dielectric\" id=\"" + materialName + "\">\n")
    outFile.write(tabbedSpace + "     <float name=\"intIOR\" value=\"" + str(intIOR) + "\"/>\n")
    outFile.write(tabbedSpace + "     <float name=\"extIOR\" value=\"" + str(extIOR) + "\"/>\n")
    outFile.write(tabbedSpace + " </bsdf>\n\n")
    '''

    # Create a structure to be written
    elementDict = {'type':'bsdf'}
    elementDict['attributes'] = {'type':'dielectric', 'id':materialName}

    elementDict['children'] = []
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'intIOR', 'value':str(intIOR) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'extIOR', 'value':str(extIOR) } } )

    # Write structure
    #writeElement(outFile, elementDict, depth)

    return elementDict

def writeShaderDiffuseTransmitter(material, materialName, outFile, tabbedSpace="     ", depth=1):
    # Get values from the scene
    transmittance = cmds.getAttr(material+".reflectance")

    '''
    outFile.write(tabbedSpace + " <bsdf type=\"diffuse\" id=\"" + materialName + "\">\n")
    outFile.write(tabbedSpace + "     <srgb name=\"reflectance\" value=\"" + str(transmittance[0][0]) + " " + str(transmittance[0][1]) + " " + str(transmittance[0][2]) + "\"/>\n")
    outFile.write(tabbedSpace + " </bsdf>\n")
    '''

    # Create a structure to be written
    elementDict = {'type':'bsdf'}
    elementDict['attributes'] = {'type':'diffuse', 'id':materialName}

    elementDict['children'] = []
    elementDict['children'].append( { 'type':'srgb', 
        'attributes':{ 'name':'reflectance', 'value':str(transmittance[0][0]) + " " + str(transmittance[0][1]) + " " + str(transmittance[0][2]) } } )

    # Write structure
    #writeElement(outFile, elementDict, depth)

    return elementDict

def writeShaderDiffuse(material, materialName, outFile, tabbedSpace="     ", depth=1):
    # Get values from the scene
    #texture
    connectionAttr = "reflectance"
    fileTexture = getTextureFile(material, connectionAttr)
    if not fileTexture:
        reflectance = cmds.getAttr(material+".reflectance")

    '''
    outFile.write(tabbedSpace + " <bsdf type=\"diffuse\" id=\"" + materialName + "\">\n")

    if fileTexture:
        outFile.write(tabbedSpace + "     <texture type=\"bitmap\" name=\"reflectance\">\n")
        outFile.write(tabbedSpace + "         <string name=\"filename\" value=\"" + fileTexture + "\"/>")
        outFile.write(tabbedSpace + "     </texture>\n")
    else:
        outFile.write(tabbedSpace + "     <srgb name=\"reflectance\" value=\"" + str(reflectance[0][0]) + " " + str(reflectance[0][1]) + " " + str(reflectance[0][2]) + "\"/>\n")

    outFile.write(tabbedSpace + " </bsdf>\n")
    '''

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

    # Write structure
    #writeElement(outFile, elementDict, depth)

    return elementDict

def writeShaderPhong(material, materialName, outFile, tabbedSpace="     ", depth=1):
    exponent = cmds.getAttr(material+".exponent")
    specularReflectance = cmds.getAttr(material+".specularReflectance")
    diffuseReflectance = cmds.getAttr(material+".diffuseReflectance")

    '''
    outFile.write(tabbedSpace + " <bsdf type=\"phong\" id=\"" + materialName + "\">\n")
    outFile.write(tabbedSpace + "     <float name=\"exponent\" value=\"" + str(exponent) + "\"/>\n")
    outFile.write(tabbedSpace + "     <srgb name=\"specularReflectance\" value=\"" + str(specularReflectance[0][0]) + " " + str(specularReflectance[0][1]) + " " + str(specularReflectance[0][2]) + "\"/>\n")
    outFile.write(tabbedSpace + "     <srgb name=\"diffuseReflectance\" value=\"" + str(diffuseReflectance[0][0]) + " " + str(diffuseReflectance[0][1]) + " " + str(diffuseReflectance[0][2]) + "\"/>\n")
    outFile.write(tabbedSpace + " </bsdf>\n")
    '''

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

    # Write structure
    #writeElement(outFile, elementDict, depth)

    return elementDict


def writeShaderPlastic(material, materialName, outFile, tabbedSpace="     ", depth=1):
    intIOR = cmds.getAttr(material+".intIOR")
    extIOR = cmds.getAttr(material+".extIOR")
    specularReflectance = cmds.getAttr(material+".specularReflectance")
    diffuseReflectance = cmds.getAttr(material+".diffuseReflectance")

    '''
    outFile.write(tabbedSpace + " <bsdf type=\"plastic\" id=\"" + materialName + "\">\n")
    outFile.write(tabbedSpace + "     <float name=\"intIOR\" value=\"" + str(intIOR) + "\"/>\n")
    outFile.write(tabbedSpace + "     <float name=\"extIOR\" value=\"" + str(extIOR) + "\"/>\n")
    outFile.write(tabbedSpace + "     <srgb name=\"specularReflectance\" value=\"" + str(specularReflectance[0][0]) + " " + str(specularReflectance[0][1]) + " " + str(specularReflectance[0][2]) + "\"/>\n")
    outFile.write(tabbedSpace + "     <srgb name=\"diffuseReflectance\" value=\"" + str(diffuseReflectance[0][0]) + " " + str(diffuseReflectance[0][1]) + " " + str(diffuseReflectance[0][2]) + "\"/>\n")
    outFile.write(tabbedSpace + " </bsdf>\n")
    '''

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

    # Write structure
    #writeElement(outFile, elementDict, depth)

    return elementDict

def writeShaderRoughCoating(material, materialName, outFile, tabbedSpace="     ", depth=1):
    distribution = cmds.getAttr(material+".distribution", asString=True)
    alpha = cmds.getAttr(material+".alpha")
    intIOR = cmds.getAttr(material+".intIOR")
    extIOR = cmds.getAttr(material+".extIOR")
    thickness = cmds.getAttr(material+".thickness")
    sigmaA = cmds.getAttr(material+".sigmaA")
    specularReflectance = cmds.getAttr(material+".specularReflectance")

    '''
    outFile.write(tabbedSpace + " <bsdf type=\"roughcoating\" id=\"" + materialName + "\">\n")
    outFile.write(tabbedSpace + "     <string name=\"distribution\" value=\"" + str(distribution) + "\"/>\n")
    outFile.write(tabbedSpace + "     <float name=\"alpha\" value=\"" + str(alpha) + "\"/>\n")
    outFile.write(tabbedSpace + "     <float name=\"intIOR\" value=\"" + str(intIOR) + "\"/>\n")
    outFile.write(tabbedSpace + "     <float name=\"extIOR\" value=\"" + str(extIOR) + "\"/>\n")
    outFile.write(tabbedSpace + "     <float name=\"thickness\" value=\"" + str(thickness) + "\"/>\n")
    outFile.write(tabbedSpace + "     <srgb name=\"sigmaA\" value=\"" + str(sigmaA[0][0]) + " " + str(sigmaA[0][1]) + " " + str(sigmaA[0][2]) + "\"/>\n")
    outFile.write(tabbedSpace + "     <srgb name=\"specularReflectance\" value=\"" + str(specularReflectance[0][0]) + " " + str(specularReflectance[0][1]) + " " + str(specularReflectance[0][2]) + "\"/>\n")
    
    #Nested bsdf
    hasNestedBSDF = False
    connections = cmds.listConnections(material, connections=True)
    for i in range(len(connections)):
        if i%2==1:
            connection = connections[i]
            connectionType = cmds.nodeType(connection)
            if connectionType in materialNodeTypes and connections[i-1]==material+".bsdf":
                #We've found the nested bsdf, so write it
                writeShader(connection, connection, outFile, tabbedSpace+"    ", depth+1)
                hasNestedBSDF=True
    
    if not hasNestedBSDF:
        #Write a basic diffuse using the bsdf attribute
        bsdf = cmds.getAttr(material+".bsdf")
        outFile.write(tabbedSpace + "     <bsdf type=\"diffuse\">\n")
        outFile.write(tabbedSpace + "          <srgb name=\"reflectance\" value=\"" + str(bsdf[0][0]) + " " + str(bsdf[0][1]) + " " + str(bsdf[0][2]) + "\"/>\n")
        outFile.write(tabbedSpace + "     </bsdf>\n")

    outFile.write(tabbedSpace + " </bsdf>\n")
    '''

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
                shaderElement = writeShader(connection, connection, outFile, tabbedSpace+"    ", depth+1)
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


def writeShaderRoughConductor(material, materialName, outFile, tabbedSpace="     ", depth=1):
    distribution = cmds.getAttr(material+".distribution", asString=True)
    alphaUV = cmds.getAttr(material+".alphaUV")
    alpha = cmds.getAttr(material+".alpha")
    conductorMaterial = cmds.getAttr(material+".material")
    extEta = cmds.getAttr(material+"extEta")

    '''
    outFile.write(tabbedSpace + " <bsdf type=\"roughconductor\" id=\"" + materialName + "\">\n")

    #We have different behaviour depending on the distribution
    outFile.write(tabbedSpace + "     <string name=\"distribution\" value=\"" + str(distribution) + "\"/>\n")
    #Using Anisotropic Phong, use alphaUV
    if distribution=="as":
        outFile.write(tabbedSpace + "     <float name=\"alphaU\" value=\"" + str(alphaUV[0]) + "\"/>\n")
        outFile.write(tabbedSpace + "     <float name=\"alphaV\" value=\"" + str(alphaUV[1]) + "\"/>\n")
    else:
        outFile.write(tabbedSpace + "     <float name=\"alpha\" value=\"" + str(alpha) + "\"/>\n")

    #write the rest
    outFile.write(tabbedSpace + "     <string name=\"material\" value=\"" + str(conductorMaterial) + "\"/>\n")
    outFile.write(tabbedSpace + "     <float name=\"extEta\" value=\"" + str(extEta) + "\"/>\n")
    outFile.write(tabbedSpace + " </bsdf>\n")
    '''

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

def writeShaderRoughDielectric(material, materialName, outFile, tabbedSpace="     ", depth=1):
    #Get all of the required attributes
    intIOR = cmds.getAttr(material+".intIOR")
    extIOR = cmds.getAttr(material+".extIOR")
    specularReflectance = cmds.getAttr(material+".specularReflectance")
    specularTransmittance = cmds.getAttr(material+".specularTransmittance")
    distribution = cmds.getAttr(material+".distribution", asString=True)
    alphaUV = cmds.getAttr(material+".alphaUV")
    alpha = cmds.getAttr(material+".alpha")

    '''
    #Write material
    outFile.write(tabbedSpace + " <bsdf type=\"dielectric\" id=\"" + materialName + "\">\n")
    
    #We have different behaviour depending on the distribution
    outFile.write(tabbedSpace + "     <string name=\"distribution\" value=\"" + str(distribution) + "\"/>\n")
    #Using Anisotropic Phong, use alphaUV
    if distribution=="as":
        outFile.write(tabbedSpace + "     <float name=\"alphaU\" value=\"" + str(alphaUV[0]) + "\"/>\n")
        outFile.write(tabbedSpace + "     <float name=\"alphaV\" value=\"" + str(alphaUV[1]) + "\"/>\n")
    else:
        outFile.write(tabbedSpace + "     <float name=\"alpha\" value=\"" + str(alpha) + "\"/>\n")

    outFile.write(tabbedSpace + "     <float name=\"intIOR\" value=\"" + str(intIOR) + "\"/>\n")
    outFile.write(tabbedSpace + "     <float name=\"extIOR\" value=\"" + str(extIOR) + "\"/>\n")
    outFile.write(tabbedSpace + "     <srgb name=\"specularReflectance\" value=\"" + str(specularReflectance[0][0]) + " " + str(specularReflectance[0][1]) + " " + str(specularReflectance[0][2]) + "\"/>\n")
    outFile.write(tabbedSpace + "     <srgb name=\"specularTransmittance\" value=\"" + str(specularTransmittance[0][0]) + " " + str(specularTransmittance[0][1]) + " " + str(specularTransmittance[0][2]) + "\"/>\n")
    outFile.write(tabbedSpace + " </bsdf>\n\n")
    '''

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


def writeShaderRoughDiffuse(material, materialName, outFile, tabbedSpace="     ", depth=1):
    reflectance = cmds.getAttr(material+".reflectance")
    alpha = cmds.getAttr(material+".alpha")
    useFastApprox = cmds.getAttr(material+".useFastApprox")
    useFastApproxText = 'true' if useFastApprox else 'false'

    '''
    outFile.write(tabbedSpace + " <bsdf type=\"roughdiffuse\" id=\"" + materialName + "\">\n")
    outFile.write(tabbedSpace + "     <srgb name=\"reflectance\" value=\"" + str(reflectance[0][0]) + " " + str(reflectance[0][1]) + " " + str(reflectance[0][2]) + "\"/>\n")
    outFile.write(tabbedSpace + "     <float name=\"alpha\" value=\"" + str(alpha) + "\"/>\n")
    outFile.write(tabbedSpace + "     <boolean name=\"useFastApprox\" value=\"" + str(useFastApprox) + "\"/>\n")
    outFile.write(tabbedSpace + " </bsdf>\n")
    '''

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

    # Write structure
    #writeElement(outFile, elementDict, depth)

    return elementDict

def writeShaderRoughPlastic(material, materialName, outFile, tabbedSpace="     ", depth=1):
    distribution = cmds.getAttr(material+".distribution", asString=True)
    alpha = cmds.getAttr(material+".alpha")
    intIOR = cmds.getAttr(material+".intIOR")
    extIOR = cmds.getAttr(material+".extIOR")
    specularReflectance = cmds.getAttr(material+".specularReflectance")
    diffuseReflectance = cmds.getAttr(material+".diffuseReflectance")

    '''
    outFile.write(tabbedSpace + " <bsdf type=\"roughplastic\" id=\"" + materialName + "\">\n")
    outFile.write(tabbedSpace + "     <string name=\"distribution\" value=\"" + str(distribution) + "\"/>\n")
    outFile.write(tabbedSpace + "     <float name=\"alpha\" value=\"" + str(alpha) + "\"/>\n")
    outFile.write(tabbedSpace + "     <float name=\"intIOR\" value=\"" + str(intIOR) + "\"/>\n")
    outFile.write(tabbedSpace + "     <float name=\"extIOR\" value=\"" + str(extIOR) + "\"/>\n")
    outFile.write(tabbedSpace + "     <srgb name=\"specularReflectance\" value=\"" + str(specularReflectance[0][0]) + " " + str(specularReflectance[0][1]) + " " + str(specularReflectance[0][2]) + "\"/>\n")
    outFile.write(tabbedSpace + "     <srgb name=\"diffuseReflectance\" value=\"" + str(diffuseReflectance[0][0]) + " " + str(diffuseReflectance[0][1]) + " " + str(diffuseReflectance[0][2]) + "\"/>\n")
    outFile.write(tabbedSpace + " </bsdf>\n")
    '''

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

    # Write structure
    #writeElement(outFile, elementDict, depth)

    return elementDict


def writeShaderThinDielectric(material, materialName, outFile, tabbedSpace="     ", depth=1):
    #Get all of the required attributes
    intIOR = cmds.getAttr(material+".intIOR")
    extIOR = cmds.getAttr(material+".extIOR")

    '''
    #Write material
    outFile.write(tabbedSpace + " <bsdf type=\"thindielectric\" id=\"" + materialName + "\">\n")
    outFile.write(tabbedSpace + "     <float name=\"intIOR\" value=\"" + str(intIOR) + "\"/>\n")
    outFile.write(tabbedSpace + "     <float name=\"extIOR\" value=\"" + str(extIOR) + "\"/>\n")
    outFile.write(tabbedSpace + " </bsdf>\n\n")
    '''

    # Create a structure to be written
    elementDict = {'type':'bsdf'}
    elementDict['attributes'] = {'type':'thindielectric', 'id':materialName}

    elementDict['children'] = []
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'intIOR', 'value':str(intIOR) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'extIOR', 'value':str(extIOR) } } )

    # Write structure
    #writeElement(outFile, elementDict, depth)

    return elementDict


def writeShaderWard(material, materialName, outFile, tabbedSpace="     ", depth=1):
    variant = cmds.getAttr(material+".variant", asString=True)
    alphaUV = cmds.getAttr(material+".alphaUV")
    specularReflectance = cmds.getAttr(material+".specularReflectance")
    diffuseReflectance = cmds.getAttr(material+".diffuseReflectance")

    '''
    outFile.write(tabbedSpace + " <bsdf type=\"phong\" id=\"" + materialName + "\">\n")
    outFile.write(tabbedSpace + "     <string name=\"variant\" value=\"" + str(variant) + "\"/>\n")
    outFile.write(tabbedSpace + "     <float name=\"alphaU\" value=\"" + str(alphaUV[0][0]) + "\"/>\n")
    outFile.write(tabbedSpace + "     <float name=\"alphaV\" value=\"" + str(alphaUV[0][1]) + "\"/>\n")
    outFile.write(tabbedSpace + "     <srgb name=\"specularReflectance\" value=\"" + str(specularReflectance[0][0]) + " " + str(specularReflectance[0][1]) + " " + str(specularReflectance[0][2]) + "\"/>\n")
    outFile.write(tabbedSpace + "     <srgb name=\"diffuseReflectance\" value=\"" + str(diffuseReflectance[0][0]) + " " + str(diffuseReflectance[0][1]) + " " + str(diffuseReflectance[0][2]) + "\"/>\n")
    outFile.write(tabbedSpace + " </bsdf>\n")
    '''

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

    # Write structure
    #writeElement(outFile, elementDict, depth)

    return elementDict

def writeShaderIrawan(material, materialName, outFile, tabbedSpace="     ", depth=1):
    filename = cmds.getAttr(material+".filename", asString=True)
    repeatu = cmds.getAttr(material+".repeatu")
    repeatv = cmds.getAttr(material+".repeatv")
    warpkd = cmds.getAttr(material+".warpkd")
    warpks = cmds.getAttr(material+".warpks")
    weftkd = cmds.getAttr(material+".weftkd")
    weftks = cmds.getAttr(material+".weftks")

    '''
    outFile.write(tabbedSpace + " <bsdf type=\"irawan\" id=\"" + materialName + "\">\n")
    outFile.write(tabbedSpace + "     <string name=\"filename\" value=\"" + filename + "\"/>\n")
    outFile.write(tabbedSpace + "     <float name=\"repeatU\" value=\"" + str(repeatu) + "\"/>\n")
    outFile.write(tabbedSpace + "     <float name=\"repeatV\" value=\"" + str(repeatv) + "\"/>\n")
    outFile.write(tabbedSpace + "     <rgb name=\"warp_kd\" value=\"" + str(warpkd[0][0]) + " " + str(warpkd[0][1]) + " " + str(warpkd[0][2]) + "\"/>\n")
    outFile.write(tabbedSpace + "     <rgb name=\"warp_ks\" value=\"" + str(warpks[0][0]) + " " + str(warpks[0][1]) + " " + str(warpks[0][2]) + "\"/>\n")
    outFile.write(tabbedSpace + "     <rgb name=\"weft_kd\" value=\"" + str(weftkd[0][0]) + " " + str(weftkd[0][1]) + " " + str(weftkd[0][2]) + "\"/>\n")
    outFile.write(tabbedSpace + "     <rgb name=\"weft_ks\" value=\"" + str(weftks[0][0]) + " " + str(weftks[0][1]) + " " + str(weftks[0][2]) + "\"/>\n")
    outFile.write(tabbedSpace + " </bsdf>\n")
    '''

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

    # Write structure
    #writeElement(outFile, elementDict, depth)

    return elementDict


def writeShaderObjectAreaLight(material, materialName, outFile, tabbedSpace="     ", depth=1):
    color = cmds.getAttr(material+".radiance")
    samplingWeight = cmds.getAttr(material+".samplingWeight")

    '''
    outFile.write(tabbedSpace + " <emitter type=\"area\" id=\"" + materialName + "\">\n")
    outFile.write(tabbedSpace + "     <rgb name=\"radiance\" value=\"" + str(color[0][0]) + " " + str(color[0][1]) + " " + str(color[0][2]) + "\"/>\n")
    outFile.write(tabbedSpace + "     <float name=\"samplingWeight\" value=\"" + str(samplingWeight) + "\"/>\n")
    outFile.write(tabbedSpace + " </emitter>\n")
    '''

    # Create a structure to be written
    elementDict = {'type':'emitter'}
    elementDict['attributes'] = {'type':'area', 'id':materialName}

    elementDict['children'] = []
    elementDict['children'].append( { 'type':'rgb', 
        'attributes':{ 'name':'radiance', 'value':str(color[0][0]) + " " + str(color[0][1]) + " " + str(color[0][2]) } } )
    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'samplingWeight', 'value':str(samplingWeight) } } )

    # Write structure
    #writeElement(outFile, elementDict, depth)

    return elementDict

def writeShaderTwoSided(material, materialName, outFile, tabbedSpace="     ", depth=1):
    '''
    outFile.write(tabbedSpace + " <bsdf type=\"twosided\" id=\"" + materialName + "\">\n")

    #Nested bsdf
    connections = cmds.listConnections(material, connections=True)
    for i in range(len(connections)):
        if i%2==1:
            connection = connections[i]
            connectionType = cmds.nodeType(connection)
            if connectionType in materialNodeTypes and connections[i-1]==material+".bsdf":
                #We've found the nested bsdf, so write it
                writeShader(connection, outFile, tabbedSpace+"    ", depth+1)

    outFile.write(tabbedSpace + " </bsdf>\n")
    '''

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
                childElement = writeShader(connection, connection, outFile, tabbedSpace+"    ", depth+1)

                elementDict['children'].append( { 'type':'ref', 
                    'attributes':{ 'id':childElement['attributes']['id'] } } )

    # Write structure
    #writeElement(outFile, elementDict, depth)

    return elementDict


'''
Write a surface material (material) to a Mitsuba scene file (outFile)
tabbedSpace is a string of blank space to account for recursive xml
'''
def writeShader(material, materialName, outFile, tabbedSpace="     ", depth=1):
    matType = cmds.nodeType(material)
    
    if matType=="MitsubaSmoothCoatingShader":
        elementDict = writeShaderSmoothCoating(material, materialName, outFile, tabbedSpace, depth)
    
    elif matType=="MitsubaConductorShader":
        elementDict = writeShaderConductor(material, materialName, outFile, tabbedSpace, depth)

    elif matType=="MitsubaDielectricShader":
        elementDict = writeShaderDielectric(material, materialName, outFile, tabbedSpace, depth)

    elif matType=="MitsubaDiffuseTransmitterShader":
        elementDict = writeShaderDiffuseTransmitter(material, materialName, outFile, tabbedSpace, depth)

    elif matType=="MitsubaDiffuseShader":
        elementDict = writeShaderDiffuse(material, materialName, outFile, tabbedSpace, depth)

    elif matType=="MitsubaPhongShader":
        elementDict = writeShaderPhong(material, materialName, outFile, tabbedSpace, depth)

    elif matType=="MitsubaPlasticShader":
        elementDict = writeShaderPlastic(material, materialName, outFile, tabbedSpace, depth)

    elif matType=="MitsubaRoughCoatingShader":
        elementDict = writeShaderRoughCoating(material, materialName, outFile, tabbedSpace, depth)

    elif matType=="MitsubaRoughConductorShader":
        elementDict = writeShaderRoughConductor(material, materialName, outFile, tabbedSpace, depth)

    elif matType=="MitsubaRoughDielectricShader":
        elementDict = writeShaderRoughDielectric(material, materialName, outFile, tabbedSpace, depth)

    elif matType=="MitsubaRoughDiffuseShader":
        elementDict = writeShaderRoughDiffuse(material, materialName, outFile, tabbedSpace, depth)

    elif matType=="MitsubaRoughPlasticShader":
        elementDict = writeShaderRoughPlastic(material, materialName, outFile, tabbedSpace, depth)

    elif matType=="MitsubaThinDielectricShader":
        elementDict = writeShaderThinDielectric(material, materialName, outFile, tabbedSpace, depth)

    elif matType=="MitsubaWardShader":
        elementDict = writeShaderWard(material, materialName, outFile, tabbedSpace, depth)

    elif matType=="MitsubaIrawanShader":
        elementDict = writeShaderIrawan(material, materialName, outFile, tabbedSpace, depth)

    elif matType=="MitsubaObjectAreaLightShader":
        elementDict = writeShaderObjectAreaLight(material, materialName, outFile, tabbedSpace, depth)

    elif matType=="MitsubaTwoSidedShader":
        elementDict = writeShaderTwoSided(material, materialName, outFile, tabbedSpace, depth, depth)

    else:
        print( "Unsupported Material : %s" % materialName )
        elementDict = {}

    return elementDict

    '''
    elif matType=="MitsubaBumpShader":
        print "bump"

    elif matType=="MitsubaMaskShader":
        print "mask"

    elif matType=="MitsubaMixtureShader":
        print "mixture"
    '''

'''
Write the appropriate integrator
'''
def writeIntegratorPathTracer(outFile, renderSettings, integratorMitsuba, depth=1):
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

    # Write structure
    #writeElement(outFile, elementDict, depth)

    return elementDict

def writeIntegratorBidirectionalPathTracer(outFile, renderSettings, integratorMitsuba, depth=1):
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

    # Write structure
    #writeElement(outFile, elementDict, depth)

    return elementDict


def writeIntegratorAmbientOcclusion(outFile, renderSettings, integratorMitsuba, depth=1):
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

    # Write structure
    #writeElement(outFile, elementDict, depth)

    return elementDict


def writeIntegratorDirectIllumination(outFile, renderSettings, integratorMitsuba, depth=1):
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

    # Write structure
    #writeElement(outFile, elementDict, depth)

    return elementDict


def writeIntegratorPhotonMap(outFile, renderSettings, integratorMitsuba, depth=1):
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

    # Write structure
    #writeElement(outFile, elementDict, depth)

    return elementDict


def writeIntegratorProgressivePhotonMap(outFile, renderSettings, integratorMitsuba, depth=1):
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

    '''
    outFile.write(" <integrator type=\"%s\">\n" % integratorMitsuba)

    outFile.write("     <integer name=\"maxDepth\" value=\"" + str(iProgressivePhotonMapMaxDepth) + "\"/>\n")
    outFile.write("     <integer name=\"photonCount\" value=\"" + str(iProgressivePhotonMapPhotonCount) + "\"/>\n")
    outFile.write("     <float name=\"initialRadius\" value=\"" + str(iProgressivePhotonMapInitialRadius) + "\"/>\n")
    outFile.write("     <float name=\"alpha\" value=\"" + str(iProgressivePhotonMapAlpha) + "\"/>\n")
    outFile.write("     <integer name=\"granularity\" value=\"" + str(iProgressivePhotonMapGranularity) + "\"/>\n")
    outFile.write("     <integer name=\"rrDepth\" value=\"" + str(iProgressivePhotonMapRRDepth) + "\"/>\n")    
    outFile.write("     <integer name=\"maxPasses\" value=\"" + str(iProgressivePhotonMapMaxPasses) + "\"/>\n")    

    outFile.write(" </integrator>\n\n\n")
    '''

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

    # Write structure
    #writeElement(outFile, elementDict, depth)

    return elementDict


def writeIntegratorPrimarySampleSpaceMetropolisLightTransport(outFile, renderSettings, integratorMitsuba, depth=1):
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

    '''
    outFile.write(" <integrator type=\"%s\">\n" % integratorMitsuba)

    outFile.write("     <boolean name=\"bidirectional\" value=\"%s\"/>\n" % iPrimarySampleSpaceMetropolisLightTransportBidirectionalText)
    outFile.write("     <integer name=\"maxDepth\" value=\"" + str(iPrimarySampleSpaceMetropolisLightTransportMaxDepth) + "\"/>\n")
    outFile.write("     <integer name=\"directSamples\" value=\"" + str(iPrimarySampleSpaceMetropolisLightTransportDirectSamples) + "\"/>\n")
    outFile.write("     <integer name=\"rrDepth\" value=\"" + str(iPrimarySampleSpaceMetropolisLightTransportRRDepth) + "\"/>\n")
    outFile.write("     <integer name=\"luminanceSamples\" value=\"" + str(iPrimarySampleSpaceMetropolisLightTransportLuminanceSamples) + "\"/>\n")
    outFile.write("     <boolean name=\"twoStage\" value=\"%s\"/>\n" % iPrimarySampleSpaceMetropolisLightTransportTwoStageText)
    outFile.write("     <float name=\"pLarge\" value=\"" + str(iPrimarySampleSpaceMetropolisLightTransportPLarge) + "\"/>\n")  

    outFile.write(" </integrator>\n\n\n")
    '''

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

    # Write structure
    #writeElement(outFile, elementDict, depth)

    return elementDict


def writeIntegratorPathSpaceMetropolisLightTransport(outFile, renderSettings, integratorMitsuba, depth=1):
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

    '''
    outFile.write(" <integrator type=\"%s\">\n" % integratorMitsuba)

    outFile.write("     <integer name=\"maxDepth\" value=\"" + str(iPathSpaceMetropolisLightTransportMaxDepth) + "\"/>\n")
    outFile.write("     <integer name=\"directSamples\" value=\"" + str(iPathSpaceMetropolisLightTransportDirectSamples) + "\"/>\n")
    outFile.write("     <integer name=\"luminanceSamples\" value=\"" + str(iPathSpaceMetropolisLightTransportLuminanceSamples) + "\"/>\n")
    outFile.write("     <boolean name=\"twoStage\" value=\"%s\"/>\n" % iPathSpaceMetropolisLightTransportTwoStageText)
    outFile.write("     <boolean name=\"bidirectionalMutation\" value=\"%s\"/>\n" % iPathSpaceMetropolisLightTransportBidirectionalMutationText)
    outFile.write("     <boolean name=\"lensPerturbation\" value=\"%s\"/>\n" % iPathSpaceMetropolisLightTransportLensPurturbationText)
    outFile.write("     <boolean name=\"multiChainPerturbation\" value=\"%s\"/>\n" % iPathSpaceMetropolisLightTransportMultiChainPurturbationText)
    outFile.write("     <boolean name=\"causticPerturbation\" value=\"%s\"/>\n" % iPathSpaceMetropolisLightTransportCausticPurturbationText)
    outFile.write("     <boolean name=\"manifoldPerturbation\" value=\"%s\"/>\n" % iPathSpaceMetropolisLightTransportManifoldPurturbationText)
    outFile.write("     <float name=\"lambda\" value=\"" + str(iPathSpaceMetropolisLightTransportLambda) + "\"/>\n")  

    outFile.write(" </integrator>\n\n\n")
    '''

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

    # Write structure
    #writeElement(outFile, elementDict, depth)

    return elementDict


def writeIntegratorEnergyRedistributionPathTracing(outFile, renderSettings, integratorMitsuba, depth=1):
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

    '''
    outFile.write(" <integrator type=\"%s\">\n" % integratorMitsuba)

    outFile.write("     <integer name=\"maxDepth\" value=\"" + str(iEnergyRedistributionPathTracingMaxDepth) + "\"/>\n")
    outFile.write("     <float name=\"numChains\" value=\"" + str(iEnergyRedistributionPathTracingNumChains) + "\"/>\n")
    outFile.write("     <integer name=\"maxChains\" value=\"" + str(iEnergyRedistributionPathTracingMaxChains) + "\"/>\n")
    outFile.write("     <integer name=\"directSamples\" value=\"" + str(iEnergyRedistributionPathTracingDirectSamples) + "\"/>\n")
    outFile.write("     <integer name=\"chainLength\" value=\"" + str(iEnergyRedistributionPathTracingChainLength) + "\"/>\n")
    outFile.write("     <boolean name=\"lensPerturbation\" value=\"%s\"/>\n" % iEnergyRedistributionPathTracingLensPerturbationText)
    outFile.write("     <boolean name=\"multiChainPerturbation\" value=\"%s\"/>\n" % iEnergyRedistributionPathTracingMultiChainPerturbationText)
    outFile.write("     <boolean name=\"causticPerturbation\" value=\"%s\"/>\n" % iEnergyRedistributionPathTracingCausticPerturbationText)
    outFile.write("     <boolean name=\"manifoldPerturbation\" value=\"%s\"/>\n" % iEnergyRedistributionPathTracingManifoldPerturbationText)
    outFile.write("     <float name=\"lambda\" value=\"" + str(iEnergyRedistributionPathTracingLambda) + "\"/>\n")  

    outFile.write(" </integrator>\n\n\n")
    '''

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

    # Write structure
    #writeElement(outFile, elementDict, depth)

    return elementDict

def writeIntegratorAdjointParticleTracer(outFile, renderSettings, integratorMitsuba, depth=1):
    # Get values from the scene
    iAdjointParticleTracerUseInfiniteDepth = cmds.getAttr("%s.%s" % (renderSettings, "iAdjointParticleTracerUseInfiniteDepth"))
    iAdjointParticleTracerMaxDepth = cmds.getAttr("%s.%s" % (renderSettings, "iAdjointParticleTracerMaxDepth"))
    iAdjointParticleTracerRRDepth = cmds.getAttr("%s.%s" % (renderSettings, "iAdjointParticleTracerRRDepth"))
    iAdjointParticleTracerGranularity = cmds.getAttr("%s.%s" % (renderSettings, "iAdjointParticleTracerGranularity"))
    iAdjointParticleTracerBruteForce = cmds.getAttr("%s.%s" % (renderSettings, "iAdjointParticleTracerBruteForce"))

    iAdjointParticleTracerMaxDepth = -1 if iAdjointParticleTracerUseInfiniteDepth else iAdjointParticleTracerMaxDepth
    iAdjointParticleTracerBruteForceText = 'true' if iAdjointParticleTracerBruteForce else 'false'

    '''
    outFile.write(" <integrator type=\"%s\">\n" % integratorMitsuba)

    outFile.write("     <integer name=\"maxDepth\" value=\"" + str(iAdjointParticleTracerMaxDepth) + "\"/>\n")
    outFile.write("     <integer name=\"rrDepth\" value=\"" + str(iAdjointParticleTracerRRDepth) + "\"/>\n")
    outFile.write("     <integer name=\"granularity\" value=\"" + str(iAdjointParticleTracerGranularity) + "\"/>\n")
    outFile.write("     <boolean name=\"bruteForce\" value=\"%s\"/>\n" % iAdjointParticleTracerBruteForceText)

    outFile.write(" </integrator>\n\n\n")
    '''

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

    # Write structure
    #writeElement(outFile, elementDict, depth)

    return elementDict

def writeIntegratorVirtualPointLight(outFile, renderSettings, integratorMitsuba, depth=1):
    # Get values from the scene
    iVirtualPointLightUseInfiniteDepth = cmds.getAttr("%s.%s" % (renderSettings, "iVirtualPointLightUseInfiniteDepth"))
    iVirtualPointLightMaxDepth = cmds.getAttr("%s.%s" % (renderSettings, "iVirtualPointLightMaxDepth"))
    iVirtualPointLightShadowMapResolution = cmds.getAttr("%s.%s" % (renderSettings, "iVirtualPointLightShadowMapResolution"))
    iVirtualPointLightClamping = cmds.getAttr("%s.%s" % (renderSettings, "iVirtualPointLightClamping"))

    iVirtualPointLightMaxDepth = -1 if iVirtualPointLightUseInfiniteDepth else iVirtualPointLightMaxDepth

    '''
    outFile.write(" <integrator type=\"%s\">\n" % integratorMitsuba)

    outFile.write("     <integer name=\"maxDepth\" value=\"" + str(iVirtualPointLightMaxDepth) + "\"/>\n")
    outFile.write("     <integer name=\"shadowMapResolution\" value=\"" + str(iVirtualPointLightShadowMapResolution) + "\"/>\n")
    outFile.write("     <float name=\"clamping\" value=\"" + str(iVirtualPointLightClamping) + "\"/>\n")

    outFile.write(" </integrator>\n\n\n")
    '''

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

    # Write structure
    #writeElement(outFile, elementDict, depth)

    return elementDict


def writeIntegrator(outFile, renderSettings, depth=1):
    integratorMaya = cmds.getAttr("%s.%s" % (renderSettings, "integrator")).replace('_', ' ')

    mayaUINameToMitsubaName = {
        "Ambient Occlusion" : "ao",
        "Direct_Illumination" : "direct",
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

    #
    # Integrators that can operate independent of the Render Settings UI
    #
    mayaUINameToIntegratorFunction = {
        "Ambient Occlusion" : writeIntegratorAmbientOcclusion,
        "Direct_Illumination" : writeIntegratorDirectIllumination,
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

    integratorElement = writeIntegratorFunction(outFile, renderSettings, integratorMitsuba, depth)

    return integratorElement

'''
Write image sample generator
'''
def writeSampler(outFile, frameNumber, renderSettings):
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
   
def writeFilm(outFile, frameNumber, renderSettings):
    #Resolution
    imageWidth = cmds.getAttr("defaultResolution.width")
    imageHeight = cmds.getAttr("defaultResolution.height")

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

    #print( "Reconstruction Filter : %s" % reconstructionFilterMitsuba )

    elementDict = {'type':'film'}
    elementDict['attributes'] = {'type':'hdrfilm'}

    elementDict['children'] = []
    elementDict['children'].append( { 'type':'integer', 'attributes':{ 'name':'height', 'value':str(imageHeight) } } )
    elementDict['children'].append( { 'type':'integer', 'attributes':{ 'name':'width', 'value':str(imageWidth) } } )
    elementDict['children'].append( { 'type':'rfilter', 'attributes':{ 'type':reconstructionFilterMitsuba } } )
    elementDict['children'].append( { 'type':'boolean', 'attributes':{ 'name':'banner', 'value':'false' } } )

    return elementDict

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

def writeSensor(outFile, frameNumber, renderSettings, depth=1):
    # Find renderable camera
    rCamShape = getRenderableCamera()

    # Type
    camType = "perspective"
    if cmds.getAttr(rCamShape+".depthOfField"):
        camType = "thinlens"
    elif cmds.getAttr(rCamShape+".orthographic"):
        camType = "orthographic"

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

    # Write Sampler
    samplerDict = writeSampler(outFile, frameNumber, renderSettings)

    # Write Film
    filmDict = writeFilm(outFile, frameNumber, renderSettings)

    # Write Camera
    elementDict = {'type':'sensor'}
    elementDict['attributes'] = {'type':camType}

    elementDict['children'] = []

    if camType in ["thinlens", "perspective"]:
        if camType == "thinlens":
            elementDict['children'].append( { 'type':'float', 
                'attributes':{ 'name':'apertureRadius', 'value':str(apertureRadius) } } )
            elementDict['children'].append( { 'type':'float', 
                'attributes':{ 'name':'focusDistance', 'value':str(focusDistance) } } )
        elementDict['children'].append( { 'type':'float', 
            'attributes':{ 'name':'fov', 'value':str(fov) } } )
        elementDict['children'].append( { 'type':'string', 
            'attributes':{ 'name':'fovAxis', 'value':'x' } } )

    elementDict['children'].append( { 'type':'float', 
        'attributes':{ 'name':'nearClip', 'value':str(nearClip) } } )

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
    elementDict['children'].append(samplerDict)
    elementDict['children'].append(filmDict)

    #writeElement(outFile, elementDict, depth)

    return elementDict

def writeLightDirectional(light):
    intensity = cmds.getAttr(light+".intensity")
    color = cmds.getAttr(light+".color")[0]
    irradiance = [0,0,0]
    for i in range(3):
        irradiance[i] = intensity*color[i]

    matrix = cmds.getAttr(light+".worldMatrix")
    lightDir = [-matrix[8],-matrix[9],-matrix[10]]

    '''
    outFile.write(" <emitter type=\"directional\">\n")
    outFile.write("     <srgb name=\"irradiance\" value=\"" + str(irradiance[0]) + " " + str(irradiance[1]) + " " + str(irradiance[2]) + "\"/>\n")
    outFile.write("     <vector name=\"direction\" x=\"" + str(lightDir[0]) + "\" y=\"" + str(lightDir[1]) + "\" z=\"" + str(lightDir[2]) + "\"/>\n")
    outFile.write(" </emitter>\n")
    '''

    # Create a structure to be written
    elementDict = {'type':'emitter'}
    elementDict['attributes'] = {'type':'directional'}

    elementDict['children'] = []

    elementDict['children'].append( { 'type':'srgb', 
        'attributes':{ 'name':'irradiance', 'value':str(irradiance[0]) + " " + str(irradiance[1]) + " " + str(irradiance[2]) } } )
    elementDict['children'].append( { 'type':'vector', 
        'attributes':{ 'name':'direction', 'value':str(lightDir[0]) + "\" y=\"" + str(lightDir[1]) + "\" z=\"" + str(lightDir[2]) } } )

    return elementDict


def writeLightPoint(light):
    intensity = cmds.getAttr(light+".intensity")
    color = cmds.getAttr(light+".color")[0]
    irradiance = [0,0,0]
    for i in range(3):
        irradiance[i] = intensity*color[i]

    matrix = cmds.getAttr(light+".worldMatrix")
    position = [matrix[12],matrix[13],matrix[14]]

    '''
    outFile.write(" <emitter type=\"point\">\n")
    outFile.write("     <srgb name=\"intensity\" value=\"" + str(irradiance[0]) + " " + str(irradiance[1]) + " " + str(irradiance[2]) + "\"/>\n")
    outFile.write("     <point name=\"position\" x=\"" + str(position[0]) + "\" y=\"" + str(position[1]) + "\" z=\"" + str(position[2]) + "\"/>\n")
    outFile.write(" </emitter>\n")
    '''

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

    '''
    outFile.write(" <emitter type=\"spot\">\n")
    outFile.write("     <rgb name=\"intensity\" value=\"" + str(irradiance[0]) + " " + str(irradiance[1]) + " " + str(irradiance[2]) + "\"/>\n")
    outFile.write("     <float name=\"cutoffAngle\" value=\"" + str(coneAngle + penumbraAngle) + "\"/>\n")
    outFile.write("     <float name=\"beamWidth\" value=\"" + str(coneAngle) + "\"/>\n")

    outFile.write("     <transform name=\"toWorld\">\n")
    outFile.write("         <translate x=\"" + str(position[0]) + "\" y=\"" + str(position[1]) + "\" z=\"" + str(position[2]) + "\"/>\n")
    outFile.write("         <rotate y=\"1\" angle=\"" + str(180.0) + "\"/>\n")
    if rotation[0] != 0.0:
        outFile.write("         <rotate x=\"1\" angle=\"" + str(rotation[0]) + "\"/>\n")
    if rotation[1] != 0.0:
        outFile.write("         <rotate y=\"1\" angle=\"" + str(rotation[1]) + "\"/>\n")
    if rotation[2] != 0.0:
        outFile.write("         <rotate z=\"1\" angle=\"" + str(rotation[2]) + "\"/>\n")
    outFile.write("     </transform>\n")

    outFile.write(" </emitter>\n")
    '''

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

    transformDict['children'].append( { 'type':'translate', 
        'attributes':{ 'x':str(position[0]), 'y':str(position[1]), 'z':str(position[2]) } } )
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

    '''
    outFile.write(" <emitter type=\"%s\">\n" % emitterType)

    outFile.write("     <float name=\"turbidity\" value=\"" + str(turbidity) + "\"/>\n")
    outFile.write("     <srgb name=\"albedo\" value=\"" + str(albedo[0][0]) + " " + str(albedo[0][1]) + " " + str(albedo[0][2]) + "\"/>\n")
    outFile.write("     <integer name=\"year\" value=\"" + str(date[0][0]) + "\"/>\n")
    outFile.write("     <integer name=\"month\" value=\"" + str(date[0][1]) + "\"/>\n")
    outFile.write("     <integer name=\"day\" value=\"" + str(date[0][2]) + "\"/>\n")
    outFile.write("     <float name=\"hour\" value=\"" + str(time[0][0]) + "\"/>\n")
    outFile.write("     <float name=\"minute\" value=\"" + str(time[0][1]) + "\"/>\n")
    outFile.write("     <float name=\"second\" value=\"" + str(time[0][2]) + "\"/>\n")
    outFile.write("     <float name=\"latitude\" value=\"" + str(latitude) + "\"/>\n")
    outFile.write("     <float name=\"longitude\" value=\"" + str(longitude) + "\"/>\n")
    outFile.write("     <float name=\"timezone\" value=\"" + str(timezone) + "\"/>\n")
    outFile.write("     <float name=\"stretch\" value=\"" + str(stretch) + "\"/>\n")
    outFile.write("     <integer name=\"resolutionX\" value=\"" + str(resolution[0][1]) + "\"/>\n")
    outFile.write("     <integer name=\"resolutionY\" value=\"" + str(resolution[0][1]) + "\"/>\n")
    outFile.write("     <float name=\"sunScale\" value=\"" + str(sunScale) + "\"/>\n")
    outFile.write("     <float name=\"skyScale\" value=\"" + str(skyScale) + "\"/>\n")
    outFile.write("     <float name=\"sunRadiusScale\" value=\"" + str(sunRadiusScale) + "\"/>\n")

    outFile.write(" </emitter>\n")
    '''

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

            '''
            outFile.write(" <emitter type=\"envmap\">\n")
            outFile.write("     <string name=\"filename\" value=\"" + fileName + "\"/>\n")
            outFile.write("     <float name=\"scale\" value=\"" + str(scale) + "\"/>\n")
            outFile.write("     <float name=\"gamma\" value=\"" + str(gamma) + "\"/>\n")
            if cache:
                outFile.write("     <boolean name=\"cache\" value=\"true\"/>\n")
            else:
                outFile.write("     <boolean name=\"cache\" value=\"false\"/>\n")

            outFile.write("     <float name=\"samplingWeight\" value=\"" + str(samplingWeight) + "\"/>\n")

            outFile.write("     <transform name=\"toWorld\">\n")
            outFile.write("         <rotate x=\"1\" angle=\"" + str(rotate[0]) + "\"/>\n")
            outFile.write("         <rotate y=\"1\" angle=\"" + str(rotate[1]) + "\"/>\n")
            outFile.write("         <rotate z=\"1\" angle=\"" + str(rotate[2]) + "\"/>\n")
            outFile.write("     </transform>\n")
            outFile.write(" </emitter>\n")
            '''

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
            
            '''
            outFile.write(" <emitter type=\"constant\">\n")
            outFile.write("     <srgb name=\"radiance\" value=\"" + str(radiance[0][0]) + " " + str(radiance[0][1]) + " " + str(radiance[0][2]) + "\"/>\n")
            outFile.write("     <float name=\"samplingWeight\" value=\"" + str(samplingWeight) + "\"/>\n")
            outFile.write(" </emitter>\n")
            '''

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
def writeLights(outFile, depth=1):
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

    '''
    # Write lights
    if lightElements:
        outFile.write("\n\n\n")
        outFile.write("<!-- Start of lights -->")
        outFile.write("\n")
        outFile.write("\n")

        for lightElement in lightElements:
            writeElement(outFile, lightElement, depth)

        outFile.write("\n")
        outFile.write("\n")
        outFile.write("<!-- End of lights -->")
        outFile.write("\n\n\n")
    '''

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

def writeMaterials(outFile, geoms, depth = 1):
    writtenMaterials = []
    materialElements = []

    #Write the material for each piece of geometry in the scene
    for geom in geoms:
        material = getShader(geom)          #Gets the user define names of the shader
        materialType = cmds.nodeType(material)
        if materialType in materialNodeTypes:
            if material not in writtenMaterials:
                if "twosided" in cmds.listAttr(material) and cmds.getAttr(material+".twosided"):
                    '''
                    outFile.write("<bsdf type=\"twosided\" id=\"" + material + "\">\n")
                    writeShader(material, material+"InnerMaterial", outFile, "    ")
                    outFile.write("</bsdf>\n")
                    '''

                    # Create a structure to be written
                    elementDict = {'type':'bsdf'}
                    elementDict['attributes'] = {'type':'twosided', 'id':material}

                    elementDict['children'] = []

                    childElement = writeShader(material, material+"InnerMaterial", outFile, "    ", depth)
                    elementDict['children'].append(childElement)

                    #elementDict['children'].append( { 'type':'ref', 
                    #    'attributes':{ 'id':childElement['attributes']['id'] } } )
                    
                    # Write structure
                    #writeElement(outFile, elementDict, depth)
                    materialElements.append(elementDict)

                    #return elementDict
                else:
                    if materialType != "MitsubaObjectAreaLightShader":
                        materialElement = writeShader(material, material, outFile, "", depth)
                        materialElements.append( materialElement )

                writtenMaterials.append(material)
        
    #outFile.write("\n")
    #outFile.write("<!-- End of materials -->")
    #outFile.write("\n\n\n")

    return writtenMaterials, materialElements

def exportGeometry(geom, cwd):
    output = os.path.join(cwd, "renderData", geom + ".obj")
    cmds.select(geom)
    objFile = cmds.file(output, op=True, typ="OBJexport", options="groups=1;ptgroups=1;materials=0;smoothing=1;normals=1", exportSelected=True, force=True)
    return objFile

def findAndWriteMedium(outFile, geom, shader, depth=1):
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
        mediumElement = writeMedium(medium, outFile, "    ", depth)
    else:
        mediumElement = None

    return mediumElement

def writeShape(outFile, geom, shader, depth=1):
    shapeDict = {'type':'shape'}
    shapeDict['attributes'] = {'type':'obj'}

    shapeDict['children'] = []
    shapeDict['children'].append( { 'type':'string', 
        'attributes':{ 'name':'filename', 'value':geom + ".obj" } } )

    #outFile.write("    <shape type=\"obj\">\n")
    #outFile.write("        <string name=\"filename\" value=\"" + geom + ".obj\"/>\n")

    if cmds.nodeType(shader) in materialNodeTypes:
        # Check for area lights
        if cmds.nodeType(shader) == "MitsubaObjectAreaLightShader":
            shaderElement = writeShader(shader, shader, outFile, "", depth)
            shapeDict['children'].append(shaderElement)

        # Otherwise refer to the already written material
        else:
            #outFile.write("        <ref id=\"" + shader + "\"/>\n")
            refDict = {'type':'ref'}
            refDict['attributes'] = {'id':shader}
            shapeDict['children'].append(refDict)

        # Write volume definition, if one exists
        mediumDict = findAndWriteMedium(outFile, geom, shader, depth)
        if mediumDict:
            shapeDict['children'].append(mediumDict)

    elif cmds.nodeType(shader) == "MitsubaVolume":
        volumeElement = writeVolume(outFile, cwd, "    ", shader, geom, depth)
        if volumeElement:
            shapeDict['children'].append(volumeElement)
    
    #outFile.write("    </shape>\n\n")

    return shapeDict


def writeGeometryAndMaterials(outFile, cwd, depth=1):
    geoms = getRenderableGeometry()

    writtenMaterials, materialElements = writeMaterials(outFile, geoms, depth)

    geoFiles = []
    shapeElements = []

    #Write each piece of geometry with references to materials
    for geom in geoms:
        shader = getShader(geom)

        exportedGeo = exportGeometry(geom, cwd)
        geoFiles.append( exportedGeo )

        shapeElement = writeShape(outFile, geom, shader, depth)
        shapeElements.append(shapeElement)

    #outFile.write("<!-- End of geometry -->")
    #outFile.write("\n\n\n")

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
def writeVolume(outFile, cwd, tabbedSpace, material, geom, depth):
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

    volFileName = cwd + "test.vol"
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

    '''
    outFile.write(tabbedSpace + "<medium type=\"heterogeneous\" name=\"interior\">\n")
    outFile.write(tabbedSpace + "    <string name=\"method\" value=\"woodcock\"/>\n")
    outFile.write(tabbedSpace + "    <volume name=\"density\" type=\"gridvolume\">\n")
    outFile.write(tabbedSpace + "        <string name=\"filename\" value=\"" + volFileName + "\"/>\n")
    outFile.write(tabbedSpace + "    </volume>\n")
    outFile.write(tabbedSpace + "    <volume name=\"albedo\" type=\"constvolume\">\n")
    outFile.write(tabbedSpace + "        <spectrum name=\"value\" value=\"0.9\"/>\n")
    outFile.write(tabbedSpace + "    </volume>\n")
    outFile.write(tabbedSpace + "</medium>\n")
    '''

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

    #writeElement(outFile, mediumDict, depth)

    return mediumDict

def writeScene(outFileName, outDir, renderSettings):
    outFile = open(outFileName, 'w+')

    #Scene stuff
    outFile.write("<?xml version=\'1.0\' encoding=\'utf-8\'?>\n")

    sceneElement = {'type':'scene'}
    sceneElement['attributes'] = {'version':'0.5.0'}
    sceneElement['children'] = []

    #Get integrator
    integratorElement = writeIntegrator(outFile, renderSettings)
    sceneElement['children'].append(integratorElement)

    #Get sensor : camera, sampler, and film
    frameNumber = int(cmds.currentTime(query=True))
    sensorElement = writeSensor(outFile, frameNumber, renderSettings)
    sceneElement['children'].append(sensorElement)

    #Get lights
    lightElements = writeLights(outFile)
    if lightElements:
        sceneElement['children'].extend(lightElements)

    #Get geom and material assignments
    (exportedGeometryFiles, shapeElements, materialElements) = writeGeometryAndMaterials(outFile, outDir)
    if materialElements:
        sceneElement['children'].extend(materialElements)

    if shapeElements:
        sceneElement['children'].extend(shapeElements)

    # Write the structure to disk
    writeElement(outFile, sceneElement)

    outFile.close()

    return exportedGeometryFiles
