#!/usr/bin/python3
# -*- coding: utf-8 -*-

# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

import bpy
import mathutils
import random
import math

standardMaterialLayerFieldNames = ["diffuseLayer", "decalLayer", "specularLayer", "selfIllumLayer",
    "emissiveLayer", "reflectionLayer", "evioLayer", "evioMaskLayer", "alphaMaskLayer", 
    "bumpLayer", "heightLayer", "layer12", "layer13"]

standardMaterialLayerNames = ["Diffuse", "Decal", "Specular", "Self Illumination", 
    "Emissive", "Reflection", "Evio", "Evio Mask", "Alpha Mask", "Bump", "Height", "Layer 12", "Layer 13"]

displacementMaterialLayerFieldNames = ["normalLayer", "strengthLayer"]
displacementMaterialLayerNames = ["Normal", "Strength"]

terrainMaterialLayerFieldNames = ["layer"]
terrainMaterialLayerNames = ["Terrain"]

volumeMaterialLayerFieldNames = ["colorDefiningLayer", "unknownLayer2", "unknownLayer3"]
volumeMaterialLayerNames = ["Color Defining Layer", "Layer 2", "Layer 3"]


materialNames = ["No Material", "Standard", "Displacement", "Composite", "Terrain", "Volume"]
standardMaterialTypeIndex = 1
displacementMaterialTypeIndex = 2
compositeMaterialTypeIndex = 3
terrainMaterialTypeIndex = 4
volumeMaterialTypeIndex = 5

tightHitTestBoneName = "HitTestTight"

rotFixMatrix = mathutils.Matrix((( 0, 1, 0, 0,),
                                 (-1, 0, 0, 0),
                                 ( 0, 0, 1, 0),
                                 ( 0, 0, 0, 1)))
rotFixMatrixInverted = rotFixMatrix.transposed()

animFlagsForAnimatedProperty = 6

star2ParticlePrefix = "Star2Part"
star2ForcePrefix = "Star2Force"
animObjectIdModel = "MODEL"
animObjectIdArmature = "ARMATURE"
animObjectIdScene = "SCENE"
lightPrefixMap = {"1": "Star2Omni", "2": "Star2Spot"}


def toValidBoneName(name):
    maxLength = 31
    return name[:maxLength]    

def boneNameForPartileSystem(boneSuffix):
    return toValidBoneName(star2ParticlePrefix + boneSuffix)
    
def boneNameForForce(boneSuffix):
    return toValidBoneName(star2ForcePrefix + boneSuffix)

def boneNameForLight(boneSuffix, lightType):
    lightPrefix = lightPrefixMap.get(lightType)
    if lightPrefix == None:
        raise Exception("No prefix is known for light %s" % lightType)
    else:
        return toValidBoneName(lightPrefix + boneSuffix)
        
def boneNameForPartileSystemCopy(particleSystem, copy):
    return toValidBoneName(star2ParticlePrefix + copy.name)

def locRotScaleMatrix(location, rotation, scale):
    """ Important: rotation must be a normalized quaternion """
    # to_matrix() only works properly with normalized quaternions.
    result = rotation.to_matrix().to_4x4()
    result.col[0] *= scale.x
    result.col[1] *= scale.y
    result.col[2] *= scale.z
    result.translation = location
    return result

def setAnimationWithIndexToCurrentData(scene, animationIndex):
    if (animationIndex < 0) or (animationIndex >= len(scene.m3_animations)):
        return
    animation = scene.m3_animations[animationIndex]
    animation.startFrame = scene.frame_start
    animation.exlusiveEndFrame = scene.frame_end+1
    while len(animation.assignedActions) > 0:
        animation.assignedActions.remove(0)

    for targetObject in bpy.data.objects:
        if targetObject.animation_data != None:
            assignedAction = animation.assignedActions.add()
            assignedAction.targetName = targetObject.name
            if targetObject.animation_data.action != None:
                assignedAction.actionName = targetObject.animation_data.action.name
    if scene.animation_data != None and scene.animation_data.action != None:
        assignedAction = animation.assignedActions.add()
        assignedAction.targetName = scene.name
        assignedAction.actionName = scene.animation_data.action.name

