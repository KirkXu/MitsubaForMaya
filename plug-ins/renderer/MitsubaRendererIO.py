import os
import struct

import maya.cmds as cmds
import maya.mel as mel
import maya.OpenMaya as OpenMaya
import maya.OpenMayaMPx as OpenMayaMPx

import pymel.core

from process import Process

# Will be populated as materials are registered with Maya
materialNodeTypes = []

#
# XML formatted printing
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
    
    # Simple formatting cheat to make the files a little more readable
    if depth == 1:
        elementText += "\n"

    return elementText

# Other options to be provided later
def writeElement(outFile, element, depth=0):
    elementText = writeElementText(element, depth)
    outFile.write(elementText)

#
# IO functions
#

#
# General functionality
#

# Returns the surfaceShader node for a piece of geometry (geom)
def getSurfaceShader(geom):
    shapeNode = cmds.listRelatives(geom, children=True, shapes=True, fullPath=True)[0]
    sg = cmds.listConnections(shapeNode, type="shadingEngine")[0]
    shader = cmds.listConnections(sg+".surfaceShader")
    #if shader is None:
    #    shader = cmds.listConnections(sg+".volumeShader")
    if shader:
        shader = shader[0]
    return shader

def getVolumeShader(geom):
    shapeNode = cmds.listRelatives(geom, children=True, shapes=True, fullPath=True)[0]
    sg = cmds.listConnections(shapeNode, type="shadingEngine")[0]
    shader = cmds.listConnections(sg+".volumeShader")
    if shader:
        shader = shader[0]
    return shader

def listToMitsubaText(list):
    return " ".join( map(str, list) )

def booleanToMisubaText(b):
    if b:
        return "true"
    else:
        return "false"

def createSceneElement(typeName=None, id=None, elementType='bsdf'):
    elementDict = {'type':elementType}
    if typeName:
        elementDict['attributes'] = { 'type':typeName }
    if id:
        elementDict['attributes']['id'] = id
    elementDict['children'] = []
    return elementDict

def createBooleanElement(name, value):
    return { 'type':'boolean', 'attributes':{ 'name':name, 'value':booleanToMisubaText(value) } }

def createIntegerElement(name, value):
    return { 'type':'integer', 'attributes':{ 'name':name, 'value':str(value) } }

def createFloatElement(name, value):
    return { 'type':'float', 'attributes':{ 'name':name, 'value':str(value) } }

def createStringElement(name, value):
    return { 'type':'string', 'attributes':{ 'name':name, 'value':str(value) } }

def createColorElement(name, value, colorspace='srgb'):
    return { 'type':colorspace, 'attributes':{ 'name':name, 'value':listToMitsubaText(value) } }

def createSpectrumElement(name, value):
    return { 'type':'spectrum', 'attributes':{ 'name':name, 'value':str(value) } }

def createNestedBSDFElement(material, connectedAttribute="bsdf", useDefault=True):
    hasNestedBSDF = False
    shaderElement = None

    connections = cmds.listConnections(material, connections=True)
    for i in range(len(connections)):
        if i%2==1:
            connection = connections[i]
            connectionType = cmds.nodeType(connection)

            if connectionType in materialNodeTypes and connections[i-1]==(material + "." + connectedAttribute):
                #We've found the nested bsdf, so build a structure for it
                shaderElement = writeShader(connection, connection)

                # Remove the id so there's no chance of this embedded definition conflicting with another
                # definition of the same BSDF
                if 'id' in shaderElement['attributes']:
                    del( shaderElement['attributes']['id'] )

                hasNestedBSDF = True

    if useDefault and not hasNestedBSDF:
        bsdf = cmds.getAttr(material + "." + connectedAttribute)

        shaderElement = createSceneElement('diffuse')
        shaderElement['children'].append( createColorElement('reflectance', bsdf[0], colorspace='srgb') )

    return shaderElement

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

def createTextureElement(name, texturePath, scale=None):
    textureElementDict = createSceneElement('bitmap', elementType='texture')
    textureElementDict['children'].append( createStringElement('filename', texturePath) )

    if scale:
        scaleElementDict = createSceneElement('scale', elementType='texture')
        scaleElementDict['children'].append( createFloatElement('scale', scale) )
        scaleElementDict['children'].append( textureElementDict )
        textureElementDict = scaleElementDict

    textureElementDict['attributes']['name'] = name
    return textureElementDict

def createVolumeElement(name, volumePath):
    volumeElementDict = createSceneElement('gridvolume', elementType='volume')
    volumeElementDict['attributes']['name'] = name
    volumeElementDict['children'].append( createStringElement('filename', volumePath) )

    return volumeElementDict

def createTexturedColorAttributeElement(material, attribute, mitsubaParameter=None, colorspace='srgb', scale=None):
    if not mitsubaParameter:
        mitsubaParameter = attribute
    fileTexture = getTextureFile(material, attribute)
    if fileTexture:
        element = createTextureElement(mitsubaParameter, fileTexture, scale)
    else:
        value = cmds.getAttr(material + "." + attribute)
        element = createColorElement(mitsubaParameter, value[0], colorspace )

    return element

def createTexturedFloatAttributeElement(material, attribute, mitsubaParameter=None, scale=None):
    if not mitsubaParameter:
        mitsubaParameter = attribute
    fileTexture = getTextureFile(material, attribute)
    if fileTexture:
        element = createTextureElement(mitsubaParameter, fileTexture, scale)
    else:
        value = cmds.getAttr(material + "." + attribute)
        element = createFloatElement(mitsubaParameter, value )

    return element

def createTexturedVolumeAttributeElement(material, attribute, mitsubaParameter=None):
    if not mitsubaParameter:
        mitsubaParameter = attribute
    fileTexture = getTextureFile(material, attribute)
    if fileTexture:
        element = createVolumeElement(mitsubaParameter, fileTexture)
    else:
        value = cmds.getAttr(material + "." + attribute)
        element = createSpectrumElement('value', value)

        volumeWrapperElement = createSceneElement('constvolume', elementType='volume')
        volumeWrapperElement['attributes']['name'] = mitsubaParameter
        volumeWrapperElement['children'].append( element )
        element = volumeWrapperElement

    return element

