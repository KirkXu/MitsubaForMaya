import getpass
import inspect
import os
import re
import struct
import sys
import time

import maya.cmds as cmds
import maya.mel as mel
import maya.OpenMaya as OpenMaya
import maya.OpenMayaMPx as OpenMayaMPx

from process import Process

import MitsubaRenderSettingsUI
kPluginCmdName = "mitsuba"

pluginDir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
sys.path.append(pluginDir)

# Import modules for material plugins
import MitsubaRenderSettings

import bump
import coating
import conductor
import dielectric
import difftrans
import diffuse
import mask
import mixturebsdf
import phong
import plastic
import roughcoating
import roughconductor
import roughdielectric
import roughdiffuse
import roughplastic
import thindielectric
import twosided
import ward
import irawan
import homogeneous
import envmap
import sunsky
import arealight

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
    homogeneous,
    irawan,
    envmap,
    sunsky,
    arealight]

generalNodeModules = [
    MitsubaRenderSettings]

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
def writeMedium(medium, outFile, tabbedSpace):
    outFile.write(tabbedSpace + " <medium type=\"homogeneous\" name=\"interior\">\n")
    
    #check if we want to use sigmaA and sigmaT or sigmaT and albedo
    sigmaAS = cmds.getAttr(medium+".sigmaAS")
    if sigmaAS:
        sigmaA = cmds.getAttr(medium+".sigmaA")
        sigmaS = cmds.getAttr(medium+".sigmaS")
        outFile.write(tabbedSpace + "      <rgb name=\"sigmaA\" value=\"" + str(sigmaA[0][0]) + " " + str(sigmaA[0][1]) + " " + str(sigmaA[0][2]) + "\"/>\n")
        outFile.write(tabbedSpace + "      <rgb name=\"sigmaS\" value=\"" + str(sigmaS[0][0]) + " " + str(sigmaS[0][1]) + " " + str(sigmaS[0][2]) + "\"/>\n")
    else:
        sigmaT = cmds.getAttr(medium+".sigmaT")
        albedo = cmds.getAttr(medium+".albedo")
        outFile.write(tabbedSpace + "      <rgb name=\"sigmaT\" value=\"" + str(sigmaT[0][0]) + " " + str(sigmaT[0][1]) + " " + str(sigmaT[0][2]) + "\"/>\n")
        outFile.write(tabbedSpace + "      <rgb name=\"albedo\" value=\"" + str(albedo[0][0]) + " " + str(albedo[0][1]) + " " + str(albedo[0][2]) + "\"/>\n")

    scale = cmds.getAttr(medium+".scale")    
    outFile.write(tabbedSpace + "      <float name=\"scale\" value=\"" + str(scale) + "\"/>\n")
    outFile.write(tabbedSpace + " </medium>\n")

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

