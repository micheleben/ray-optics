# History of promps passed to LLM for re-implementing a JS optical simulator in Python

This file contains a history of prompts passed to the LLM to re-implement the javascript optical simulator in python.

## Making a plan for re-implementation:

### bottom-up re-implementation plan
looking to the javascript template so far we have done the Layer 0: pure Utilities. 
Let's examin the javascript project structure (dependency table) to find a template to follow in our re-implementation
It is as the following:

1. Layer 0: PURE UTILITIES (No dependencies)
    *geometry.js*   ← THIS IS THE NAME OF THE FILE WE JUST TRANSLATED, WE STARTED HERE                           
    * Points, Lines, Circles
    * Intersections (line-line, line-circle)
    * Vector operations (dot, cross)
    * Distance calculations

↓ (imported by)

2. Layer 1: BASE CLASSES (This file is into SceneObjs subdir structure)
    *BaseSceneObj.js*
    * Base class for all optical objects 
    * Defines interface: checkRayIntersects(), onRayIncident()
    * Serialization, drawing interface 
    - NO dependencies on other simulator modules

↓ (imported by)

3. Layer 2: MIXINS & SPECIALIZED BASES (These files are into SceneObjs subdir structure)
    *LineObjMixin.js*
    - imports: geometry,BaseSceneObj

    *CircleObjMixin.js*
    - imports: geometry,BaseSceneObj

    *BaseGlass.js*
    - imports geometry, BaseSceneObj

    *BaseFilter.js* 
    - imports: BaseSceneObj

↓ (imported by)

4. Layer 3: CONCRETE OPTICAL OBJECTS (these files are into subfolders in SceneObjs subdir,e.g. all the mirrors are in same .) 
    * mirrors:
        *Mirror.js*, 
        *ArcMirror.js*, 
        *ParabolicMirror.js*
        - extends: BaseFilter + LineObjMixin

    * glasses:
        *Glass.js*, 
        *CircleGlass.js*,  
        *PolygonGlass*, 
        - extends: BaseGlass + various mixins

    * light sources
        *SingleRay.js*
        *Beam.js* 

    Note: These Objects only import Simulator for constants like
    Simulator.MIN_RAY_SEGMENT_LENGTH

↓ (used by)

5. Layer 4: SIMULATION ENGINE
    *Simulator.js* <- this will be the last we reimplement
    - imports: ALL object classes geometry
    * Ray tracing loop
    * Intersection search
    * Ray propagation
    * Drawing/rendering coordination

I would like now to translate the code in BaseSceneObj.js. Could you please write a python equivalent and place it in the subfolder src_python/core/scene_obj ?