# UI to API name mappings
conductorUIToPreset = {
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

distributionUIToPreset = {
    "Beckmann" : "beckmann",
    "GGX" : "ggx",
    "Phong" : "phong",
    "Ashikhmin Shirley" : "as",
}

iorMaterialUIToPreset = {
    "Vacuum" : "vacuum",
    "Helum"  : "helium",
    "Hydrogen" : "hydrogen",
    "Air" : "air",
    "Carbon Dioxide" : "carbon dioxide",
    "Water" : "water",
    "Acetone" : "acetone",
    "Ethanol" : "ethanol",
    "Carbon Tetrachloride" : "carbon tetrachloride",
    "Glycerol" : "glycerol",
    "Benzene" : "benzene",
    "Silicone Oil" : "silicone oil",
    "Bromine" : "bromine",
    "Water Ice" : "water ice",
    "Fused Quartz" : "fused quartz",
    "Pyrex" : "pyrex",
    "Acrylic Glass" : "acrylic glass",
    "Polypropylene" : "polypropylene",
    "BK7" : "bk7",
    "Sodium Chloride" : "sodium chloride",
    "Amber" : "amber",
    "Pet" : "pet",
    "Diamond" : "diamond",
}

wardVariantUIToPreset = {
    "Ward" : "ward",
    "Ward-Duer" : "ward-duer",
    "Balanced" : "balanced",
}

mediumMaterialUIToPreset = {
    "Apple" : "Apple",
    "Cream" : "Cream",
    "Skimmilk" : "Skimmilk",
    "Spectralon" : "Spectralon",
    "Chicken1" : "Chicken1",
    "Ketchup" : "Ketchup",
    "Skin1" : "Skin1",
    "Wholemilk" : "Wholemilk",
    "Chicken2" : "Chicken2",
    "Potato" : "Potato",
    "Skin2" : "Skin2",
    "Lowfat Milk" : "Lowfat Milk",
    "Reduced Milk" : "Reduced Milk",
    "Regular Milk" : "Regular Milk",
    "Espresso" : "Espresso",
    "Mint Mocha Coffee" : "Mint Mocha Coffee",
    "Lowfat Soy Milk" : "Lowfat Soy Milk",
    "Regular Soy Milk" : "Regular Soy Milk",
    "Lowfat Chocolate Milk" : "Lowfat Chocolate Milk",
    "Regular Chocolate Milk" : "Regular Chocolate Milk",
    "Coke" : "Coke",
    "Pepsi Sprite" : "Pepsi Sprite",
    "Gatorade" : "Gatorade",
    "Chardonnay" : "Chardonnay",
    "White Zinfandel" : "White Zinfandel",
    "Merlot" : "Merlot",
    "Budweiser Beer" : "Budweiser Beer",
    "Coors Light Beer" : "Coors Light Beer",
    "Clorox" : "Clorox",
    "Apple Juice" : "Apple Juice",
    "Cranberry Juice" : "Cranberry Juice",
    "Grape Juice" : "Grape Juice",
    "Ruby Grapefruit Juice" : "Ruby Grapefruit Juice",
    "White Grapefruit Juice" : "White Grapefruit Juice",
    "Shampoo" : "Shampoo",
    "Strawberry Shampoo" : "Strawberry Shampoo",
    "Head & Shoulders Shampoo" : "Head & Shoulders Shampoo",
    "Lemon Tea Powder" : "Lemon Tea Powder",
    "Orange Juice Powder" : "Orange Juice Powder",
    "Pink Lemonade Powder" : "Pink Lemonade Powder",
    "Cappuccino Powder" : "Cappuccino Powder",
    "Salt Powder" : "Salt Powder",
    "Sugar Powder" : "Sugar Powder",
    "Suisse Mocha" : "Suisse Mocha",
}

phaseFunctionUIToPreset = {
    "Isotropic" : "isotropic",
    "Henyey-Greenstein" : "hg",
    "Rayleigh" : "rayleigh",
    "Kajiya-Kay" : "kkay",
    "Micro-Flake" : "microflake",
}

samplingMethodUIToPreset = {
    "Simpson" : "simpson",
    "Woodcock" : "woodcock",
}

#
# Medium Scattering Models
#

# A homogeneous medium
def writeMediumHomogeneous(medium, mediumName):
    useSigmaAS = cmds.getAttr(medium+".useSigmaAS")
    useSigmaTAlbedo = cmds.getAttr(medium+".useSigmaTAlbedo")
    sigmaA = cmds.getAttr(medium+".sigmaA")
    sigmaS = cmds.getAttr(medium+".sigmaS")
    sigmaT = cmds.getAttr(medium+".sigmaT")
    albedo = cmds.getAttr(medium+".albedo")
    scale = cmds.getAttr(medium+".scale")    

    # Create a structure to be written
    mediumElement = createSceneElement('homogeneous', mediumName, elementType='medium')

    if useSigmaAS:
        mediumElement['children'].append( createColorElement('sigmaA', sigmaA[0], colorspace='rgb') )
        mediumElement['children'].append( createColorElement('sigmaS', sigmaS[0], colorspace='rgb') )

    elif useSigmaTAlbedo:
        mediumElement['children'].append( createColorElement('sigmaT', sigmaT[0], colorspace='rgb') )
        mediumElement['children'].append( createColorElement('albedo', albedo[0], colorspace='rgb') )

    else:
        materialString = cmds.getAttr(medium+".material", asString=True)
        mediumElement['children'].append( createStringElement('material', materialString) )

    mediumElement['children'].append( createFloatElement('scale', scale) )

    phaseFunctionUIName = cmds.getAttr(medium+".phaseFunction", asString=True)
    if phaseFunctionUIName in phaseFunctionUIToPreset:
        phaseFunctionName = phaseFunctionUIToPreset[phaseFunctionUIName]

        phaseFunctionElement = createSceneElement(phaseFunctionName, elementType='phase')
        if phaseFunctionName == 'hg':
            g = cmds.getAttr(medium+".phaseFunctionHGG")
            phaseFunctionElement['children'].append( createFloatElement('g', g) )
        elif phaseFunctionName == 'microflake':
            s = cmds.getAttr(medium+".phaseFunctionMFSD")
            phaseFunctionElement['children'].append( createFloatElement('stddev', s) )

        mediumElement['children'].append( phaseFunctionElement  )

    return mediumElement

# A heterogeneous medium
def writeMediumHeterogeneous(medium, mediumName):
    # Create a structure to be written
    mediumElement = createSceneElement('heterogeneous', mediumName, elementType='medium')

    samplingMethodUIName = cmds.getAttr(medium+".samplingMethod", asString=True)
    if samplingMethodUIName in samplingMethodUIToPreset:
        samplingMethodName = samplingMethodUIToPreset[samplingMethodUIName]
    mediumElement['children'].append( createStringElement('method', samplingMethodName) )

    mediumElement['children'].append( createTexturedVolumeAttributeElement(medium, 'density') )
    mediumElement['children'].append( createTexturedVolumeAttributeElement(medium, 'albedo') )

    fileTexture = getTextureFile(medium, 'orientation')
    if fileTexture:
        mediumElement['children'].append( createVolumeElement('orientation', fileTexture) )

    scale = cmds.getAttr(medium+".scale")
    mediumElement['children'].append( createFloatElement('scale', scale) )

    phaseFunctionUIName = cmds.getAttr(medium+".phaseFunction", asString=True)
    if phaseFunctionUIName in phaseFunctionUIToPreset:
        phaseFunctionName = phaseFunctionUIToPreset[phaseFunctionUIName]

        phaseFunctionElement = createSceneElement(phaseFunctionName, elementType='phase')
        if phaseFunctionName == 'hg':
            g = cmds.getAttr(medium+".phaseFunctionHGG")
            phaseFunctionElement['children'].append( createFloatElement('g', g) )
        elif phaseFunctionName == 'microflake':
            s = cmds.getAttr(medium+".phaseFunctionMFSD")
            phaseFunctionElement['children'].append( createFloatElement('stddev', s) )

        mediumElement['children'].append( phaseFunctionElement  )

    return mediumElement


#
# Surface Scattering Models
#
def writeShaderSmoothCoating(material, materialName):
    bsdfElement = createSceneElement('coating', materialName)

    thickness = cmds.getAttr(material+".thickness")
    bsdfElement['children'].append( createFloatElement('thickness', thickness) )

    bsdfElement['children'].append( createTexturedColorAttributeElement(material, "sigmaA") )
    bsdfElement['children'].append( createTexturedColorAttributeElement(material, "specularReflectance") )

    # Get interior IOR preset or value
    interiorMaterialName = cmds.getAttr(material + ".interiorMaterial", asString=True)
    interiorMaterialName = interiorMaterialName.split('-')[0].strip()
    if interiorMaterialName in iorMaterialUIToPreset:
        interiorMaterialPreset = iorMaterialUIToPreset[interiorMaterialName]

        bsdfElement['children'].append( createStringElement('intIOR', interiorMaterialPreset)  )
    else:
        intIOR = cmds.getAttr(material+".intior")
        bsdfElement['children'].append( createFloatElement('intIOR', intIOR)  )

    # Get exterior IOR preset or value
    exteriorMaterialName = cmds.getAttr(material + ".exteriorMaterial", asString=True)
    exteriorMaterialName = exteriorMaterialName.split('-')[0].strip()
    if exteriorMaterialName in iorMaterialUIToPreset:
        exteriorMaterialPreset = iorMaterialUIToPreset[exteriorMaterialName]

        bsdfElement['children'].append( createStringElement('extIOR', exteriorMaterialPreset)  )
    else:
        extIOR = cmds.getAttr(material+".extior")
        bsdfElement['children'].append( createFloatElement('extIOR', extIOR)  )

    # Get connected BSDF
    nestedBSDFElement = createNestedBSDFElement(material, "bsdf")
    if nestedBSDFElement:
        bsdfElement['children'].append( nestedBSDFElement )

    return bsdfElement

def writeShaderConductor(material, materialName):
    extEta = cmds.getAttr(material+".extEta")

    conductorMaterialUI = cmds.getAttr(material+".material", asString=True)
    if conductorMaterialUI in conductorUIToPreset:
        conductorMaterialPreset = conductorUIToPreset[conductorMaterialUI]
    else:
        # Default to a perfectly reflective mirror
        conductorMaterialPreset = "none"

    # Create a structure to be written
    bsdfElement = createSceneElement('conductor', materialName)

    bsdfElement['children'].append( createStringElement('material', conductorMaterialPreset) )
    bsdfElement['children'].append( createFloatElement('extEta', extEta) )
    bsdfElement['children'].append( createTexturedColorAttributeElement(material, "specularReflectance") )

    return bsdfElement

def writeShaderDielectric(material, materialName):
    bsdfElement = createSceneElement('dielectric', materialName)

    # Get interior IOR preset or value
    interiorMaterialName = cmds.getAttr(material + ".interiorMaterial", asString=True)
    interiorMaterialName = interiorMaterialName.split('-')[0].strip()
    if interiorMaterialName in iorMaterialUIToPreset:
        interiorMaterialPreset = iorMaterialUIToPreset[interiorMaterialName]

        bsdfElement['children'].append( createStringElement('intIOR', interiorMaterialPreset)  )
    else:
        intIOR = cmds.getAttr(material+".intior")
        bsdfElement['children'].append( createFloatElement('intIOR', intIOR)  )

    # Get exterior IOR preset or value
    exteriorMaterialName = cmds.getAttr(material + ".exteriorMaterial", asString=True)
    exteriorMaterialName = exteriorMaterialName.split('-')[0].strip()
    if exteriorMaterialName in iorMaterialUIToPreset:
        exteriorMaterialPreset = iorMaterialUIToPreset[exteriorMaterialName]

        bsdfElement['children'].append( createStringElement('extIOR', exteriorMaterialPreset)  )
    else:
        extIOR = cmds.getAttr(material+".extior")
        bsdfElement['children'].append( createFloatElement('extIOR', extIOR)  )

    bsdfElement['children'].append( createTexturedColorAttributeElement(material, "specularReflectance") )
    bsdfElement['children'].append( createTexturedColorAttributeElement(material, "specularTransmittance") )

    return bsdfElement

def writeShaderDiffuseTransmitter(material, materialName):
    bsdfElement = createSceneElement('difftrans', materialName)
    bsdfElement['children'].append( createTexturedColorAttributeElement(material, "transmittance") )

    return bsdfElement

def writeShaderDiffuse(material, materialName):
    bsdfElement = createSceneElement('diffuse', materialName)
    bsdfElement['children'].append( createTexturedColorAttributeElement(material, "reflectance") )

    return bsdfElement

def writeShaderPhong(material, materialName):
    exponent = cmds.getAttr(material+".exponent")
    specularReflectance = cmds.getAttr(material+".specularReflectance")
    diffuseReflectance = cmds.getAttr(material+".diffuseReflectance")

    # Create a structure to be written
    bsdfElement = createSceneElement('phong', materialName)

    bsdfElement['children'].append( createTexturedFloatAttributeElement(material, "exponent")  )
    bsdfElement['children'].append( createTexturedColorAttributeElement(material, "diffuseReflectance") )
    bsdfElement['children'].append( createTexturedColorAttributeElement(material, "specularReflectance") )

    return bsdfElement

def writeShaderPlastic(material, materialName):
    bsdfElement = createSceneElement('plastic', materialName)

    # Get interior IOR preset or value
    interiorMaterialName = cmds.getAttr(material + ".interiorMaterial", asString=True)
    interiorMaterialName = interiorMaterialName.split('-')[0].strip()
    if interiorMaterialName in iorMaterialUIToPreset:
        interiorMaterialPreset = iorMaterialUIToPreset[interiorMaterialName]

        bsdfElement['children'].append( createStringElement('intIOR', interiorMaterialPreset)  )
    else:
        intIOR = cmds.getAttr(material+".intior")
        bsdfElement['children'].append( createFloatElement('intIOR', intIOR)  )

    # Get exterior IOR preset or value
    exteriorMaterialName = cmds.getAttr(material + ".exteriorMaterial", asString=True)
    exteriorMaterialName = exteriorMaterialName.split('-')[0].strip()
    if exteriorMaterialName in iorMaterialUIToPreset:
        exteriorMaterialPreset = iorMaterialUIToPreset[exteriorMaterialName]

        bsdfElement['children'].append( createStringElement('extIOR', exteriorMaterialPreset)  )
    else:
        extIOR = cmds.getAttr(material+".extior")
        bsdfElement['children'].append( createFloatElement('extIOR', extIOR)  )

    bsdfElement['children'].append( createTexturedColorAttributeElement(material, "diffuseReflectance") )
    bsdfElement['children'].append( createTexturedColorAttributeElement(material, "specularReflectance") )

    nonlinear = cmds.getAttr(material+".nonlinear")
    bsdfElement['children'].append( createBooleanElement('nonlinear', nonlinear)  )

    return bsdfElement

def writeShaderRoughCoating(material, materialName):
    bsdfElement = createSceneElement('roughcoating', materialName)

    thickness = cmds.getAttr(material+".thickness")
    bsdfElement['children'].append( createFloatElement('thickness', thickness) )
    bsdfElement['children'].append( createTexturedFloatAttributeElement(material, "alpha") )
    bsdfElement['children'].append( createTexturedColorAttributeElement(material, "sigmaA") )
    bsdfElement['children'].append( createTexturedColorAttributeElement(material, "specularReflectance") )

    distributionUI = cmds.getAttr(material+".distribution", asString=True)

    if distributionUI in distributionUIToPreset:
        distributionPreset = distributionUIToPreset[distributionUI]
    else:
        distributionPreset = "beckmann"

    bsdfElement['children'].append( createStringElement('distribution', distributionPreset) )

    # Get interior IOR preset or value
    interiorMaterialName = cmds.getAttr(material + ".interiorMaterial", asString=True)
    interiorMaterialName = interiorMaterialName.split('-')[0].strip()
    if interiorMaterialName in iorMaterialUIToPreset:
        interiorMaterialPreset = iorMaterialUIToPreset[interiorMaterialName]

        bsdfElement['children'].append( createStringElement('intIOR', interiorMaterialPreset)  )
    else:
        intIOR = cmds.getAttr(material+".intior")
        bsdfElement['children'].append( createFloatElement('intIOR', intIOR)  )

    # Get exterior IOR preset or value
    exteriorMaterialName = cmds.getAttr(material + ".exteriorMaterial", asString=True)
    exteriorMaterialName = exteriorMaterialName.split('-')[0].strip()
    if exteriorMaterialName in iorMaterialUIToPreset:
        exteriorMaterialPreset = iorMaterialUIToPreset[exteriorMaterialName]

        bsdfElement['children'].append( createStringElement('extIOR', exteriorMaterialPreset)  )
    else:
        extIOR = cmds.getAttr(material+".extior")
        bsdfElement['children'].append( createFloatElement('extIOR', extIOR)  )

    # Get connected BSDF
    nestedBSDFElement = createNestedBSDFElement(material, "bsdf")
    if nestedBSDFElement:
        bsdfElement['children'].append( nestedBSDFElement )

    return bsdfElement

def writeShaderRoughConductor(material, materialName):
    distributionUI = cmds.getAttr(material+".distribution", asString=True)
    alphaUV = cmds.getAttr(material+".alphaUV")
    alpha = cmds.getAttr(material+".alpha")
    conductorMaterialUI = cmds.getAttr(material+".material")
    extEta = cmds.getAttr(material+".extEta")

    if distributionUI in distributionUIToPreset:
        distributionPreset = distributionUIToPreset[distributionUI]
    else:
        distributionPreset = "beckmann"

    if conductorMaterialUI in conductorUIToPreset:
        conductorMaterialPreset = conductorUIToPreset[conductorMaterialUI]
    else:
        conductorMaterialPreset = "Cu"

    # Create a structure to be written
    bsdfElement = createSceneElement('roughconductor', materialName)

    bsdfElement['children'].append( createStringElement('distribution', distributionPreset) )
    if distributionPreset == "as":
        bsdfElement['children'].append( createFloatElement('alphaU', alphaUV[0]) )
        bsdfElement['children'].append( createFloatElement('alphaV', alphaUV[1]) )
    else:
        bsdfElement['children'].append( createFloatElement('alpha', alpha) )

    bsdfElement['children'].append( createStringElement('material', conductorMaterialPreset) )
    bsdfElement['children'].append( createFloatElement('extEta', extEta) )

    bsdfElement['children'].append( createTexturedColorAttributeElement(material, "specularReflectance") )

    return bsdfElement

def writeShaderRoughDielectric(material, materialName):
    bsdfElement = createSceneElement('roughdielectric', materialName)

    distributionUI = cmds.getAttr(material+".distribution", asString=True)
    if distributionUI in distributionUIToPreset:
        distributionPreset = distributionUIToPreset[distributionUI]
    else:
        distributionPreset = "beckmann"

    bsdfElement['children'].append( createStringElement('distribution', distributionPreset) )
    if distributionPreset == "as":
        alphaUV = cmds.getAttr(material+".alphaUV")
        bsdfElement['children'].append( createFloatElement('alphaU', alphaUV[0])  )
        bsdfElement['children'].append( createFloatElement('alphaV', alphaUV[1])  )
    else:
        alpha = cmds.getAttr(material+".alpha")
        bsdfElement['children'].append( createTexturedFloatAttributeElement(material, "alpha") )

    # Get interior IOR preset or value
    interiorMaterialName = cmds.getAttr(material + ".interiorMaterial", asString=True)
    interiorMaterialName = interiorMaterialName.split('-')[0].strip()
    if interiorMaterialName in iorMaterialUIToPreset:
        interiorMaterialPreset = iorMaterialUIToPreset[interiorMaterialName]

        bsdfElement['children'].append( createStringElement('intIOR', interiorMaterialPreset)  )
    else:
        intIOR = cmds.getAttr(material+".intior")
        bsdfElement['children'].append( createFloatElement('intIOR', intIOR)  )

    # Get exterior IOR preset or value
    exteriorMaterialName = cmds.getAttr(material + ".exteriorMaterial", asString=True)
    exteriorMaterialName = exteriorMaterialName.split('-')[0].strip()
    if exteriorMaterialName in iorMaterialUIToPreset:
        exteriorMaterialPreset = iorMaterialUIToPreset[exteriorMaterialName]

        bsdfElement['children'].append( createStringElement('extIOR', exteriorMaterialPreset)  )
    else:
        extIOR = cmds.getAttr(material+".extior")
        bsdfElement['children'].append( createFloatElement('extIOR', extIOR)  )

    bsdfElement['children'].append( createTexturedColorAttributeElement(material, "specularReflectance") )
    bsdfElement['children'].append( createTexturedColorAttributeElement(material, "specularTransmittance") )

    return bsdfElement

def writeShaderRoughDiffuse(material, materialName):
    alpha = cmds.getAttr(material+".alpha")
    useFastApprox = cmds.getAttr(material+".useFastApprox")

    # Create a structure to be written
    bsdfElement = createSceneElement('roughdiffuse', materialName)

    bsdfElement['children'].append( createTexturedColorAttributeElement(material, "reflectance") )
    bsdfElement['children'].append( createFloatElement('alpha', alpha)  )
    bsdfElement['children'].append( createBooleanElement('useFastApprox', useFastApprox)  )

    return bsdfElement

def writeShaderRoughPlastic(material, materialName):
    bsdfElement = createSceneElement('roughplastic', materialName)

    bsdfElement['children'].append( createTexturedColorAttributeElement(material, "specularReflectance") )
    bsdfElement['children'].append( createTexturedColorAttributeElement(material, "diffuseReflectance") )

    distributionUI = cmds.getAttr(material+".distribution", asString=True)
    if distributionUI in distributionUIToPreset:
        distributionPreset = distributionUIToPreset[distributionUI]
    else:
        distributionPreset = "beckmann"

    bsdfElement['children'].append( createStringElement('distribution', distributionPreset) )

    alpha = cmds.getAttr(material+".alpha")
    bsdfElement['children'].append( createTexturedFloatAttributeElement(material, "alpha") )

    # Get interior IOR preset or value
    interiorMaterialName = cmds.getAttr(material + ".interiorMaterial", asString=True)
    interiorMaterialName = interiorMaterialName.split('-')[0].strip()
    if interiorMaterialName in iorMaterialUIToPreset:
        interiorMaterialPreset = iorMaterialUIToPreset[interiorMaterialName]

        bsdfElement['children'].append( createStringElement('intIOR', interiorMaterialPreset)  )
    else:
        intIOR = cmds.getAttr(material+".intior")
        bsdfElement['children'].append( createFloatElement('intIOR', intIOR)  )

    # Get exterior IOR preset or value
    exteriorMaterialName = cmds.getAttr(material + ".exteriorMaterial", asString=True)
    exteriorMaterialName = exteriorMaterialName.split('-')[0].strip()
    if exteriorMaterialName in iorMaterialUIToPreset:
        exteriorMaterialPreset = iorMaterialUIToPreset[exteriorMaterialName]

        bsdfElement['children'].append( createStringElement('extIOR', exteriorMaterialPreset)  )
    else:
        extIOR = cmds.getAttr(material+".extior")
        bsdfElement['children'].append( createFloatElement('extIOR', extIOR)  )

    nonlinear = cmds.getAttr(material+".nonlinear")
    bsdfElement['children'].append( createBooleanElement('nonlinear', nonlinear) )

    return bsdfElement

def writeShaderThinDielectric(material, materialName):
    bsdfElement = createSceneElement('thindielectric', materialName)

    # Get interior IOR preset or value
    interiorMaterialName = cmds.getAttr(material + ".interiorMaterial", asString=True)
    interiorMaterialName = interiorMaterialName.split('-')[0].strip()
    if interiorMaterialName in iorMaterialUIToPreset:
        interiorMaterialPreset = iorMaterialUIToPreset[interiorMaterialName]

        bsdfElement['children'].append( createStringElement('intIOR', interiorMaterialPreset)  )
    else:
        intIOR = cmds.getAttr(material+".intior")
        bsdfElement['children'].append( createFloatElement('intIOR', intIOR)  )

    # Get exterior IOR preset or value
    exteriorMaterialName = cmds.getAttr(material + ".exteriorMaterial", asString=True)
    exteriorMaterialName = exteriorMaterialName.split('-')[0].strip()
    if exteriorMaterialName in iorMaterialUIToPreset:
        exteriorMaterialPreset = iorMaterialUIToPreset[exteriorMaterialName]

        bsdfElement['children'].append( createStringElement('extIOR', exteriorMaterialPreset)  )
    else:
        extIOR = cmds.getAttr(material+".extior")
        bsdfElement['children'].append( createFloatElement('extIOR', extIOR)  )

    bsdfElement['children'].append( createTexturedColorAttributeElement(material, "specularReflectance") )
    bsdfElement['children'].append( createTexturedColorAttributeElement(material, "specularTransmittance") )

    return bsdfElement


def writeShaderWard(material, materialName):
    bsdfElement = createSceneElement('ward', materialName)

    variant = cmds.getAttr(material+".variant", asString=True)
    if variant in wardVariantUIToPreset:
        variantPreset = wardVariantUIToPreset[variant]
    else:
        variantPreset = "balanced"

    bsdfElement['children'].append( createStringElement('variant', variantPreset)  )

    bsdfElement['children'].append( createTexturedFloatAttributeElement(material, "alphaU") )
    bsdfElement['children'].append( createTexturedFloatAttributeElement(material, "alphaV") )

    bsdfElement['children'].append( createTexturedColorAttributeElement(material, "diffuseReflectance") )
    bsdfElement['children'].append( createTexturedColorAttributeElement(material, "specularReflectance") )

    return bsdfElement

def writeShaderIrawan(material, materialName):
    filename = cmds.getAttr(material+".filename", asString=True)
    repeatu = cmds.getAttr(material+".repeatu")
    repeatv = cmds.getAttr(material+".repeatv")
    warpkd = cmds.getAttr(material+".warpkd")
    warpks = cmds.getAttr(material+".warpks")
    weftkd = cmds.getAttr(material+".weftkd")
    weftks = cmds.getAttr(material+".weftks")

    bsdfElement = createSceneElement('irawan', materialName)

    bsdfElement['children'].append( createStringElement('filename', filename) )
    bsdfElement['children'].append( createFloatElement('repeatU', repeatu) )
    bsdfElement['children'].append( createFloatElement('repeatV', repeatv) )

    bsdfElement['children'].append( createColorElement('warp_kd', warpkd[0], colorspace='rgb') )
    bsdfElement['children'].append( createColorElement('warp_ks', warpks[0], colorspace='rgb') )

    bsdfElement['children'].append( createColorElement('weft_kd', weftkd[0], colorspace='rgb') )
    bsdfElement['children'].append( createColorElement('weft_ks', weftks[0], colorspace='rgb') )

    return bsdfElement

def writeShaderTwoSided(material, materialName):
    bsdfElement = createSceneElement('twosided', materialName)

    frontBSDFElement = createNestedBSDFElement(material, "frontBSDF")
    bsdfElement['children'].append( frontBSDFElement )

    backBSDFElement = createNestedBSDFElement(material, "backBSDF", useDefault=False)
    if backBSDFElement:
        bsdfElement['children'].append( backBSDFElement )

    return bsdfElement

def writeShaderMixture(material, materialName):
    bsdfElement = createSceneElement('mixturebsdf', materialName)

    weight1 = cmds.getAttr(material+".weight1")
    weight2 = cmds.getAttr(material+".weight2")
    weight3 = cmds.getAttr(material+".weight3")
    weight4 = cmds.getAttr(material+".weight4")

    weights = [weight1, weight2, weight3, weight4]
    weights = [x for x in weights if x != 0]
    weightString = ", ".join(map(str, weights))

    if weight1 > 0.0:
        bsdf1Element = createNestedBSDFElement(material, "bsdf1")
        bsdfElement['children'].append( bsdf1Element )

    if weight2 > 0.0:
        bsdf2Element = createNestedBSDFElement(material, "bsdf2")
        bsdfElement['children'].append( bsdf2Element )

    if weight3 > 0.0:
        bsdf3Element = createNestedBSDFElement(material, "bsdf3")
        bsdfElement['children'].append( bsdf3Element )

    if weight4 > 0.0:
        bsdf4Element = createNestedBSDFElement(material, "bsdf4")
        bsdfElement['children'].append( bsdf4Element )

    bsdfElement['children'].append( createStringElement('weights', weightString) )

    return bsdfElement

def writeShaderBlend(material, materialName):
    bsdfElement = createSceneElement('blendbsdf', materialName)

    bsdfElement['children'].append( createTexturedFloatAttributeElement(material, "weight") )

    bsdf1Element = createNestedBSDFElement(material, "bsdf1")
    bsdfElement['children'].append( bsdf1Element )

    bsdf2Element = createNestedBSDFElement(material, "bsdf2")
    bsdfElement['children'].append( bsdf2Element )

    return bsdfElement

def writeShaderMask(material, materialName):
    bsdfElement = createSceneElement('mask', materialName)

    bsdfElement['children'].append( createTexturedColorAttributeElement(material, "opacity") )

    bsdf1Element = createNestedBSDFElement(material, "bsdf")
    bsdfElement['children'].append( bsdf1Element )

    return bsdfElement

def writeShaderBump(material, materialName):
    bsdfElement = createSceneElement('bumpmap', materialName)

    bumpScale = cmds.getAttr(material+".bumpScale")
    bsdfElement['children'].append( createTexturedColorAttributeElement(material, "texture", scale=bumpScale) )

    bsdf1Element = createNestedBSDFElement(material, "bsdf")
    bsdfElement['children'].append( bsdf1Element )

    return bsdfElement

def writeShaderHK(material, materialName):
    bsdfElement = createSceneElement('hk', materialName)

    useSigmaSA = cmds.getAttr(material+".useSigmaSA")
    useSigmaTAlbedo = cmds.getAttr(material+".useSigmaTAlbedo")
    if useSigmaSA:
        bsdfElement['children'].append( createTexturedColorAttributeElement(material, "sigmaS") )
        bsdfElement['children'].append( createTexturedColorAttributeElement(material, "sigmaA") )

    elif useSigmaTAlbedo:
        bsdfElement['children'].append( createTexturedColorAttributeElement(material, "sigmaT") )
        bsdfElement['children'].append( createTexturedColorAttributeElement(material, "albedo") )

    else:
        materialString = cmds.getAttr(material+".material", asString=True)
        bsdfElement['children'].append( createStringElement('material', materialString) )

    thickness = cmds.getAttr(material+".thickness")
    bsdfElement['children'].append( createFloatElement('thickness', thickness) )

    phaseFunctionUIName = cmds.getAttr(material+".phaseFunction", asString=True)
    if phaseFunctionUIName in phaseFunctionUIToPreset:
        phaseFunctionName = phaseFunctionUIToPreset[phaseFunctionUIName]

        phaseFunctionElement = createSceneElement(phaseFunctionName, elementType='phase')
        if phaseFunctionName == 'hg':
            g = cmds.getAttr(material+".phaseFunctionHGG")
            phaseFunctionElement['children'].append( createFloatElement('g', g) )
        elif phaseFunctionName == 'microflake':
            s = cmds.getAttr(material+".phaseFunctionMFSD")
            phaseFunctionElement['children'].append( createFloatElement('stddev', s) )

        bsdfElement['children'].append( phaseFunctionElement  )

    return bsdfElement

def writeShaderObjectAreaLight(material, materialName):
    elementDict = createSceneElement('area', materialName, 'emitter')

    color = cmds.getAttr(material+".radiance")
    samplingWeight = cmds.getAttr(material+".samplingWeight")

    elementDict['children'].append( createColorElement('radiance', color[0], colorspace='rgb') )
    elementDict['children'].append( createFloatElement('samplingWeight', samplingWeight) )

    return elementDict

def writeShaderDipoleSSS(material, materialName):
    # roughplastic bsdf
    bsdfElement = createSceneElement('roughplastic')

    bsdfElement['children'].append( createTexturedColorAttributeElement(material, "specularReflectance") )

    distributionUI = cmds.getAttr(material+".surfaceDistribution", asString=True)
    if distributionUI in distributionUIToPreset:
        distributionPreset = distributionUIToPreset[distributionUI]
    else:
        distributionPreset = "beckmann"

    bsdfElement['children'].append( createStringElement('distribution', distributionPreset) )

    bsdfElement['children'].append( createTexturedFloatAttributeElement(material, "surfaceAlpha", mitsubaParameter="alpha") )

    # Get interior IOR preset or value
    interiorMaterialName = cmds.getAttr(material + ".interiorMaterial", asString=True)
    interiorMaterialName = interiorMaterialName.split('-')[0].strip()
    if interiorMaterialName in iorMaterialUIToPreset:
        interiorMaterialPreset = iorMaterialUIToPreset[interiorMaterialName]

        bsdfElement['children'].append( createStringElement('intIOR', interiorMaterialPreset)  )
    else:
        intIOR = cmds.getAttr(material+".intior")
        bsdfElement['children'].append( createFloatElement('intIOR', intIOR)  )

    # Get exterior IOR preset or value
    exteriorMaterialName = cmds.getAttr(material + ".exteriorMaterial", asString=True)
    exteriorMaterialName = exteriorMaterialName.split('-')[0].strip()
    if exteriorMaterialName in iorMaterialUIToPreset:
        exteriorMaterialPreset = iorMaterialUIToPreset[exteriorMaterialName]

        bsdfElement['children'].append( createStringElement('extIOR', exteriorMaterialPreset)  )
    else:
        extIOR = cmds.getAttr(material+".extior")
        bsdfElement['children'].append( createFloatElement('extIOR', extIOR)  )

    nonlinear = cmds.getAttr(material+".nonlinear")
    bsdfElement['children'].append( createBooleanElement('nonlinear', nonlinear) )

    useSingleScatteringModel = cmds.getAttr(material+".useSingleScatteringModel")

    # dipole sss
    sssElement = createSceneElement('dipole', elementType='subsurface')

    useSigmaSA = cmds.getAttr(material+".useSigmaSA")
    useSigmaTAlbedo = cmds.getAttr(material+".useSigmaTAlbedo")
    if useSigmaSA:
        sigmaS = cmds.getAttr(material+".sigmaS")
        sigmaA = cmds.getAttr(material+".sigmaA")
        sssElement['children'].append( createColorElement("sigmaS", sigmaS[0]) )
        sssElement['children'].append( createColorElement("sigmaA", sigmaA[0]) )

    elif useSigmaTAlbedo:
        sigmaT = cmds.getAttr(material+".sigmaT")
        albedo = cmds.getAttr(material+".albedo")
        sssElement['children'].append( createColorElement("sigmaT", sigmaT[0]) )
        sssElement['children'].append( createColorElement("albedo", albedo[0]) )

    else:
        materialString = cmds.getAttr(material+".material", asString=True)
        sssElement['children'].append( createStringElement('material', materialString) )

    scale = cmds.getAttr(material+".scale")
    sssElement['children'].append( createFloatElement("scale", scale) )

    irrSamples = cmds.getAttr(material+".irrSamples")
    sssElement['children'].append( createIntegerElement("irrSamples", irrSamples) )

    # Get interior IOR preset or value
    interiorMaterialName = cmds.getAttr(material + ".interiorMaterial", asString=True)
    interiorMaterialName = interiorMaterialName.split('-')[0].strip()
    if interiorMaterialName in iorMaterialUIToPreset:
        interiorMaterialPreset = iorMaterialUIToPreset[interiorMaterialName]

        sssElement['children'].append( createStringElement('intIOR', interiorMaterialPreset)  )
    else:
        intIOR = cmds.getAttr(material+".intior")
        sssElement['children'].append( createFloatElement('intIOR', intIOR)  )

    # Get exterior IOR preset or value
    exteriorMaterialName = cmds.getAttr(material + ".exteriorMaterial", asString=True)
    exteriorMaterialName = exteriorMaterialName.split('-')[0].strip()
    if exteriorMaterialName in iorMaterialUIToPreset:
        exteriorMaterialPreset = iorMaterialUIToPreset[exteriorMaterialName]

        sssElement['children'].append( createStringElement('extIOR', exteriorMaterialPreset)  )
    else:
        extIOR = cmds.getAttr(material+".extior")
        sssElement['children'].append( createFloatElement('extIOR', extIOR)  )

    if not useSingleScatteringModel:
        bsdfElement = None

    return sssElement, bsdfElement


'''
Write a surface material (material) to a Mitsuba scene file (outFile)
'''
def writeShader(material, materialName):
    matType = cmds.nodeType(material)
    
    mayaMaterialTypeToShaderFunction = {
        "MitsubaSmoothCoatingShader" : writeShaderSmoothCoating,
        "MitsubaConductorShader" : writeShaderConductor,
        "MitsubaDielectricShader" : writeShaderDielectric,
        "MitsubaDiffuseTransmitterShader" : writeShaderDiffuseTransmitter,
        "MitsubaDiffuseShader" : writeShaderDiffuse,
        "MitsubaPhongShader" : writeShaderPhong,
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
        "MitsubaMixtureShader" : writeShaderMixture,
        "MitsubaBlendShader" : writeShaderBlend,
        "MitsubaMaskShader" : writeShaderMask,
        "MitsubaBumpShader" : writeShaderBump,
        "MitsubaHKShader" : writeShaderHK,
        "MitsubaHomogeneousParticipatingMedium" : writeMediumHomogeneous,
        "MitsubaHeterogeneousParticipatingMedium" : writeMediumHeterogeneous,
    }

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
    cams = cmds.ls(type="camera", long=True)
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
        'attributes':{ 'target':listToMitsubaText(camAim), 
            'origin':listToMitsubaText(camPos),
             'up':listToMitsubaText(camUp) } } )

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

    elementDict['children'].append( { 'type':'rgb', 
        'attributes':{ 'name':'irradiance', 'value':listToMitsubaText(irradiance) } } )
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

    elementDict['children'].append( { 'type':'rgb', 
        'attributes':{ 'name':'intensity', 'value':listToMitsubaText(irradiance) } } )
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

    transform = cmds.listRelatives( light, parent=True, fullPath=True )[0]
    rotation = cmds.getAttr(transform+".rotate")[0]

    # Create a structure to be written
    elementDict = {'type':'emitter'}
    elementDict['attributes'] = {'type':'spot'}

    elementDict['children'] = []

    elementDict['children'].append( { 'type':'rgb', 
        'attributes':{ 'name':'intensity', 'value':listToMitsubaText(irradiance) } } )
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
        'attributes':{ 'name':'albedo', 'value':listToMitsubaText(albedo[0]) } } )

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

            elementDict['children'].append( { 'type':'rgb', 
                'attributes':{ 'name':'radiance', 'value':listToMitsubaText(radiance[0]) } } )
            elementDict['children'].append( { 'type':'float', 
                'attributes':{ 'name':'samplingWeight', 'value':str(samplingWeight) } } )

            return elementDict