'''
Write a surface material (material) to a Mitsuba scene file (outFile)
tabbedSpace is a string of blank space to account for recursive xml
'''
def writeShader(material, materialName, outFile, tabbedSpace):
    matType = cmds.nodeType(material)
    
    if matType=="MitsubaBumpShader":
        print "bump"

    elif matType=="MitsubaSmoothCoatingShader":
        intIOR = cmds.getAttr(material+".intIOR")
        extIOR = cmds.getAttr(material+".extIOR")
        thickness = cmds.getAttr(material+".thickness")
        sigmaA = cmds.getAttr(material+".sigmaA")
        specularReflectance = cmds.getAttr(material+".specularReflectance")

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
                    writeShader(connection, connection, outFile, tabbedSpace+"    ")
                    hasNestedBSDF = True

        if not hasNestedBSDF:
            #Write a basic diffuse using the bsdf attribute
            bsdf = cmds.getAttr(material+".bsdf")
            outFile.write(tabbedSpace + "     <bsdf type=\"diffuse\">\n")
            outFile.write(tabbedSpace + "          <srgb name=\"reflectance\" value=\"" + str(bsdf[0][0]) + " " + str(bsdf[0][1]) + " " + str(bsdf[0][2]) + "\"/>\n")
            outFile.write(tabbedSpace + "     </bsdf>\n")

        outFile.write(tabbedSpace + " </bsdf>\n")
    
    elif matType=="MitsubaConductorShader":
        conductorMaterial = cmds.getAttr(material+".material", asString=True)
        extEta = cmds.getAttr(material+".extEta")
        outFile.write(tabbedSpace + " <bsdf type=\"conductor\"   id=\"" + materialName + "\">\n")
        outFile.write(tabbedSpace + "     <string name=\"material\" value=\"" + str(conductorMaterial) + "\"/>\n")
        outFile.write(tabbedSpace + "     <float name=\"extEta\" value=\"" + str(extEta) + "\"/>\n")
        outFile.write(tabbedSpace + " </bsdf>\n")

    elif matType=="MitsubaDielectricShader":
        #Get all of the required attributes
        intIOR = cmds.getAttr(material+".intIOR")
        extIOR = cmds.getAttr(material+".extIOR")

        #Write material
        outFile.write(tabbedSpace + " <bsdf type=\"dielectric\" id=\"" + materialName + "\">\n")
        outFile.write(tabbedSpace + "     <float name=\"intIOR\" value=\"" + str(intIOR) + "\"/>\n")
        outFile.write(tabbedSpace + "     <float name=\"extIOR\" value=\"" + str(extIOR) + "\"/>\n")
        outFile.write(tabbedSpace + " </bsdf>\n\n")

    elif matType=="MitsubaDiffuseTransmitterShader":
        transmittance = cmds.getAttr(material+".reflectance")
        outFile.write(tabbedSpace + " <bsdf type=\"diffuse\" id=\"" + materialName + "\">\n")
        outFile.write(tabbedSpace + "     <srgb name=\"reflectance\" value=\"" + str(transmittance[0][0]) + " " + str(transmittance[0][1]) + " " + str(transmittance[0][2]) + "\"/>\n")
        outFile.write(tabbedSpace + " </bsdf>\n")

    elif matType=="MitsubaDiffuseShader":
        outFile.write(tabbedSpace + " <bsdf type=\"diffuse\" id=\"" + materialName + "\">\n")

        #texture
        connectionAttr = "reflectance"
        fileTexture = getTextureFile(material, connectionAttr)

        if fileTexture:
            outFile.write(tabbedSpace + "     <texture type=\"bitmap\" name=\"reflectance\">\n")
            outFile.write(tabbedSpace + "         <string name=\"filename\" value=\"" + fileTexture + "\"/>")
            outFile.write(tabbedSpace + "     </texture>\n")
        else:
            reflectance = cmds.getAttr(material+".reflectance")
            outFile.write(tabbedSpace + "     <srgb name=\"reflectance\" value=\"" + str(reflectance[0][0]) + " " + str(reflectance[0][1]) + " " + str(reflectance[0][2]) + "\"/>\n")

        outFile.write(tabbedSpace + " </bsdf>\n")

    elif matType=="MitsubaMaskShader":
        print "mask"

    elif matType=="MitsubaMixtureShader":
        print "mixture"

    elif matType=="MitsubaPhongShader":
        exponent = cmds.getAttr(material+".exponent")
        specularReflectance = cmds.getAttr(material+".specularReflectance")
        diffuseReflectance = cmds.getAttr(material+".diffuseReflectance")

        outFile.write(tabbedSpace + " <bsdf type=\"phong\" id=\"" + materialName + "\">\n")
        outFile.write(tabbedSpace + "     <float name=\"exponent\" value=\"" + str(exponent) + "\"/>\n")
        outFile.write(tabbedSpace + "     <srgb name=\"specularReflectance\" value=\"" + str(specularReflectance[0][0]) + " " + str(specularReflectance[0][1]) + " " + str(specularReflectance[0][2]) + "\"/>\n")
        outFile.write(tabbedSpace + "     <srgb name=\"diffuseReflectance\" value=\"" + str(diffuseReflectance[0][0]) + " " + str(diffuseReflectance[0][1]) + " " + str(diffuseReflectance[0][2]) + "\"/>\n")
        outFile.write(tabbedSpace + " </bsdf>\n")

    elif matType=="MitsubaPlasticShader":
        intIOR = cmds.getAttr(material+".intIOR")
        extIOR = cmds.getAttr(material+".extIOR")
        specularReflectance = cmds.getAttr(material+".specularReflectance")
        diffuseReflectance = cmds.getAttr(material+".diffuseReflectance")

        outFile.write(tabbedSpace + " <bsdf type=\"plastic\" id=\"" + materialName + "\">\n")
        outFile.write(tabbedSpace + "     <float name=\"intIOR\" value=\"" + str(intIOR) + "\"/>\n")
        outFile.write(tabbedSpace + "     <float name=\"extIOR\" value=\"" + str(extIOR) + "\"/>\n")
        outFile.write(tabbedSpace + "     <srgb name=\"specularReflectance\" value=\"" + str(specularReflectance[0][0]) + " " + str(specularReflectance[0][1]) + " " + str(specularReflectance[0][2]) + "\"/>\n")
        outFile.write(tabbedSpace + "     <srgb name=\"diffuseReflectance\" value=\"" + str(diffuseReflectance[0][0]) + " " + str(diffuseReflectance[0][1]) + " " + str(diffuseReflectance[0][2]) + "\"/>\n")
        outFile.write(tabbedSpace + " </bsdf>\n")


    elif matType=="MitsubaRoughCoatingShader":
        distribution = cmds.getAttr(material+".distribution", asString=True)
        alpha = cmds.getAttr(material+".alpha")
        intIOR = cmds.getAttr(material+".intIOR")
        extIOR = cmds.getAttr(material+".extIOR")
        thickness = cmds.getAttr(material+".thickness")
        sigmaA = cmds.getAttr(material+".sigmaA")
        specularReflectance = cmds.getAttr(material+".specularReflectance")

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
                    writeShader(connection, connection, outFile, tabbedSpace+"    ")
                    hasNestedBSDF=True
        
        if not hasNestedBSDF:
            #Write a basic diffuse using the bsdf attribute
            bsdf = cmds.getAttr(material+".bsdf")
            outFile.write(tabbedSpace + "     <bsdf type=\"diffuse\">\n")
            outFile.write(tabbedSpace + "          <srgb name=\"reflectance\" value=\"" + str(bsdf[0][0]) + " " + str(bsdf[0][1]) + " " + str(bsdf[0][2]) + "\"/>\n")
            outFile.write(tabbedSpace + "     </bsdf>\n")

        outFile.write(tabbedSpace + " </bsdf>\n")

    elif matType=="MitsubaRoughConductorShader":
        outFile.write(tabbedSpace + " <bsdf type=\"roughconductor\" id=\"" + materialName + "\">\n")

        distribution = cmds.getAttr(material+".distribution", asString=True)
        #We have different behaviour depending on the distribution
        outFile.write(tabbedSpace + "     <string name=\"distribution\" value=\"" + str(distribution) + "\"/>\n")
        #Using Anisotropic Phong, use alphaUV
        if distribution=="as":
            alphaUV = cmds.getAttr(material+".alphaUV")
            outFile.write(tabbedSpace + "     <float name=\"alphaU\" value=\"" + str(alphaUV[0]) + "\"/>\n")
            outFile.write(tabbedSpace + "     <float name=\"alphaV\" value=\"" + str(alphaUV[1]) + "\"/>\n")
        else:
            alpha = cmds.getAttr(material+".alpha")
            outFile.write(tabbedSpace + "     <float name=\"alpha\" value=\"" + str(alpha) + "\"/>\n")

        #write the rest
        conductorMaterial = cmds.getAttr(material+".material")
        extEta = cmds.getAttr(material+"extEta")
        outFile.write(tabbedSpace + "     <string name=\"material\" value=\"" + str(conductorMaterial) + "\"/>\n")
        outFile.write(tabbedSpace + "     <float name=\"extEta\" value=\"" + str(extEta) + "\"/>\n")
        outFile.write(tabbedSpace + " </bsdf>\n")

    elif matType=="MitsubaRoughDielectricShader":
        #Get all of the required attributes
        intIOR = cmds.getAttr(material+".intIOR")
        extIOR = cmds.getAttr(material+".extIOR")
        specularReflectance = cmds.getAttr(material+".specularReflectance")
        specularTransmittance = cmds.getAttr(material+".specularTransmittance")

        #Write material
        outFile.write(tabbedSpace + " <bsdf type=\"dielectric\" id=\"" + materialName + "\">\n")
        
        distribution = cmds.getAttr(material+".distribution", asString=True)
        #We have different behaviour depending on the distribution
        outFile.write(tabbedSpace + "     <string name=\"distribution\" value=\"" + str(distribution) + "\"/>\n")
        #Using Anisotropic Phong, use alphaUV
        if distribution=="as":
            alphaUV = cmds.getAttr(material+".alphaUV")
            outFile.write(tabbedSpace + "     <float name=\"alphaU\" value=\"" + str(alphaUV[0]) + "\"/>\n")
            outFile.write(tabbedSpace + "     <float name=\"alphaV\" value=\"" + str(alphaUV[1]) + "\"/>\n")
        else:
            alpha = cmds.getAttr(material+".alpha")
            outFile.write(tabbedSpace + "     <float name=\"alpha\" value=\"" + str(alpha) + "\"/>\n")

        outFile.write(tabbedSpace + "     <float name=\"intIOR\" value=\"" + str(intIOR) + "\"/>\n")
        outFile.write(tabbedSpace + "     <float name=\"extIOR\" value=\"" + str(extIOR) + "\"/>\n")
        outFile.write(tabbedSpace + "     <srgb name=\"specularReflectance\" value=\"" + str(specularReflectance[0][0]) + " " + str(specularReflectance[0][1]) + " " + str(specularReflectance[0][2]) + "\"/>\n")
        outFile.write(tabbedSpace + "     <srgb name=\"specularTransmittance\" value=\"" + str(specularTransmittance[0][0]) + " " + str(specularTransmittance[0][1]) + " " + str(specularTransmittance[0][2]) + "\"/>\n")
        outFile.write(tabbedSpace + " </bsdf>\n\n")

    elif matType=="MitsubaRoughDiffuseShader":
        reflectance = cmds.getAttr(material+".reflectance")
        alpha = cmds.getAttr(material+".alpha")
        useFastApprox = cmds.getAttr(material+".useFastApprox")

        outFile.write(tabbedSpace + " <bsdf type=\"roughdiffuse\" id=\"" + materialName + "\">\n")
        outFile.write(tabbedSpace + "     <srgb name=\"reflectance\" value=\"" + str(reflectance[0][0]) + " " + str(reflectance[0][1]) + " " + str(reflectance[0][2]) + "\"/>\n")
        outFile.write(tabbedSpace + "     <float name=\"alpha\" value=\"" + str(alpha) + "\"/>\n")
        outFile.write(tabbedSpace + "     <boolean name=\"useFastApprox\" value=\"" + str(useFastApprox) + "\"/>\n")
        outFile.write(tabbedSpace + " </bsdf>\n")

    elif matType=="MitsubaRoughPlasticShader":
        distribution = cmds.getAttr(material+".distribution", asString=True)
        alpha = cmds.getAttr(material+".alpha")
        intIOR = cmds.getAttr(material+".intIOR")
        extIOR = cmds.getAttr(material+".extIOR")
        specularReflectance = cmds.getAttr(material+".specularReflectance")
        diffuseReflectance = cmds.getAttr(material+".diffuseReflectance")

        outFile.write(tabbedSpace + " <bsdf type=\"roughplastic\" id=\"" + materialName + "\">\n")
        outFile.write(tabbedSpace + "     <string name=\"distribution\" value=\"" + str(distribution) + "\"/>\n")
        outFile.write(tabbedSpace + "     <float name=\"alpha\" value=\"" + str(alpha) + "\"/>\n")
        outFile.write(tabbedSpace + "     <float name=\"intIOR\" value=\"" + str(intIOR) + "\"/>\n")
        outFile.write(tabbedSpace + "     <float name=\"extIOR\" value=\"" + str(extIOR) + "\"/>\n")
        outFile.write(tabbedSpace + "     <srgb name=\"specularReflectance\" value=\"" + str(specularReflectance[0][0]) + " " + str(specularReflectance[0][1]) + " " + str(specularReflectance[0][2]) + "\"/>\n")
        outFile.write(tabbedSpace + "     <srgb name=\"diffuseReflectance\" value=\"" + str(diffuseReflectance[0][0]) + " " + str(diffuseReflectance[0][1]) + " " + str(diffuseReflectance[0][2]) + "\"/>\n")
        outFile.write(tabbedSpace + " </bsdf>\n")

    elif matType=="MitsubaThinDielectricShader":
        #Get all of the required attributes
        intIOR = cmds.getAttr(material+".intIOR")
        extIOR = cmds.getAttr(material+".extIOR")

        #Write material
        outFile.write(tabbedSpace + " <bsdf type=\"thindielectric\">\n id=\"" + materialName + "\">\n")
        outFile.write(tabbedSpace + "     <float name=\"intIOR\" value=\"" + str(intIOR) + "\"/>\n")
        outFile.write(tabbedSpace + "     <float name=\"extIOR\" value=\"" + str(extIOR) + "\"/>\n")
        outFile.write(tabbedSpace + " </bsdf>\n\n")

    elif matType=="MitsubaTwoSidedShader":
        outFile.write(tabbedSpace + " <bsdf type=\"twosided\" id=\"" + materialName + "\">\n")
        #Nested bsdf
        connections = cmds.listConnections(material, connections=True)
        for i in range(len(connections)):
            if i%2==1:
                connection = connections[i]
                connectionType = cmds.nodeType(connection)
                if connectionType in materialNodeTypes and connections[i-1]==material+".bsdf":
                    #We've found the nested bsdf, so write it
                    writeShader(connection, outFile, tabbedSpace+"    ")

        outFile.write(tabbedSpace + " </bsdf>\n")

    elif matType=="MitsubaWardShader":
        variant = cmds.getAttr(material+".variant", asString=True)
        alphaUV = cmds.getAttr(material+".alphaUV")
        specularReflectance = cmds.getAttr(material+".specularReflectance")
        diffuseReflectance = cmds.getAttr(material+".diffuseReflectance")

        outFile.write(tabbedSpace + " <bsdf type=\"phong\" id=\"" + materialName + "\">\n")
        outFile.write(tabbedSpace + "     <string name=\"variant\" value=\"" + str(variant) + "\"/>\n")
        outFile.write(tabbedSpace + "     <float name=\"alphaU\" value=\"" + str(alphaUV[0][0]) + "\"/>\n")
        outFile.write(tabbedSpace + "     <float name=\"alphaV\" value=\"" + str(alphaUV[0][1]) + "\"/>\n")
        outFile.write(tabbedSpace + "     <srgb name=\"specularReflectance\" value=\"" + str(specularReflectance[0][0]) + " " + str(specularReflectance[0][1]) + " " + str(specularReflectance[0][2]) + "\"/>\n")
        outFile.write(tabbedSpace + "     <srgb name=\"diffuseReflectance\" value=\"" + str(diffuseReflectance[0][0]) + " " + str(diffuseReflectance[0][1]) + " " + str(diffuseReflectance[0][2]) + "\"/>\n")
        outFile.write(tabbedSpace + " </bsdf>\n")

    elif matType=="MitsubaIrawanShader":
        outFile.write(tabbedSpace + " <bsdf type=\"irawan\" id=\"" + materialName + "\">\n")

        # filename
        filename = cmds.getAttr(material+".filename", asString=True)
        outFile.write(tabbedSpace + "     <string name=\"filename\" value=\"" + filename + "\"/>\n")

        # repeat
        repeatu = cmds.getAttr(material+".repeatu")
        outFile.write(tabbedSpace + "     <float name=\"repeatU\" value=\"" + str(repeatu) + "\"/>\n")

        repeatv = cmds.getAttr(material+".repeatv")
        outFile.write(tabbedSpace + "     <float name=\"repeatV\" value=\"" + str(repeatv) + "\"/>\n")

        #warp and weft
        warpkd = cmds.getAttr(material+".warpkd")
        outFile.write(tabbedSpace + "     <rgb name=\"warp_kd\" value=\"" + str(warpkd[0][0]) + " " + str(warpkd[0][1]) + " " + str(warpkd[0][2]) + "\"/>\n")

        warpks = cmds.getAttr(material+".warpks")
        outFile.write(tabbedSpace + "     <rgb name=\"warp_ks\" value=\"" + str(warpks[0][0]) + " " + str(warpks[0][1]) + " " + str(warpks[0][2]) + "\"/>\n")

        weftkd = cmds.getAttr(material+".weftkd")
        outFile.write(tabbedSpace + "     <rgb name=\"weft_kd\" value=\"" + str(weftkd[0][0]) + " " + str(weftkd[0][1]) + " " + str(weftkd[0][2]) + "\"/>\n")

        weftks = cmds.getAttr(material+".weftks")
        outFile.write(tabbedSpace + "     <rgb name=\"weft_ks\" value=\"" + str(weftks[0][0]) + " " + str(weftks[0][1]) + " " + str(weftks[0][2]) + "\"/>\n")

        outFile.write(tabbedSpace + " </bsdf>\n")

    elif matType=="MitsubaObjectAreaLightShader":
        outFile.write(tabbedSpace + " <emitter type=\"area\" id=\"" + materialName + "\">\n")

        color = cmds.getAttr(material+".radiance")
        outFile.write(tabbedSpace + "     <rgb name=\"radiance\" value=\"" + str(color[0][0]) + " " + str(color[0][1]) + " " + str(color[0][2]) + "\"/>\n")

        #radiance = cmds.getAttr(material+".radiance")
        #outFile.write(tabbedSpace + "     <spectrum name=\"radiance\" value=\"" + str(radiance) + "\"/>\n")

        samplingWeight = cmds.getAttr(material+".samplingWeight")
        outFile.write(tabbedSpace + "     <float name=\"samplingWeight\" value=\"" + str(samplingWeight) + "\"/>\n")

        outFile.write(tabbedSpace + " </emitter>\n")