def getMaterial(scene, materialTypeIndex, materialIndex):
    if materialTypeIndex == standardMaterialTypeIndex:
        return scene.m3_standard_materials[materialIndex]
    elif materialTypeIndex == displacementMaterialTypeIndex:
        return scene.m3_displacement_materials[materialIndex]
    elif materialTypeIndex == compositeMaterialTypeIndex:
        return scene.m3_composite_materials[materialIndex] 
    elif materialTypeIndex == terrainMaterialTypeIndex:
        return scene.m3_terrain_materials[materialIndex] 
    elif materialTypeIndex == volumeMaterialTypeIndex:
        return scene.m3_volume_materials[materialIndex] 
    return None

def sqr(x):
    return x*x

def smoothQuaternionTransition(previousQuaternion, quaternionToFix):
    sumOfSquares =  sqr(quaternionToFix.x - previousQuaternion.x) + sqr(quaternionToFix.y - previousQuaternion.y) + sqr(quaternionToFix.z - previousQuaternion.z) + sqr(quaternionToFix.w - previousQuaternion.w)
    sumOfSquaresMinus =  sqr(-quaternionToFix.x - previousQuaternion.x) + sqr(-quaternionToFix.y - previousQuaternion.y) + sqr(-quaternionToFix.z - previousQuaternion.z) + sqr(-quaternionToFix.w - previousQuaternion.w)
    if sumOfSquaresMinus < sumOfSquares:
        quaternionToFix.negate()

def vectorInterpolationFunction(leftInterpolationValue, rightInterpolationValue, rightFactor):
    return leftInterpolationValue.lerp(rightInterpolationValue, rightFactor)

def quaternionInterpolationFunction(leftInterpolationValue, rightInterpolationValue, rightFactor):
    return leftInterpolationValue.slerp(rightInterpolationValue, rightFactor)
    
def vectorsAlmostEqual(vectorExpected, vectorActual):
    diff = vectorExpected - vectorActual
    return diff.length < 0.00001
    
def quaternionsAlmostEqual(q0, q1):
    distanceSqr = sqr(q0.x-q1.x)+sqr(q0.y-q1.y)+sqr(q0.z-q1.z)+sqr(q0.w-q1.w)
    return distanceSqr < sqr(0.00001)

def simplifyVectorAnimationWithInterpolation(timeValuesInMS, vectors):
    return simplifyAnimationWithInterpolation(timeValuesInMS, vectors, vectorInterpolationFunction, vectorsAlmostEqual)

def simplifyQuaternionAnimationWithInterpolation(timeValuesInMS, vectors):
    return simplifyAnimationWithInterpolation(timeValuesInMS, vectors, quaternionInterpolationFunction, quaternionsAlmostEqual)

def simplifyAnimationWithInterpolation(timeValuesInMS, values, interpolationFunction, almostEqualFunction):
    if len(timeValuesInMS) < 2:
        return timeValuesInMS, values
    leftTimeInMS = timeValuesInMS[0]
    leftValue = values[0]
    currentTimeInMS = timeValuesInMS[1]
    currentValue = values[1]
    newTimeValuesInMS = [leftTimeInMS]
    newValues = [leftValue]
    for rightTimeInMS, rightValue in zip(timeValuesInMS[2:], values[2:]):
        timeSinceLeftTime =  currentTimeInMS - leftTimeInMS
        intervalLength = rightTimeInMS - leftTimeInMS
        rightFactor = timeSinceLeftTime / intervalLength
        expectedValue = interpolationFunction(leftValue, rightValue, rightFactor)
        if almostEqualFunction(expectedValue, currentValue):
            # ignore current value since it's interpolatable:
            pass
        else:
            newTimeValuesInMS.append(currentTimeInMS)
            newValues.append(currentValue)
            leftTimeInMS = currentTimeInMS
            leftValue = currentValue
        currentValue = rightValue
        currentTimeInMS = rightTimeInMS
    newTimeValuesInMS.append(timeValuesInMS[-1])
    newValues.append(values[-1])
    return newTimeValuesInMS, newValues

def findMeshObjects(scene):
    for currentObject in scene.objects:
        if currentObject.type == 'MESH':
            yield currentObject
            
def createDefaulValuesAction(scene, ownerName, actionIdRoot):
    action = bpy.data.actions.new("DEFAULTS_FOR_" + ownerName)
    action.id_root = actionIdRoot
    actionAssignment = scene.m3_default_value_action_assignments.add()
    actionAssignment.actionName = action.name
    actionAssignment.targetName = ownerName
    return action
    