'''
Write lights
'''
def isVisible(object):
    print( "Checking visibility : %s" % object )
    visible = True

    if cmds.attributeQuery("visibility", node=object, exists=True):
        visible = visible and cmds.getAttr(object+".visibility")

    if cmds.attributeQuery("intermediateObject", node=object, exists=True):
        visible = visible and not cmds.getAttr(object+".intermediateObject")

    if cmds.attributeQuery("overrideEnabled", node=object, exists=True):
        visible = visible and cmds.getAttr(object+".overrideVisibility")

    if visible:
        parents = cmds.listRelatives(object, fullPath=True, parent=True)
        if parents:
            for parent in parents:
                parentVisible = isVisible(parent)
                if not parentVisible:
                    print( "\tParent not visible. Breaking : %s" % parent )
                    visible = False
                    break
                
    print( "\tVisibility : %s" % visible )
    
    return visible

def writeLights():
    lights = cmds.ls(type="light", long=True)
    sunskyLights = cmds.ls(type="MitsubaSunsky", long=True)
    envLights = cmds.ls(type="MitsubaEnvironmentLight", long=True)

    if sunskyLights and envLights or sunskyLights and len(sunskyLights)>1 or envLights and len(envLights)>1:
        print "Cannot specify more than one environment light (MitsubaSunsky and MitsubaEnvironmentLight)"
        # print "Defaulting to constant environment emitter"
        # outFile.write(" <emitter type=\"constant\"/>\n")

    lightElements = []

    # Gather element definitions for standard lights
    for light in lights:
        if isVisible(light):
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
        if isVisible(sunsky):
            lightElements.append( writeLightSunSky(sunsky) )

    # Gather element definitions for Environment lights
    if envLights:
        envmap = envLights[0]
        if isVisible(envmap):
            lightElements.append( writeLightEnvMap(envmap) )

    return lightElements