'''
Write the appropriate integrator
'''
def writeIntegrator(outFile):
    #Write the integrator########################################################################
    integratorMenu = MitsubaRenderSettingsUI.integratorMenu
    integratorFrames = MitsubaRenderSettingsUI.integratorFrames

    #activeIntegrator = integrator
    activeIntegrator = cmds.optionMenu(integratorMenu, query=True, value=True)

    #print( "integrator menu : %s" % integratorMenu )
    #print( "integrator frames : %s" % integratorFrames )
    #print( "active integrator : %s" % activeIntegrator )

    #Find the active integrator's settings frame layout
    for frame in integratorFrames:
        if cmds.frameLayout(frame, query=True, visible=True):
            activeSettings = frame

    #print( "Active Integrator : %s" % activeIntegrator )

    if activeIntegrator=="Ambient_Occlusion" or activeIntegrator=="Ambient Occlusion":
        '''
        The order for this integrator is:
        0. intFieldGrp shadingSamples
        1. checkBox to use automatic ray length
        2. intFieldGrp rayLength (for manual rayLength)
        '''
        outFile.write(" <integrator type=\"ao\">\n")
        integratorSettings = cmds.frameLayout(activeSettings, query=True, childArray=True)

        sSamples = cmds.intFieldGrp(integratorSettings[0], query=True, value1=True)
        outFile.write("     <integer name=\"shadingSamples\" value=\"" + str(sSamples) + "\"/>\n")

        if cmds.checkBox(integratorSettings[1], query=True, value=True):
            outFile.write("     <integer name=\"rayLength\" value=\"" + str(-1) + "\"/>\n")
        else:
            rl = cmds.floatFieldGrp(integratorSettings[2], query=True, value1=True)
            outFile.write("     <float name=\"rayLength\" value=\"" + str(rl) + "\"/>\n")
    
    #Write DI settings
    elif activeIntegrator=="Direct_Illumination" or activeIntegrator=="Direct Illumination":
        '''
        The order for this integrator is:
        0. intFieldGrp shadingSamples
        1. checkBox to use separate samples for emitters and bsdfs
        2. intFieldGrp emitterSamples
        3. intFieldGrp bsdfSamples
        4. checkBox strictNormals
        5. checkBox hideEmitters
        '''
        outFile.write(" <integrator type=\"direct\">\n")
        integratorSettings = cmds.frameLayout(activeSettings, query=True, childArray=True)
        if cmds.checkBox(integratorSettings[1], query=True, value=True):
            eSamples = cmds.intFieldGrp(integratorSettings[2], query=True, value1=True)
            bSamples = cmds.intFieldGrp(integratorSettings[3], query=True, value1=True)
            outFile.write("     <integer name=\"emitterSamples\" value=\"" + str(eSamples) + "\"/>\n")
            outFile.write("     <integer name=\"bsdfSamples\" value=\"" + str(bSamples) + "\"/>\n")
        else:
            sSamples = cmds.intFieldGrp(integratorSettings[0], query=True, value1=True)
            outFile.write("     <integer name=\"shadingSamples\" value=\"" + str(sSamples) + "\"/>\n")

        if cmds.checkBox(integratorSettings[4], query=True, value=True):
            outFile.write("     <boolean name=\"strictNormals\" value=\"true\"/>\n")
        else:
            outFile.write("     <boolean name=\"strictNormals\" value=\"false\"/>\n")

        if cmds.checkBox(integratorSettings[5], query=True, value=True):
            outFile.write("     <boolean name=\"hideEmitters\" value=\"true\"/>\n")
        else:
            outFile.write("     <boolean name=\"hideEmitters\" value=\"false\"/>\n")

    #Write path tracer, volpaths settings
    elif activeIntegrator=="Path_Tracer" or activeIntegrator=="Volumetric_Path_Tracer" or activeIntegrator=="Simple_Volumetric_Path_Tracer" \
    or   activeIntegrator=="Path Tracer" or activeIntegrator=="Volumetric Path Tracer" or activeIntegrator=="Simple Volumetric Path Tracer":
        '''
        The order for this integrator is:
        0. checkBox to use infinite samples
        1. intFieldGrp maxDepth
        2. intFieldGrp rrDepth
        3. checkBox strictNormals
        4. checkBox hideEmitters
        '''
        if activeIntegrator=="Path_Tracer" or activeIntegrator=="Path Tracer":
            outFile.write(" <integrator type=\"path\">\n")
        elif activeIntegrator=="Volumetric_Path_Tracer" or activeIntegrator=="Volumetric Path Tracer":
            outFile.write(" <integrator type=\"volpath\">\n")
        else:
            outFile.write(" <integrator type=\"volpath_simple\">\n")

        integratorSettings = cmds.frameLayout(activeSettings, query=True, childArray=True)

        if cmds.checkBox(integratorSettings[0], query=True, value=True):
            outFile.write("     <integer name=\"maxDepth\" value=\"-1\"/>\n")
        else:
            maxDepth = cmds.intFieldGrp(integratorSettings[1], query=True, value1=True)
            outFile.write("     <integer name=\"maxDepth\" value=\"" + str(maxDepth) + "\"/>\n")

        rrDepth = cmds.intFieldGrp(integratorSettings[2], query=True, value1=True)
        outFile.write("     <integer name=\"rrDepth\" value=\"" + str(rrDepth) + "\"/>\n")            

        if cmds.checkBox(integratorSettings[3], query=True, value=True):
            outFile.write("     <boolean name=\"strictNormals\" value=\"true\"/>\n")
        else:
            outFile.write("     <boolean name=\"strictNormals\" value=\"false\"/>\n")

        if cmds.checkBox(integratorSettings[4], query=True, value=True):
            outFile.write("     <boolean name=\"hideEmitters\" value=\"true\"/>\n")
        else:
            outFile.write("     <boolean name=\"hideEmitters\" value=\"false\"/>\n")

    #Write bdpt
    elif activeIntegrator=="Bidirectional_Path_Tracer" or activeIntegrator=="Bidirectional Path Tracer":
        '''
        The order for this integrator is:
        0. checkBox to use infinite samples
        1. intFieldGrp maxDepth
        2. checkBox lightImage
        3. checkBox sampleDirect
        4. intFieldGrp rrDepth
        '''
        outFile.write(" <integrator type=\"bdpt\">\n")
        integratorSettings = cmds.frameLayout(activeSettings, query=True, childArray=True)

        if cmds.checkBox(integratorSettings[0], query=True, value=True):
            outFile.write("     <integer name=\"maxDepth\" value=\"-1\"/>\n")
        else:
            maxDepth = cmds.intFieldGrp(integratorSettings[1], query=True, value1=True)
            outFile.write("     <integer name=\"maxDepth\" value=\"" + str(maxDepth) + "\"/>\n")

        if cmds.checkBox(integratorSettings[2], query=True, value=True):
            outFile.write("     <boolean name=\"lightImage\" value=\"true\"/>\n")
        else:
            outFile.write("     <boolean name=\"lightImage\" value=\"false\"/>\n")

        if cmds.checkBox(integratorSettings[3], query=True, value=True):
            outFile.write("     <boolean name=\"sampleDirect\" value=\"true\"/>\n")
        else:
            outFile.write("     <boolean name=\"sampleDirect\" value=\"false\"/>\n")

        rrDepth = cmds.intFieldGrp(integratorSettings[4], query=True, value1=True)
        outFile.write("     <integer name=\"emitterSamples\" value=\"" + str(rrDepth) + "\"/>\n")    


    #Write photon mapper
    elif activeIntegrator=="Photon_Map" or activeIntegrator=="Photon Map":
        '''
        The order for this integrator is:
        0. intFieldGrp directSamples
        1. intFieldGrp glossySamples
        2. checkBox to use infinite depth
        3. intFieldGrp maxDepth
        4. intFieldGrp globalPhotons
        5. intFieldGrp causticPhotons
        6. intFieldGrp volumePhotons
        7. floatFieldGrp globalLookupRadius
        8. floatFieldGrp causticLookupRadius
        9. intFieldGrp lookupSize
        10. checkBox to use automatic granularity
        11. intFieldGrp granularity
        12. checkBox hideEmitters
        13. intFieldGrp rrDepth
        '''
        outFile.write(" <integrator type=\"photonmapper\">\n")
        integratorSettings = cmds.frameLayout(activeSettings, query=True, childArray=True)

        directSamples = cmds.intFieldGrp(integratorSettings[0], query=True, value1=True)
        outFile.write("     <integer name=\"directSamples\" value=\"" + str(directSamples) + "\"/>\n")

        glossySamples = cmds.intFieldGrp(integratorSettings[1], query=True, value1=True)
        outFile.write("     <integer name=\"glossySamples\" value=\"" + str(glossySamples) + "\"/>\n")

        if cmds.checkBox(integratorSettings[2], query=True, value=True):
            outFile.write("     <integer name=\"maxDepth\" value=\"-1\"/>\n")
        else:
            maxDepth = cmds.intFieldGrp(integratorSettings[3], query=True, value1=True)
            outFile.write("     <integer name=\"maxDepth\" value=\"" + str(maxDepth) + "\"/>\n")

        globalPhotons = cmds.intFieldGrp(integratorSettings[4], query=True, value1=True)
        outFile.write("     <integer name=\"globalPhotons\" value=\"" + str(globalPhotons) + "\"/>\n")

        causticPhotons = cmds.intFieldGrp(integratorSettings[5], query=True, value1=True)
        outFile.write("     <integer name=\"causticPhotons\" value=\"" + str(causticPhotons) + "\"/>\n")

        volumePhotons = cmds.intFieldGrp(integratorSettings[6], query=True, value1=True)
        outFile.write("     <integer name=\"volumePhotons\" value=\"" + str(volumePhotons) + "\"/>\n")

        globalLookupRadius = cmds.floatFieldGrp(integratorSettings[7], query=True, value1=True)
        outFile.write("     <float name=\"globalLookupRadius\" value=\"" + str(globalLookupRadius) + "\"/>\n")  

        causticLookupRadius = cmds.floatFieldGrp(integratorSettings[8], query=True, value1=True)
        outFile.write("     <float name=\"causticLookupRadius\" value=\"" + str(causticLookupRadius) + "\"/>\n")            

        lookupSize = cmds.intFieldGrp(integratorSettings[9], query=True, value1=True)
        outFile.write("     <integer name=\"lookupSize\" value=\"" + str(lookupSize) + "\"/>\n")

        if cmds.checkBox(integratorSettings[10], query=True, value=True):
            outFile.write("     <integer name=\"granularity\" value=\"0\"/>\n")
        else:
            granularity = cmds.intFieldGrp(integratorSettings[11], query=True, value1=True)
            outFile.write("     <integer name=\"granularity\" value=\"" + str(granularity) + "\"/>\n")

        if cmds.checkBox(integratorSettings[12], query=True, value=True):
            outFile.write("     <boolean name=\"hideEmitters\" value=\"true\"/>\n")
        else:
            outFile.write("     <boolean name=\"hideEmitters\" value=\"false\"/>\n")

        rrDepth = cmds.intFieldGrp(integratorSettings[13], query=True, value1=True)
        outFile.write("     <integer name=\"rrDepth\" value=\"" + str(rrDepth) + "\"/>\n")    

    #Write progressive photon mapper
    elif activeIntegrator=="Progressive_Photon_Map" or activeIntegrator=="Progressive Photon Map":
        '''
        The order for this integrator is:
        0. checkBox to use infinite depth
        1. intFieldGrp maxDepth
        2. intFieldGrp photonCount
        3. checkBox to use automatic initialRadius
        4. floatFieldGrp initialRadius
        5. floatFieldGrp alpha
        6. checkBox to use automatic granularity
        7. intFieldGrp granularity
        8. checkBox hideEmitters
        9. intFieldGrp rrDepth
        10. checkBox to use infinite maxPasses
        11. intFieldGrp maxPasses
        '''
        outFile.write(" <integrator type=\"ppm\">\n")
        integratorSettings = cmds.frameLayout(activeSettings, query=True, childArray=True)

        if cmds.checkBox(integratorSettings[0], query=True, value=True):
            outFile.write("     <integer name=\"maxDepth\" value=\"-1\"/>\n")
        else:
            maxDepth = cmds.intFieldGrp(integratorSettings[1], query=True, value1=True)
            outFile.write("     <integer name=\"maxDepth\" value=\"" + str(maxDepth) + "\"/>\n")

        photonCount = cmds.intFieldGrp(integratorSettings[2], query=True, value1=True)
        outFile.write("     <integer name=\"photonCount\" value=\"" + str(photonCount) + "\"/>\n")

        if cmds.checkBox(integratorSettings[3], query=True, value=True):
            outFile.write("     <float name=\"initialRadius\" value=\"0\"/>\n")
        else:
            initialRadius = cmds.floatFieldGrp(integratorSettings[4], query=True, value1=True)
            outFile.write("     <float name=\"initialRadius\" value=\"" + str(initialRadius) + "\"/>\n")

        alpha = cmds.floatFieldGrp(integratorSettings[5], query=True, value1=True)
        outFile.write("     <float name=\"alpha\" value=\"" + str(alpha) + "\"/>\n") 

        if cmds.checkBox(integratorSettings[6], query=True, value=True):
            outFile.write("     <integer name=\"granularity\" value=\"0\"/>\n")
        else:
            granularity = cmds.intFieldGrp(integratorSettings[7], query=True, value1=True)
            outFile.write("     <integer name=\"granularity\" value=\"" + str(granularity) + "\"/>\n")

        if cmds.checkBox(integratorSettings[8], query=True, value=True):
            outFile.write("     <boolean name=\"lightImage\" value=\"true\"/>\n")
        else:
            outFile.write("     <boolean name=\"lightImage\" value=\"false\"/>\n")
       
        rrDepth = cmds.intFieldGrp(integratorSettings[9], query=True, value1=True)
        outFile.write("     <integer name=\"rrDepth\" value=\"" + str(rrDepth) + "\"/>\n")    

        if cmds.checkBox(integratorSettings[10], query=True, value=True):
            outFile.write("     <integer name=\"maxPasses\" value=\"-1\"/>\n")
        else:
            maxPasses = cmds.intFieldGrp(integratorSettings[11], query=True, value1=True)
            outFile.write("     <integer name=\"maxPasses\" value=\"" + str(maxPasses) + "\"/>\n")

    #Write sppm
    elif activeIntegrator=="Stochastic_Progressive_Photon_Map" or activeIntegrator=="Stochastic Progressive Photon Map":
        '''
        The order for this integrator is:
        0. checkBox to use infinite depth
        1. intFieldGrp maxDepth
        2. intFieldGrp photonCount
        3. checkBox to use automatic initialRadius
        4. floatFieldGrp initialRadius
        5. floatFieldGrp alpha
        6. checkBox to use automatic granularity
        7. intFieldGrp granularity
        8. checkBox hideEmitters
        9. intFieldGrp rrDepth
        10. checkBox to use infinite maxPasses
        11. intFieldGrp maxPasses
        '''
        outFile.write(" <integrator type=\"sppm\">\n")
        integratorSettings = cmds.frameLayout(activeSettings, query=True, childArray=True)

        if cmds.checkBox(integratorSettings[0], query=True, value=True):
            outFile.write("     <integer name=\"maxDepth\" value=\"-1\"/>\n")
        else:
            maxDepth = cmds.intFieldGrp(integratorSettings[1], query=True, value1=True)
            outFile.write("     <integer name=\"maxDepth\" value=\"" + str(maxDepth) + "\"/>\n")

        photonCount = cmds.intFieldGrp(integratorSettings[2], query=True, value1=True)
        outFile.write("     <integer name=\"photonCount\" value=\"" + str(photonCount) + "\"/>\n")

        if cmds.checkBox(integratorSettings[3], query=True, value=True):
            outFile.write("     <float name=\"initialRadius\" value=\"0\"/>\n")
        else:
            initialRadius = cmds.floatFieldGrp(integratorSettings[4], query=True, value1=True)
            outFile.write("     <float name=\"initialRadius\" value=\"" + str(initialRadius) + "\"/>\n")

        alpha = cmds.floatFieldGrp(integratorSettings[5], query=True, value1=True)
        outFile.write("     <float name=\"alpha\" value=\"" + str(alpha) + "\"/>\n") 

        if cmds.checkBox(integratorSettings[6], query=True, value=True):
            outFile.write("     <integer name=\"granularity\" value=\"0\"/>\n")
        else:
            granularity = cmds.intFieldGrp(integratorSettings[7], query=True, value1=True)
            outFile.write("     <integer name=\"granularity\" value=\"" + str(granularity) + "\"/>\n")

        if cmds.checkBox(integratorSettings[8], query=True, value=True):
            outFile.write("     <boolean name=\"hideEmitters\" value=\"true\"/>\n")
        else:
            outFile.write("     <boolean name=\"hideEmitters\" value=\"false\"/>\n")
        
        rrDepth = cmds.intFieldGrp(integratorSettings[9], query=True, value1=True)
        outFile.write("     <integer name=\"rrDepth\" value=\"" + str(rrDepth) + "\"/>\n")    

        if cmds.checkBox(integratorSettings[10], query=True, value=True):
            outFile.write("     <integer name=\"maxPasses\" value=\"-1\"/>\n")
        else:
            maxPasses = cmds.intFieldGrp(integratorSettings[11], query=True, value1=True)
            outFile.write("     <integer name=\"maxPasses\" value=\"" + str(maxPasses) + "\"/>\n")

    #Write pssmlt
    elif activeIntegrator=="Primary_Sample_Space_Metropolis_Light_Transport" or activeIntegrator=="Primary Sample Space Metropolis Light Transport":
        '''
        The order for this integrator is:
        0. checkBox bidirectional
        1. checkBox to use infinite depth
        2. intFieldGrp maxDepth
        3. checkBox to use automatic directSamples
        4. intFieldGrp directSamples
        5. intFieldGrp luminanceSamples
        6. checkBox twoStage
        7. checkBox hideEmitters
        8. intFieldGrp rrDepth
        9. floatFieldGrp pLarge
        '''
        outFile.write(" <integrator type=\"pssmlt\">\n")
        integratorSettings = cmds.frameLayout(activeSettings, query=True, childArray=True)

        if cmds.checkBox(integratorSettings[0], query=True, value=True):
            outFile.write("     <boolean name=\"bidirectional\" value=\"true\"/>\n")
        else:
            outFile.write("     <boolean name=\"bidirectional\" value=\"false\"/>\n")

        if cmds.checkBox(integratorSettings[1], query=True, value=True):
            outFile.write("     <integer name=\"maxDepth\" value=\"-1\"/>\n")
        else:
            maxDepth = cmds.intFieldGrp(integratorSettings[2], query=True, value1=True)
            outFile.write("     <integer name=\"maxDepth\" value=\"" + str(maxDepth) + "\"/>\n")

        if cmds.checkBox(integratorSettings[3], query=True, value=True):
            outFile.write("     <integer name=\"directSamples\" value=\"-1\"/>\n")
        else:
            directSamples = cmds.intFieldGrp(integratorSettings[4], query=True, value1=True)
            outFile.write("     <integer name=\"directSamples\" value=\"" + str(directSamples) + "\"/>\n")

        luminanceSamples = cmds.intFieldGrp(integratorSettings[5], query=True, value1=True)
        outFile.write("     <integer name=\"luminanceSamples\" value=\"" + str(luminanceSamples) + "\"/>\n")

        if cmds.checkBox(integratorSettings[6], query=True, value=True):
            outFile.write("     <boolean name=\"twoStage\" value=\"true\"/>\n")
        else:
            outFile.write("     <boolean name=\"twoStage\" value=\"false\"/>\n")

        if cmds.checkBox(integratorSettings[7], query=True, value=True):
            outFile.write("     <boolean name=\"hideEmitters\" value=\"true\"/>\n")
        else:
            outFile.write("     <boolean name=\"hideEmitters\" value=\"false\"/>\n")

        rrDepth = cmds.intFieldGrp(integratorSettings[8], query=True, value1=True)
        outFile.write("     <integer name=\"rrDepth\" value=\"" + str(rrDepth) + "\"/>\n")

        pLarge = cmds.floatFieldGrp(integratorSettings[9], query=True, value1=True)
        outFile.write("     <float name=\"pLarge\" value=\"" + str(pLarge) + "\"/>\n")

    #Write psmlt
    elif activeIntegrator=="Path_Space_Metropolis_Light_Transport" or activeIntegrator=="Path Space Metropolis Light Transport":
        '''
        The order for this integrator is:
        0. checkBox to use infinite depth
        1. intFieldGrp maxDepth
        2. checkBox to use automatic directSamples
        3. intFieldGrp directSamples
        4. intFieldGrp luminanceSamples
        5. checkBox twoStage
        6. checkBox bidirectionalMutation
        7. checkBox lensPerturbation
        8. checkBox multiChainPerturbation
        9. checkBox causticPerturbation
        10. checkBox manifoldPerturbation
        11. checkBox hideEmitters
        12. floatFieldGrp lambda
        '''
        outFile.write(" <integrator type=\"mlt\">\n")
        integratorSettings = cmds.frameLayout(activeSettings, query=True, childArray=True)

        if cmds.checkBox(integratorSettings[0], query=True, value=True):
            outFile.write("     <integer name=\"maxDepth\" value=\"-1\"/>\n")
        else:
            maxDepth = cmds.intFieldGrp(integratorSettings[1], query=True, value1=True)
            outFile.write("     <integer name=\"maxDepth\" value=\"" + str(maxDepth) + "\"/>\n")

        if cmds.checkBox(integratorSettings[2], query=True, value=True):
            outFile.write("     <integer name=\"directSamples\" value=\"-1\"/>\n")
        else:
            directSamples = cmds.intFieldGrp(integratorSettings[3], query=True, value1=True)
            outFile.write("     <integer name=\"directSamples\" value=\"" + str(directSamples) + "\"/>\n")

        luminanceSamples = cmds.intFieldGrp(integratorSettings[4], query=True, value1=True)
        outFile.write("     <integer name=\"luminanceSamples\" value=\"" + str(luminanceSamples) + "\"/>\n")

        if cmds.checkBox(integratorSettings[5], query=True, value=True):
            outFile.write("     <boolean name=\"twoStage\" value=\"true\"/>\n")
        else:
            outFile.write("     <boolean name=\"twoStage\" value=\"false\"/>\n")

        if cmds.checkBox(integratorSettings[6], query=True, value=True):
            outFile.write("     <boolean name=\"bidirectionalMutation\" value=\"true\"/>\n")
        else:
            outFile.write("     <boolean name=\"bidirectionalMutation\" value=\"false\"/>\n")

        if cmds.checkBox(integratorSettings[7], query=True, value=True):
            outFile.write("     <boolean name=\"lensPerturbation\" value=\"true\"/>\n")
        else:
            outFile.write("     <boolean name=\"lensPerturbation\" value=\"false\"/>\n")

        if cmds.checkBox(integratorSettings[8], query=True, value=True):
            outFile.write("     <boolean name=\"multiChainPerturbation\" value=\"true\"/>\n")
        else:
            outFile.write("     <boolean name=\"multiChainPerturbation\" value=\"false\"/>\n")

        if cmds.checkBox(integratorSettings[9], query=True, value=True):
            outFile.write("     <boolean name=\"causticPerturbation\" value=\"true\"/>\n")
        else:
            outFile.write("     <boolean name=\"causticPerturbation\" value=\"false\"/>\n")

        if cmds.checkBox(integratorSettings[9], query=True, value=True):
            outFile.write("     <boolean name=\"manifoldPerturbation\" value=\"true\"/>\n")
        else:
            outFile.write("     <boolean name=\"manifoldPerturbation\" value=\"false\"/>\n")

        if cmds.checkBox(integratorSettings[11], query=True, value=True):
            outFile.write("     <boolean name=\"hideEmitters\" value=\"true\"/>\n")
        else:
            outFile.write("     <boolean name=\"hideEmitters\" value=\"false\"/>\n")

        mtsLambda = cmds.floatFieldGrp(integratorSettings[12], query=True, value1=True)
        outFile.write("     <float name=\"lambda\" value=\"" + str(mtsLambda) + "\"/>\n")

    #Write erpt
    elif activeIntegrator=="Energy_Redistribution_Path_Tracer" or activeIntegrator=="Energy Redistribution Path Tracer":
        '''
        The order for this integrator is:
        0. checkBox to use infinite depth
        1. intFieldGrp maxDepth
        2. floatFieldGrp numChains
        3. checkBox to use maxChains
        4. floatFieldGrp maxChains
        5. checkBox to use automatic directSamples
        6. intFieldGrp directSamples
        7. checkBox lensPerturbation
        8. checkBox multiChainPerturbation
        9. checkBox causticPerturbation
        10. checkBox manifoldPerturbation
        11. checkBox hideEmitters
        12. floatFieldGrp lambda
        '''
        outFile.write(" <integrator type=\"mlt\">\n")
        integratorSettings = cmds.frameLayout(activeSettings, query=True, childArray=True)

        if cmds.checkBox(integratorSettings[0], query=True, value=True):
            outFile.write("     <integer name=\"maxDepth\" value=\"-1\"/>\n")
        else:
            maxDepth = cmds.intFieldGrp(integratorSettings[1], query=True, value1=True)
            outFile.write("     <integer name=\"maxDepth\" value=\"" + str(maxDepth) + "\"/>\n")

        numChains = cmds.floatFieldGrp(integratorSettings[2], query=True, value1=True)
        outFile.write("     <float name=\"numChains\" value=\"" + str(numChains) + "\"/>\n")

        if not cmds.checkBox(integratorSettings[3], query=True, value=True):
            outFile.write("     <integer name=\"maxChains\" value=\"0\"/>\n")
        else:
            maxChains = cmds.floatFieldGrp(integratorSettings[4], query=True, value1=True)
            outFile.write("     <integer name=\"maxChains\" value=\"" + str(maxChains) + "\"/>\n")

        if cmds.checkBox(integratorSettings[5], query=True, value=True):
            outFile.write("     <integer name=\"directSamples\" value=\"-1\"/>\n")
        else:
            directSamples = cmds.intFieldGrp(integratorSettings[6], query=True, value1=True)
            outFile.write("     <integer name=\"directSamples\" value=\"" + str(directSamples) + "\"/>\n")

        if cmds.checkBox(integratorSettings[7], query=True, value=True):
            outFile.write("     <boolean name=\"lensPerturbation\" value=\"true\"/>\n")
        else:
            outFile.write("     <boolean name=\"lensPerturbation\" value=\"false\"/>\n")

        if cmds.checkBox(integratorSettings[8], query=True, value=True):
            outFile.write("     <boolean name=\"multiChainPerturbation\" value=\"true\"/>\n")
        else:
            outFile.write("     <boolean name=\"multiChainPerturbation\" value=\"false\"/>\n")

        if cmds.checkBox(integratorSettings[9], query=True, value=True):
            outFile.write("     <boolean name=\"causticPerturbation\" value=\"true\"/>\n")
        else:
            outFile.write("     <boolean name=\"causticPerturbation\" value=\"false\"/>\n")

        if cmds.checkBox(integratorSettings[10], query=True, value=True):
            outFile.write("     <boolean name=\"manifoldPerturbation\" value=\"true\"/>\n")
        else:
            outFile.write("     <boolean name=\"manifoldPerturbation\" value=\"false\"/>\n")

        if cmds.checkBox(integratorSettings[11], query=True, value=True):
            outFile.write("     <boolean name=\"hideEmitters\" value=\"true\"/>\n")
        else:
            outFile.write("     <boolean name=\"hideEmitters\" value=\"false\"/>\n")

        mtsLambda = cmds.floatFieldGrp(integratorSettings[12], query=True, value1=True)
        outFile.write("     <float name=\"lambda\" value=\"" + str(mtsLambda) + "\"/>\n")\

    #Write ptracer
    elif activeIntegrator=="Adjoint_Particle_Tracer" or activeIntegrator=="Adjoint Particle Tracer":
        '''
        The order for this integrator is:
        0. checkBox to use infinite depth
        1. intFieldGrp maxDepth
        2. intFieldGrp rrDepth
        3. intFieldGrp granularity
        4. checkBox bruteForce
        5. checkBox hideEmitters
        '''
        outFile.write(" <integrator type=\"mlt\">\n")
        integratorSettings = cmds.frameLayout(activeSettings, query=True, childArray=True)

        if cmds.checkBox(integratorSettings[0], query=True, value=True):
            outFile.write("     <integer name=\"maxDepth\" value=\"-1\"/>\n")
        else:
            maxDepth = cmds.intFieldGrp(integratorSettings[1], query=True, value1=True)
            outFile.write("     <integer name=\"maxDepth\" value=\"" + str(maxDepth) + "\"/>\n")

        rrDepth = cmds.intFieldGrp(integratorSettings[2], query=True, value1=True)
        outFile.write("     <integer name=\"rrDepth\" value=\"" + str(rrDepth) + "\"/>\n")

        granularity = cmds.intFieldGrp(integratorSettings[3], query=True, value1=True)
        outFile.write("     <integer name=\"granularity\" value=\"" + str(granularity) + "\"/>\n")

        if cmds.checkBox(integratorSettings[4], query=True, value=True):
            outFile.write("     <boolean name=\"bruteForce\" value=\"true\"/>\n")
        else:
            outFile.write("     <boolean name=\"bruteForce\" value=\"false\"/>\n")

        if cmds.checkBox(integratorSettings[5], query=True, value=True):
            outFile.write("     <boolean name=\"hideEmitters\" value=\"true\"/>\n")
        else:
            outFile.write("     <boolean name=\"hideEmitters\" value=\"false\"/>\n")

    #Write vpl
    elif activeIntegrator=="Virtual_Point_Lights" or activeIntegrator=="Virtual Point Lights":
        print "vpl"

    outFile.write(" </integrator>\n\n\n")
    #############################################################################################