def findActionOfAssignedAction(assignedAction, actionOwnerName, actionOwnerType):
    if actionOwnerName == assignedAction.targetName:
        actionName = assignedAction.actionName
        action = bpy.data.actions.get(actionName)
        if action == None:
            print("Warning: The action %s was referenced by name but does no longer exist" % assignedAction.actionName)
        else:
            if action.id_root == actionOwnerType:
                return action
    return None
    
def composeMatrix(location, rotation, scale):
    locMatrix= mathutils.Matrix.Translation(location)
    rotationMatrix = rotation.to_matrix().to_4x4()
    scaleMatrix = mathutils.Matrix()
    for i in range(3):
        scaleMatrix[i][i] = scale[i]
    return locMatrix * rotationMatrix * scaleMatrix

def determineDefaultActionFor(scene, actionOwnerName, actionOwnerType):
    for assignedAction in scene.m3_default_value_action_assignments:
        action = findActionOfAssignedAction(assignedAction, actionOwnerName, actionOwnerType)
        if action != None:
            return action
            
def getLongAnimIdOf(objectId, animPath):
    if objectId == animObjectIdScene and animPath.startswith("m3_boundings"):
        return objectId + "m3_boundings"
    return objectId + animPath;


def getRandomAnimIdNotIn(animIdSet):
    maxValue = 0x0fffffff
    unusedAnimId = random.randint(1, maxValue)
    while unusedAnimId in animIdSet:
        unusedAnimId = random.randint(1, maxValue)
    return unusedAnimId
    

def createMeshDataForSphere(radius, numberOfSideFaces = 10, numberOfCircles = 10):
    """returns vertices and faces"""
    vertices = []
    faces = []
    for circleIndex in range(numberOfCircles):
        circleAngle = math.pi * (circleIndex+1) / float(numberOfCircles+1)
        circleRadius = radius*math.sin(circleAngle)
        circleHeight = -radius*math.cos(circleAngle)
        nextCircleIndex = (circleIndex+1) % numberOfCircles
        for i in range(numberOfSideFaces):
            angle = 2*math.pi * i / float(numberOfSideFaces)
            nextI = ((i+1) % numberOfSideFaces)
            if nextCircleIndex != 0:
                i0 = circleIndex * numberOfSideFaces + i
                i1 = circleIndex * numberOfSideFaces + nextI
                i2 = nextCircleIndex * numberOfSideFaces + nextI
                i3 = nextCircleIndex * numberOfSideFaces + i
                faces.append((i0, i1 ,i2, i3))
            x = math.cos(angle)*circleRadius
            y = math.sin(angle)*circleRadius
            vertices.append((x, y, circleHeight))
    
    bottomVertexIndex = len(vertices)
    vertices.append((0, 0,-radius))
    for i in range(numberOfSideFaces):
        nextI = ((i+1) % numberOfSideFaces)
        i0 = i
        i1 = bottomVertexIndex
        i2 = nextI
        faces.append((i0, i1, i2))
    
    topVertexIndex = len(vertices)
    vertices.append((0, 0,radius))
    for i in range(numberOfSideFaces):
        nextI = ((i+1) % numberOfSideFaces)
        i0 = ((numberOfCircles-1)* numberOfSideFaces) + nextI
        i1 = topVertexIndex
        i2 = ((numberOfCircles-1)* numberOfSideFaces) + i
        faces.append((i0, i1, i2))
    return (vertices, faces)

def createMeshDataForCuboid(sizeX, sizeY, sizeZ):
    """returns vertices and faces"""
    s0 = sizeX / 2.0
    s1 = sizeY / 2.0
    s2 = sizeZ / 2.0
    faces = []
    faces.append((0, 1, 3, 2))
    faces.append((6,7,5,4))
    faces.append((4,5,1,0))
    faces.append((2, 3, 7, 6))
    faces.append((0, 2, 6, 4 ))
    faces.append((5, 7, 3, 1 ))
    vertices = [(-s0, -s1, -s2), (-s0, -s1, s2), (-s0, s1, -s2), (-s0, s1, s2), (s0, -s1, -s2), (s0, -s1, s2), (s0, s1, -s2), (s0, s1, s2)]
    return (vertices, faces)