def getRenderableGeometry():
    # Build list of visible geometry
    transforms = cmds.ls(type="transform", long=True)
    geoms = []

    for transform in transforms:
        rels = cmds.listRelatives(transform, fullPath=True)
        if rels:
            for rel in rels:
                if cmds.nodeType(rel)=="mesh":
                    visible = isVisible(transform)
                    if visible:
                        if transform not in geoms:
                            geoms.append(transform)
                            #print( "getRenderableGeometry - transform : %s" % transform )

    return geoms

def addTwoSided(material, materialElement):
    # Create a structure to be written
    elementDict = createSceneElement('twosided', material)

    materialElement['attributes']['id'] = material + "InnerMaterial"
    elementDict['children'].append(materialElement)
    
    return elementDict


def writeMaterials(geoms):
    writtenMaterials = []
    materialElements = []

    #Write the material for each piece of geometry in the scene
    for geom in geoms:
        #print( "writeMaterials - geom : %s" % geom )
        # Surface shader
        material = getSurfaceShader(geom)
        if material and material not in writtenMaterials:

            materialType = cmds.nodeType(material)
            if materialType in materialNodeTypes:
                if materialType not in ["MitsubaObjectAreaLightShader", "MitsubaSSSDipoleShader"]:
                    materialElement = writeShader(material, material)

                    if "twosided" in cmds.listAttr(material) and cmds.getAttr(material+".twosided"):
                            materialElement = addTwoSided(material, materialElement)

                    materialElements.append(materialElement)
                    writtenMaterials.append(material)

        # Medium / Volume shaders
        mediumMaterial = getVolumeShader(geom)
        if mediumMaterial and mediumMaterial not in writtenMaterials:

            materialType = cmds.nodeType(mediumMaterial)
            if materialType in materialNodeTypes:
                mediumMaterialElement = writeShader(mediumMaterial, mediumMaterial)

                materialElements.append(mediumMaterialElement)
                writtenMaterials.append(mediumMaterial)
        
    return writtenMaterials, materialElements