'''
Write image sample generator
'''
def writeSampler(outFile, frameNumber):
    samplerMenu = MitsubaRenderSettingsUI.samplerMenu
    samplerFrames = MitsubaRenderSettingsUI.samplerFrames

    activeSampler = cmds.optionMenu(samplerMenu, query=True, value=True)

    #print( "sampler menu : %s" % samplerMenu )
    #print( "sampler frames : %s" % samplerFrames )
    #print( "active sampler : %s" % activeSampler )

    #activeSampler = sampler
    activeSettings = samplerFrames[0]

    #print( "Active Sampler : %s" % activeSampler )

    for frame in samplerFrames:
        if cmds.frameLayout(frame, query=True, visible=True):
            activeSettings = frame

    if activeSampler=="Independent_Sampler" or activeSampler=="Independent Sampler":
        samplerSettings = cmds.frameLayout(activeSettings, query=True, childArray=True)
        outFile.write("         <sampler type=\"independent\">\n")

        sampleCount = cmds.intFieldGrp(samplerSettings[0], query=True, value1=True)
        outFile.write("             <integer name=\"sampleCount\" value=\"" + str(sampleCount) + "\"/>\n")

    elif activeSampler=="Stratified_Sampler" or activeSampler=="Stratified Sampler":
        samplerSettings = cmds.frameLayout(activeSettings, query=True, childArray=True)
        outFile.write("         <sampler type=\"stratified\">\n")

        sampleCount = cmds.intFieldGrp(samplerSettings[0], query=True, value1=True)
        outFile.write("             <integer name=\"sampleCount\" value=\"" + str(sampleCount) + "\"/>\n")

        dimension = cmds.intFieldGrp(samplerSettings[1], query=True, value1=True)
        outFile.write("             <integer name=\"dimension\" value=\"" + str(dimension) + "\"/>\n")

    elif activeSampler=="Low_Discrepancy_Sampler" or activeSampler=="Low Discrepancy Sampler":
        samplerSettings = cmds.frameLayout(activeSettings, query=True, childArray=True)
        outFile.write("         <sampler type=\"ldsampler\">\n")

        sampleCount = cmds.intFieldGrp(samplerSettings[0], query=True, value1=True)
        outFile.write("             <integer name=\"sampleCount\" value=\"" + str(sampleCount) + "\"/>\n")

        dimension = cmds.intFieldGrp(samplerSettings[1], query=True, value1=True)
        outFile.write("             <integer name=\"dimension\" value=\"" + str(dimension) + "\"/>\n")

    elif activeSampler=="Halton_QMC_Sampler" or activeSampler=="Halton QMC Sampler":
        samplerSettings = cmds.frameLayout(activeSettings, query=True, childArray=True)
        outFile.write("         <sampler type=\"halton\">\n")

        sampleCount = cmds.intFieldGrp(samplerSettings[0], query=True, value1=True)
        outFile.write("             <integer name=\"sampleCount\" value=\"" + str(sampleCount) + "\"/>\n")

        scramble = cmds.intFieldGrp(samplerSettings[1], query=True, value1=True)
        scramble = frameNumber
        outFile.write("             <integer name=\"scramble\" value=\"" + str(scramble) + "\"/>\n")

    elif activeSampler=="Hammersley_QMC_Sampler" or activeSampler=="Hammersley QMC Sampler":
        samplerSettings = cmds.frameLayout(activeSettings, query=True, childArray=True)
        outFile.write("         <sampler type=\"hammersley\">\n")

        sampleCount = cmds.intFieldGrp(samplerSettings[0], query=True, value1=True)
        outFile.write("             <integer name=\"sampleCount\" value=\"" + str(sampleCount) + "\"/>\n")

        scramble = cmds.intFieldGrp(samplerSettings[1], query=True, value1=True)
        scramble = frameNumber
        outFile.write("             <integer name=\"scramble\" value=\"" + str(scramble) + "\"/>\n")

    elif activeSampler=="Sobol_QMC_Sampler" or activeSampler=="Sobol QMC Sampler":
        samplerSettings = cmds.frameLayout(activeSettings, query=True, childArray=True)
        outFile.write("         <sampler type=\"sobol\">\n")

        sampleCount = cmds.intFieldGrp(samplerSettings[0], query=True, value1=True)
        outFile.write("             <integer name=\"sampleCount\" value=\"" + str(sampleCount) + "\"/>\n")

        scramble = cmds.intFieldGrp(samplerSettings[1], query=True, value1=True)
        scramble = frameNumber
        outFile.write("             <integer name=\"scramble\" value=\"" + str(scramble) + "\"/>\n")

    outFile.write("         </sampler>\n")
    outFile.write("\n")