def createMeshDataForCapsule(radius, height, numberOfSideFaces = 10, numberOfCircles = 10):
    """returns vertices and faces"""
    vertices = []
    faces = []
    halfHeight = height / 2.0
    for circleIndex in range(numberOfCircles):
        if circleIndex < numberOfCircles/2:
            circleAngle = math.pi * (circleIndex+1) / float(numberOfCircles+1-1)
            circleHeight = -halfHeight -radius*math.cos(circleAngle)
        else:
            circleAngle = math.pi * (circleIndex) / float(numberOfCircles+1-1)
            circleHeight =  halfHeight -radius*math.cos(circleAngle)
        circleRadius = radius*math.sin(circleAngle)
        nextCircleIndex = (circleIndex+1) % numberOfCircles
        for i in range(numberOfSideFaces):
            angle = 2*math.pi * i / float(numberOfSideFaces)
            nextI = ((i+1) % numberOfSideFaces)
            if nextCircleIndex != 0:
                i0 = circleIndex * numberOfSideFaces + i
                i1 = circleIndex * numberOfSideFaces + nextI
                i2 = nextCircleIndex * numberOfSideFaces + nextI
                i3 = nextCircleIndex * numberOfSideFaces + i
                faces.append((i0, i1 ,i2, i3))
            x = math.cos(angle)*circleRadius
            y = math.sin(angle)*circleRadius
            vertices.append((x, y, circleHeight))
    
    bottomVertexIndex = len(vertices)
    vertices.append((0, 0,-halfHeight -radius))
    for i in range(numberOfSideFaces):
        nextI = ((i+1) % numberOfSideFaces)
        i0 = i
        i1 = bottomVertexIndex
        i2 = nextI
        faces.append((i0, i1, i2))
    
    topVertexIndex = len(vertices)
    vertices.append((0, 0,halfHeight + radius))
    for i in range(numberOfSideFaces):
        nextI = ((i+1) % numberOfSideFaces)
        i0 = ((numberOfCircles-1)* numberOfSideFaces) + nextI
        i1 = topVertexIndex
        i2 = ((numberOfCircles-1)* numberOfSideFaces) + i
        faces.append((i0, i1, i2))
    return (vertices, faces)


def createMeshDataForCylinder(radius, height, numberOfSideFaces = 10):
    """returns the vertices and faces for a cylinder without head and bottom plane"""
    halfHeight = height / 2.0
    vertices = []
    faces = []
    for i in range(numberOfSideFaces):
        angle0 = 2*math.pi * i / float(numberOfSideFaces)
        angle1 = 2*math.pi * (i+1) / float(numberOfSideFaces)
        i0 = i*2+1
        i1 = i*2
        i2 = ((i+1)*2) % (numberOfSideFaces*2)
        i3 = ((i+1)*2 +1)% (numberOfSideFaces*2)
        faces.append((i0, i1 ,i2, i3))
        x = math.cos(angle0)*radius
        y = math.sin(angle0)*radius
        vertices.append((x,y,-halfHeight))
        vertices.append((x,y,+halfHeight))
    return (vertices, faces)