def exportGeometry(geom, renderDir):
    geomFilename = geom.replace(':', '__').replace('|', '__')

    cmds.select(geom)

    objFilenameFullPath = os.path.join(renderDir, geomFilename + ".obj")
    objFile = cmds.file(objFilenameFullPath, op=True, typ="OBJexport", options="groups=1;ptgroups=1;materials=0;smoothing=1;normals=1", exportSelected=True, force=True)

    return objFilenameFullPath

def writeShape(geomFilename, surfaceShader, mediumShader, renderDir):
    shapeDict = createSceneElement('obj', elementType='shape')

    # Add reference to exported geometry
    shapeDict['children'].append( createStringElement('filename', geomFilename) )

    # Write medium shader
    if mediumShader and cmds.nodeType(mediumShader) in materialNodeTypes:
        refDict = createSceneElement(elementType='ref')
        refDict['attributes'] = {'name':'interior', 'id':mediumShader}

        shapeDict['children'].append(refDict)

    # Write surface shader
    if surfaceShader and cmds.nodeType(surfaceShader) in materialNodeTypes:
        # Check for area lights
        if cmds.nodeType(surfaceShader) == "MitsubaObjectAreaLightShader":
            shaderElement = writeShaderObjectAreaLight(surfaceShader, surfaceShader)
            shapeDict['children'].append(shaderElement)

        # Check for dipole sss
        elif cmds.nodeType(surfaceShader) == "MitsubaSSSDipoleShader":
            sssElement, bsdfElement = writeShaderDipoleSSS(surfaceShader, surfaceShader)
            shapeDict['children'].append(sssElement)
            if bsdfElement:
                shapeDict['children'].append(bsdfElement)

        # Otherwise refer to the already written material
        else:
            refDict = createSceneElement(elementType='ref')
            refDict['attributes'] = {'id':surfaceShader}

            shapeDict['children'].append(refDict)
    
    return shapeDict