'''
Write sensor, which include camera, image sampler, and film
'''
def writeSensor(outFile, frameNumber):
    outFile.write(" <!-- Camera -->\n")

    cams = cmds.ls(type="camera")
    rCamShape = ""
    for cam in cams:
        isRenderable = cmds.getAttr(cam+".renderable")
        if isRenderable:
            print( "Rendering camera : %s" % cam )
            rCamShape = cam
            break

    if rCamShape == "":
        print( "No renderable camera found. Rendering with first camera : %s" % cams[0] )
        rCamShape = cams[0]
    
    rGroup = cmds.listConnections(rCamShape)[0]

    rGroupRels = cmds.listRelatives(rGroup)

    rCam = rGroupRels[0]
    rAim = rGroupRels[1]
    rUp  = rGroupRels[2]

    camPos = cmds.getAttr(rCam+".translate")[0]
    camAim = cmds.getAttr(rAim+".translate")[0]
    camUp  = cmds.getAttr(rUp+".translate")[0]

    #Type
    camType="perspective"
    if cmds.getAttr(rCamShape+".depthOfField"):
        camType="thinlens"

    #dof stuff
    apertureRadius = 1
    focusDistance = 1
    if camType=="thinlens":
        apertureRadius = cmds.getAttr(rCamShape+".focusRegionScale")
        focusDistance = cmds.getAttr(rCamShape+".focusDistance")

    #fov
    fov = cmds.camera(rCamShape, query=True, horizontalFieldOfView=True)

    #near clip plane
    nearClip = cmds.getAttr(rCamShape+".nearClipPlane")

    outFile.write(" <sensor type=\"" + camType + "\">\n")
    if camType=="thinlens":
        outFile.write("         <float name=\"apertureRadius\" value=\"" + str(apertureRadius) + "\"/>\n")
        outFile.write("         <float name=\"focusDistance\" value=\"" + str(focusDistance) + "\"/>\n")    
    outFile.write("         <float name=\"fov\" value=\"" + str(fov) + "\"/>\n")
    outFile.write("         <string name=\"fovAxis\" value=\"x\"/>\n")
    outFile.write("         <float name=\"nearClip\" value=\"" + str(nearClip) + "\"/>\n")
    outFile.write("         <transform name=\"toWorld\">\n")
    outFile.write("             <lookat target=\"" + str(camAim[0]) + " " + str(camAim[1]) + " " + str(camAim[2]) + "\" origin=\"" + str(camPos[0]) + " " + str(camPos[1]) + " " + str(camPos[2]) + "\" up=\"" + str(camUp[0]-camPos[0]) + " " + str(camUp[1]-camPos[1]) + " " + str(camUp[2]-camPos[2]) + "\"/>\n")
    outFile.write("         </transform>\n")
    outFile.write("\n")
    
    #write sampler generator:
    writeSampler(outFile, frameNumber)

    #Film
    outFile.write("     <film type=\"hdrfilm\">\n")
    
    #Resolution
    imageWidth = cmds.getAttr("defaultResolution.width")
    imageHeight = cmds.getAttr("defaultResolution.height")
    outFile.write("         <integer name=\"height\" value=\"" + str(imageHeight) + "\"/>\n")
    outFile.write("         <integer name=\"width\" value=\"" + str(imageWidth) + "\"/>\n")

    #Filter
    rfilterMenu = MitsubaRenderSettingsUI.rfilterMenu

    rfilterValue = cmds.optionMenu(rfilterMenu, query=True, value=True)
    rfilterString = ""
    if rfilterValue=="Box_filter" or rfilterValue=="Box filter":
        rfilterString = "box"
    if rfilterValue=="Tent_filter" or rfilterValue=="Tent filter":
        rfilterString = "tent"
    if rfilterValue=="Gaussian_filter" or rfilterValue=="Gaussian filter":
        rfilterString = "gaussian"
    if rfilterValue=="Mitchell_Netravali_filter" or rfilterValue=="Mitchell-Netravali filter":
        rfilterString = "mitchell"
    if rfilterValue=="Catmull_Rom_filter" or rfilterValue=="Catmull-Rom filter":
        rfilterString = "catmullrom"
    if rfilterValue=="Lanczos_filter" or rfilterValue=="Lanczos filter":
        rfilterString = "lanczos"

    outFile.write("         <rfilter type=\"" + rfilterString + "\"/>\n")
    outFile.write("         <boolean name=\"banner\" value=\"false\"/>\n")
    outFile.write("     </film>\n")
    outFile.write(" </sensor>\n")
    outFile.write("\n")