def transferParticleSystem(transferer):
    transferer.transferAnimatableFloat("emissionSpeed1")
    transferer.transferAnimatableFloat("emissionSpeed2")
    transferer.transferBoolean("randomizeWithEmissionSpeed2")
    transferer.transferAnimatableFloat("emissionAngleX")
    transferer.transferAnimatableFloat("emissionAngleY")
    transferer.transferAnimatableFloat("emissionSpreadX")
    transferer.transferAnimatableFloat("emissionSpreadY")
    transferer.transferAnimatableFloat("lifespan1")
    transferer.transferAnimatableFloat("lifespan2")
    transferer.transferBoolean("randomizeWithLifespan2")
    transferer.transferFloat("zAcceleration")
    transferer.transferFloat("unknownFloat1a")
    transferer.transferFloat("unknownFloat1b")
    transferer.transferFloat("unknownFloat1c")
    transferer.transferFloat("unknownFloat1d")
    transferer.transferAnimatableVector3("particleSizes1")
    transferer.transferAnimatableVector3("rotationValues1")
    transferer.transferAnimatableColor("initialColor1")
    transferer.transferAnimatableColor("finalColor1")
    transferer.transferAnimatableColor("unknownColor1")
    transferer.transferFloat("slowdown")
    transferer.transferFloat("unknownFloat2a")
    transferer.transferFloat("unknownFloat2b")
    transferer.transferFloat("unknownFloat2c")
    transferer.transferBoolean("trailingEnabled")
    transferer.transferInt("maxParticles")
    transferer.transferAnimatableFloat("emissionRate")
    transferer.transferEnum("emissionAreaType")
    transferer.transferAnimatableVector3("emissionAreaSize")
    transferer.transferAnimatableVector3("tailUnk1")
    transferer.transferAnimatableFloat("emissionAreaRadius")
    transferer.transferAnimatableFloat("spreadUnk")
    transferer.transferEnum("emissionType")
    transferer.transferBoolean("randomizeWithParticleSizes2")
    transferer.transferAnimatableVector3("particleSizes2")
    transferer.transferBoolean("randomizeWithRotationValues2")
    transferer.transferAnimatableVector3("rotationValues2")
    transferer.transferBoolean("randomizeWithColor2")
    transferer.transferAnimatableColor("initialColor2")
    transferer.transferAnimatableColor("finalColor2")
    transferer.transferAnimatableColor("unknownColor2")
    transferer.transferAnimatableInt16("partEmit")
    transferer.transferInt("phase1StartImageIndex")
    transferer.transferInt("phase1EndImageIndex")
    transferer.transferInt("phase2StartImageIndex")
    transferer.transferInt("phase2EndImageIndex")
    transferer.transferFloat("relativePhase1Length")
    transferer.transferInt("numberOfColumns")
    transferer.transferInt("numberOfRows")
    transferer.transferFloat("columnWidth")
    transferer.transferFloat("rowHeight")
    transferer.transferEnum("particleType")
    transferer.transferFloat("lengthWidthRatio")
    transferer.transfer32Bits("forceChannels")
    transferer.transferBit("flags", "sort")
    transferer.transferBit("flags", "collideTerrain")
    transferer.transferBit("flags", "collideObjects")
    transferer.transferBit("flags", "spawnOnBounce")
    transferer.transferBit("flags", "useInnerShape")
    transferer.transferBit("flags", "inheritEmissionParams")
    transferer.transferBit("flags", "inheritParentVel")
    transferer.transferBit("flags", "sortByZHeight")
    transferer.transferBit("flags", "reverseIteration")
    transferer.transferBit("flags", "smoothRotation")
    transferer.transferBit("flags", "bezSmoothRotation")
    transferer.transferBit("flags", "smoothSize")
    transferer.transferBit("flags", "bezSmoothSize")
    transferer.transferBit("flags", "smoothColor")
    transferer.transferBit("flags", "bezSmoothColor")
    transferer.transferBit("flags", "litParts")
    transferer.transferBit("flags", "randFlipBookStart")
    transferer.transferBit("flags", "multiplyByGravity")
    transferer.transferBit("flags", "clampTailParts")
    transferer.transferBit("flags", "spawnTrailingParts")
    transferer.transferBit("flags", "useVertexAlpha")
    transferer.transferBit("flags", "modelParts")
    transferer.transferBit("flags", "swapYZonModelParts")
    transferer.transferBit("flags", "scaleTimeByParent")
    transferer.transferBit("flags", "useLocalTime")
    transferer.transferBit("flags", "simulateOnInit")
    transferer.transferBit("flags", "copy")

def transferParticleSystemCopy(transferer):
    transferer.transferAnimatableFloat("emissionRate")
    transferer.transferAnimatableInt16("partEmit")
    
def transferForce(transferer):
    transferer.transferEnum("forceType")
    transferer.transfer32Bits("forceChannels")
    transferer.transferAnimatableFloat("forceStrength")
    transferer.transferAnimatableFloat("forceRange")
    transferer.transferAnimatableFloat("unknownAt64")
    transferer.transferAnimatableFloat("unknownAt84")

def transferStandardMaterial(transferer):
    transferer.transferString("name")
    transferer.transferBit("flags", "unfogged")
    transferer.transferBit("flags", "twoSided")
    transferer.transferBit("flags", "unshaded")
    transferer.transferBit("flags", "noShadowsCast")
    transferer.transferBit("flags", "noHitTest")
    transferer.transferBit("flags", "noShadowsReceived")
    transferer.transferBit("flags", "depthPrepass")
    transferer.transferBit("flags", "useTerrainHDR")
    transferer.transferBit("flags", "splatUVfix")
    transferer.transferBit("flags", "softBlending")
    transferer.transferBit("flags", "forParticles")
    transferer.transferBit("flags", "darkNormalMapping")
    transferer.transferBit("unknownFlags", "unknownFlag0x1")
    transferer.transferBit("unknownFlags", "unknownFlag0x4")
    transferer.transferBit("unknownFlags", "unknownFlag0x8")
    transferer.transferBit("unknownFlags", "unknownFlag0x200")
    transferer.transferEnum("blendMode")
    transferer.transferInt("priority")
    transferer.transferFloat("specularity")
    transferer.transferFloat("specMult")
    transferer.transferFloat("emisMult")
    transferer.transferEnum("layerBlendType")
    transferer.transferEnum("emisBlendType")
    transferer.transferEnum("specType")
    