def writeGeometryAndMaterials(renderDir):
    geoms = getRenderableGeometry()

    writtenMaterials, materialElements = writeMaterials(geoms)

    geoFiles = []
    shapeElements = []

    #Write each piece of geometry with references to materials
    for geom in geoms:
        #print( "writeGeometryAndMaterials - geometry : %s" % geom )
        surfaceShader = getSurfaceShader(geom)
        volumeShader  = getVolumeShader(geom)

        #print( "\tsurface : %s" % surfaceShader )
        #print( "\tvolume  : %s" % volumeShader )

        geomFilename = exportGeometry(geom, renderDir)
        geoFiles.append(geomFilename)

        shapeElement = writeShape(geomFilename, surfaceShader, volumeShader, renderDir)
        shapeElements.append(shapeElement)

    return (geoFiles, shapeElements, materialElements)

def writeScene(outFileName, renderDir, renderSettings):
    #
    # Generate scene element hierarchy
    #
    sceneElement = createSceneElement(elementType='scene')

    # Should make this query the binary...
    sceneElement['attributes'] = {'version':'0.5.0'}

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

    #
    # Write the structure to disk
    #
    with open(outFileName, 'w+') as outFile:
        outFile.write("<?xml version=\'1.0\' encoding=\'utf-8\'?>\n")
        writeElement(outFile, sceneElement)

    return exportedGeometryFiles