'''
Write lights
'''
def writeLights(outFile):
    lights = cmds.ls(type="light")
    sunskyLights = cmds.ls(type="MitsubaSunsky")
    envLights = cmds.ls(type="MitsubaEnvironmentLight")

    if sunskyLights and envLights or sunskyLights and len(sunskyLights)>1 or envLights and len(envLights)>1:
        print "Cannot specify more than one environment light (MitsubaSunsky and MitsubaEnvironmentLight)"
        # print "Defaulting to constant environment emitter"
        # outFile.write(" <emitter type=\"constant\"/>\n")

    for light in lights:
        lightType = cmds.nodeType(light)
        if lightType == "directionalLight":
            intensity = cmds.getAttr(light+".intensity")
            color = cmds.getAttr(light+".color")[0]
            irradiance = [0,0,0]
            for i in range(3):
                irradiance[i] = intensity*color[i]
            matrix = cmds.getAttr(light+".worldMatrix")
            lightDir = [-matrix[8],-matrix[9],-matrix[10]]
            outFile.write(" <emitter type=\"directional\">\n")
            outFile.write("     <vector name=\"direction\" x=\"" + str(lightDir[0]) + "\" y=\"" + str(lightDir[1]) + "\" z=\"" + str(lightDir[2]) + "\"/>\n")
            outFile.write("     <srgb name=\"irradiance\" value=\"" + str(irradiance[0]) + " " + str(irradiance[1]) + " " + str(irradiance[2]) + "\"/>\n")
            outFile.write(" </emitter>\n")

    #Sunsky light
    if sunskyLights:
        sunsky = sunskyLights[0]
        sun = cmds.getAttr(sunsky+".useSun")
        sky = cmds.getAttr(sunsky+".useSky")
        if sun and sky:
            outFile.write(" <emitter type=\"sunsky\">\n")
        elif sun:
            outFile.write(" <emitter type=\"sun\">\n")
        elif sky:
            outFile.write(" <emitter type=\"sky\">\n")
        else:
            print "Must use either sun or sky, defaulting to sunsky"
            outFile.write(" <emitter type=\"sunsky\">\n")

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

    #Area lights
    if envLights:
        envmap = envLights[0]
        connections = cmds.listConnections(envmap, plugs=False, c=True)
        fileName = ""
        hasFile = False
        correctFormat = True

        if connections:
            connectionAttr = "source"
            fileName = getTextureFile(envmap, connectionAttr)

            '''
            for i in range(len(connections)):
                connection = connections[i]
                if connection == envmap+".source":
                    inConnection = connections[i+1]
                    if cmds.nodeType(inConnection) == "file":
                        fileName = cmds.getAttr(inConnection+".fileTextureName")
            '''

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

            else:
                radiance = cmds.getAttr(envmap+".source")
                samplingWeight = cmds.getAttr(envmap+".samplingWeight")
                
                outFile.write(" <emitter type=\"constant\">\n")
                outFile.write("     <srgb name=\"radiance\" value=\"" + str(radiance[0][0]) + " " + str(radiance[0][1]) + " " + str(radiance[0][2]) + "\"/>\n")
                outFile.write("     <float name=\"samplingWeight\" value=\"" + str(samplingWeight) + "\"/>\n")
                outFile.write(" </emitter>\n")

    outFile.write("\n")
    outFile.write("<!-- End of lights -->")
    outFile.write("\n\n\n")