def transferDisplacementMaterial(transferer):
    transferer.transferString("name")
    transferer.transferAnimatableFloat("strengthFactor")
    transferer.transferInt("priority")

def transferCompositeMaterial(transferer):
    transferer.transferString("name")

def transferCompositeMaterialSection(transferer):
    transferer.transferAnimatableFloat("alphaFactor")

def transferTerrainMaterial(transferer):
    transferer.transferString("name")

def transferVolumeMaterial(transferer):
    transferer.transferString("name")
    transferer.transferAnimatableFloat("volumeDensity")

def transferMaterialLayer(transferer):
    transferer.transferString("imagePath")
    transferer.transferInt("unknown11")
    transferer.transferAnimatableColor("color")
    transferer.transferBit("flags", "textureWrapX")
    transferer.transferBit("flags", "textureWrapY")
    transferer.transferBit("flags", "colorEnabled")
    transferer.transferEnum("uvSource")
    transferer.transferBit("alphaFlags", "alphaAsTeamColor")
    transferer.transferBit("alphaFlags", "alphaOnly")
    transferer.transferBit("alphaFlags", "alphaBasedShading")
    transferer.transferAnimatableFloat("brightMult")
    transferer.transferAnimatableFloat("midtoneOffset")
    transferer.transferAnimatableVector2("uvOffset")
    transferer.transferAnimatableVector3("uvAngle")
    transferer.transferAnimatableVector2("uvTiling")
    transferer.transferAnimatableFloat("brightness")
    transferer.transferBit("tintFlags", "useTint")
    transferer.transferBit("tintFlags", "tintAlpha")
    transferer.transferFloat("tintStrength")
    transferer.transferFloat("tintStart")
    transferer.transferFloat("tintCutout")

def transferAnimation(transferer):
    transferer.transferString("name")
    transferer.transferFloat("movementSpeed")
    transferer.transferInt("frequency")
    transferer.transferBit("flags", "notLooping")
    transferer.transferBit("flags", "alwaysGlobal")
    transferer.transferBit("flags", "globalInPreviewer")
    
def transferSTC(transferer):
    transferer.transferBoolean("runsConcurrent")

def transferCamera(transferer):
    transferer.transferString("name")
    transferer.transferAnimatableFloat("fieldOfView")
    transferer.transferAnimatableFloat("farClip")
    transferer.transferAnimatableFloat("nearClip")
    transferer.transferAnimatableFloat("clip2")
    transferer.transferAnimatableFloat("focalDepth")
    transferer.transferAnimatableFloat("falloffStart")
    transferer.transferAnimatableFloat("falloffEnd")
    transferer.transferAnimatableFloat("depthOfField")

def transferFuzzyHitTest(transferer):
    transferer.transferEnum("shape")
    transferer.transferFloat("size0")
    transferer.transferFloat("size1") 
    transferer.transferFloat("size2")

def transferLight(transferer):
    transferer.transferEnum("lightType")
    transferer.transferAnimatableVector3("lightColor")
    transferer.transferBit("flags", "shadowCast")
    transferer.transferBit("flags", "specular")
    transferer.transferBit("flags", "unknownFlag0x04")
    transferer.transferBit("flags", "turnOn")
    transferer.transferBoolean("unknownAt8")
    transferer.transferAnimatableFloat("lightIntensity")
    transferer.transferAnimatableVector3("specColor")
    transferer.transferAnimatableFloat("specIntensity")
    transferer.transferAnimatableFloat("attenuationFar")
    transferer.transferFloat("unknownAt148")
    transferer.transferAnimatableFloat("attenuationNear")
    transferer.transferAnimatableFloat("hotSpot")
    transferer.transferAnimatableFloat("falloff")

def transferBoundings(transferer):
    transferer.transferAnimatableBoundings()