def writeGeometryAndMaterials(outFile, cwd):
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

    #Write the material for each piece of geometry in the scene
    writtenMaterials = []
    for geom in geoms:
        material = getShader(geom)          #Gets the user define names of the shader
        materialType = cmds.nodeType(material)
        if materialType in materialNodeTypes:
            if material not in writtenMaterials:
                if "twosided" in cmds.listAttr(material) and cmds.getAttr(material+".twosided"):
                    outFile.write("<bsdf type=\"twosided\" id=\"" + material + "\">\n")
                    writeShader(material, material+"InnerMaterial", outFile, "    ")
                    outFile.write("</bsdf>\n")
                else:
                    if materialType != "MitsubaObjectAreaLightShader":
                        writeShader(material, material, outFile, "")  #Write the shader to the xml file
                writtenMaterials.append(material)
        
    outFile.write("\n")
    outFile.write("<!-- End of materials -->")
    outFile.write("\n\n\n")

    objFiles = []

    #Write each piece of geometry
    for geom in geoms:
        shader = getShader(geom)
        if cmds.nodeType(shader) in materialNodeTypes:
            output = os.path.join(cwd, "renderData", geom + ".obj")
            cmds.select(geom)
            objFiles.append(cmds.file(output, op=True, typ="OBJexport", options="groups=1;ptgroups=1;materials=0;smoothing=1;normals=1", exportSelected=True, force=True))
            outFile.write("    <shape type=\"obj\">\n")
            outFile.write("        <string name=\"filename\" value=\"" + geom + ".obj\"/>\n")
            # Check for area lights
            if cmds.nodeType(shader) == "MitsubaObjectAreaLightShader":
                writeShader(shader, shader, outFile, "")
            else:
                outFile.write("        <ref id=\"" + shader + "\"/>\n")
            
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
                writeMedium(medium, outFile, "    ")

            outFile.write("    </shape>\n\n")
        elif cmds.nodeType(shader) == "MitsubaVolume":
            output = os.path.join(cwd, "renderData", geom + ".obj")
            cmds.select(geom)
            objFiles.append(cmds.file(output, op=True, typ="OBJexport", options="groups=1;ptgroups=1;materials=0;smoothing=1;normals=1", exportSelected=True, force=True))
            outFile.write("    <shape type=\"obj\">\n")
            outFile.write("        <string name=\"filename\" value=\"" + geom + ".obj\"/>\n")

            writeVolume(outFile, cwd, "    ", shader, geom)

            outFile.write("    </shape>\n\n")
            

    outFile.write("<!-- End of geometry -->")
    outFile.write("\n\n\n")
    return objFiles

def getVtxPos(shapeNode):
    vtxWorldPosition = []    # will contain positions un space of all object vertex
    vtxIndexList = cmds.getAttr( shapeNode+".vrts", multiIndices=True )
    for i in vtxIndexList :
        curPointPosition = cmds.xform( str(shapeNode)+".pnts["+str(i)+"]", query=True, translation=True, worldSpace=True )    # [1.1269192869360154, 4.5408735275268555, 1.3387055339628269]
        vtxWorldPosition.append( curPointPosition )
    return vtxWorldPosition

def writeVolume(outFile, cwd, tabbedSpace, material, geom):
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
        return

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

    outFile.write(tabbedSpace + "<medium type=\"heterogeneous\" name=\"interior\">\n")
    outFile.write(tabbedSpace + "    <string name=\"method\" value=\"woodcock\"/>\n")
    outFile.write(tabbedSpace + "    <volume name=\"density\" type=\"gridvolume\">\n")
    outFile.write(tabbedSpace + "        <string name=\"filename\" value=\"" + volFileName + "\"/>\n")
    outFile.write(tabbedSpace + "    </volume>\n")
    outFile.write(tabbedSpace + "    <volume name=\"albedo\" type=\"constvolume\">\n")
    outFile.write(tabbedSpace + "        <spectrum name=\"value\" value=\"0.9\"/>\n")
    outFile.write(tabbedSpace + "    </volume>\n")
    outFile.write(tabbedSpace + "</medium>\n")




def writeScene(outFileName, outDir):
    outFile = open(outFileName, 'w+')

    #Scene stuff
    outFile.write("<?xml version=\'1.0\' encoding=\'utf-8\'?>\n")
    outFile.write("\n")
    outFile.write("<scene version=\"0.5.0\">\n")

    #Write integrator
    writeIntegrator(outFile)

    #Write camera, sampler, and film
    writeSensor(outFile, 0)

    #Write lights
    writeLights(outFile)

    #Write geom and mats together since theyre inter-dependent
    geometryFiles = writeGeometryAndMaterials(outFile, outDir)
        
    outFile.write("\n")
    outFile.write("</scene>")
    outFile.close()

    return geometryFiles

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
        os.remove(logName)
    else:
        print( "Keeping temporary files" )

    return imageName

'''
This registers a mel command to render with Mitsuba
'''
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
                geometryFiles = writeScene(outFileName, projectDir)
        
                # Render scene, delete scene and geometry
                imageName = renderScene(outFileName, projectDir, mitsubaPath, 
                    mtsDir, keepTempFiles, geometryFiles, animation, frame)

                print("Rendering frame " + str(frame) + " - end" )
                time.sleep(2)
        else:
            # Export scene and geometry
            geometryFiles = writeScene(outFileName, projectDir)

            # Render scene, delete scene and geometry
            imageName = renderScene(outFileName, projectDir, mitsubaPath, 
                mtsDir, keepTempFiles, geometryFiles)

            # Display the render
            MitsubaRenderSettingsUI.showRender(imageName)

        '''
        Select the objects that the user had selected before
        they rendered, or clear the selection
        '''
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

        #mel.eval("mitsubaCreateRenderSettings()")

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

