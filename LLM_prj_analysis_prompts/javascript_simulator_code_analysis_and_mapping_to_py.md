### Analysis of the structure of the code of the javascript simulator and mapping to python implementation

#### JavaScript Simulator Architecture - Detailed Pseudo-Code
##### File Structure

src/core/
- Simulator.js          [Main simulation engine - ~1500 lines]
- Scene.js              [Scene data structure and settings]
- CanvasRenderer.js     [2D Canvas drawing backend]
- FloatColorRenderer.js [WebGL drawing for color modes]
- geometry.js           [Geometric utilities]
- sceneObjs/            [Optical element classes]
    * BaseSceneObj.js
    * PointSource.js
    * IdealLens.js
    * Blocker.js
    * ...
##### SIMULATOR.JS - Main Ray Tracing Engine
```
Constructor

class Simulator {
  constructor(scene, contexts...) {
    this.scene = scene
    this.ctxMain = mainCanvas           // Light layer (rays)
    this.ctxBelowLight = belowCanvas    // Objects (glass, mirrors)
    this.ctxAboveLight = aboveCanvas    // UI (detectors, text)
    this.ctxGrid = gridCanvas           // Grid overlay
    
    // Simulation state
    this.pendingRays = []               // Queue of rays to process
    this.processedRayCount = 0          // Total rays traced
    this.totalTruncation = 0            // Lost brightness from limits
    this.totalUndefinedBehavior = 0     // Rays with undefined behavior
    this.brightnessScale = 0            // Normalization factor
    
    // Limits
    this.rayCountLimit = Infinity       // Max rays to trace
    this.enableTimer = false            // Pause every 50ms?
    
    // Constants
    MIN_RAY_SEGMENT_LENGTH = 1e-6      // Ignore interactions below this
  }
}
```
###### MAIN METHOD: updateSimulation()
File: Simulator.js lines 303-510
```
def update_simulation(skip_light=False, skip_grid=False, force_redraw=False):
    """
    Main entry point - runs simulation and renders scene.
    
    Args:
        skip_light: Don't redraw rays (only update objects)
        skip_grid: Don't redraw grid
        force_redraw: Force redraw even if manual mode
    """
    
    # ====== INITIALIZATION ======
    emit_event('update')
    
    if not skip_light:
        total_truncation = 0
        total_undefined_behavior = 0
        brightness_scale = 0
        pending_rays = []
        processed_ray_count = 0
        emit_event('simulationStart')
    
    # ====== SETUP RENDERERS ======
    # Create renderer objects for each canvas layer
    canvas_renderer_below_light = CanvasRenderer(ctx_below_light, origin, scale)
    canvas_renderer_above_light = CanvasRenderer(ctx_above_light, origin, scale)
    
    if scene.color_mode != 'default':
        # Use WebGL for advanced color rendering
        canvas_renderer_main = FloatColorRenderer(gl_main, origin, scale, color_mode)
    else:
        # Use 2D canvas for simple rendering
        canvas_renderer_main = CanvasRenderer(ctx_main, origin, scale)
    
    # ====== DRAW GRID ======
    if not skip_grid and show_grid:
        for x in range(0, canvas_width, grid_size):
            draw_vertical_line(x)
        for y in range(0, canvas_height, grid_size):
            draw_horizontal_line(y)
    
    # ====== DRAW OBJECTS (BELOW LIGHT LAYER) ======
    # Sort objects by z-index
    sorted_objects = sort_by_z_index(scene.objects)
    
    for obj in sorted_objects:
        is_highlighted = editor.is_obj_highlighted(obj)
        obj.draw(canvas_renderer_below_light, is_above_light=False, is_highlighted)
    
    # ====== INITIALIZE RAY SOURCES ======
    if not skip_light:
        for obj in scene.optical_objects:
            result = obj.on_simulation_start()
            
            if result:
                if result.new_rays:
                    pending_rays.extend(result.new_rays)
                
                if result.truncation:
                    total_truncation += result.truncation
                
                if result.brightness_scale:
                    brightness_scale = result.brightness_scale
    
    # ====== MAIN RAY TRACING LOOP ======
    if not skip_light:
        process_rays()  # This is where the magic happens!
    
    # ====== DRAW OBJECTS (ABOVE LIGHT LAYER) ======
    for obj in scene.objects:
        is_highlighted = editor.is_obj_highlighted(obj)
        obj.draw(canvas_renderer_above_light, is_above_light=True, is_highlighted)
    
    # Draw observer (if in observer mode)
    if scene.mode == 'observer':
        draw_circle(scene.observer.position, scene.observer.radius)
    
    emit_event('requestUpdateErrorAndWarning')
```
###### CORE METHOD: processRays()
File: Simulator.js lines 517-882 This is the heart of the simulation - the ray tracing loop.
```
def process_rays():
    """
    Process all pending rays until queue is empty.
    
    This implements the main ray tracing algorithm:
    1. Pop ray from pending queue
    2. Find nearest optical object intersection
    3. Draw ray segment
    4. Call object's on_ray_incident() method
    5. Add new rays to queue
    6. Repeat until queue empty
    """
    
    start_time = current_time()
    pending_rays_index = -1
    
    # ====== MAIN LOOP ======
    while True:
        
        # ==== PAUSE MECHANISM (prevent UI freeze) ====
        if (current_time() - start_time) > 50ms and enable_timer:
            # Pause for 10ms to let UI update
            schedule_continuation(delay=10ms, callback=process_rays)
            flush_renderer()  # Push drawn rays to screen
            emit_event('simulationPause')
            return  # Exit and resume later
        
        # ==== TERMINATION CONDITIONS ====
        if processed_ray_count > ray_count_limit:
            should_simulator_stop = True
            break
        
        if should_simulator_stop:
            break
        
        if pending_rays_index >= len(pending_rays):
            # Processed all rays in queue
            if left_ray_count == 0:
                break  # Done!
            else:
                # Some rays were deferred, restart from beginning
                left_ray_count = 0
                pending_rays_index = -1
                continue
        
        # ==== POP NEXT RAY ====
        pending_rays_index += 1
        ray = pending_rays[pending_rays_index]
        
        if not ray:
            continue
        
        # ====== FIND NEAREST INTERSECTION ======
        nearest_obj = None
        nearest_obj_index = -1
        nearest_point = None
        nearest_distance_sq = Infinity
        surface_merging_objs = []  # Glasses to merge at surface
        undefined_behavior = False
        undefined_behavior_objs = []
        
        for i, obj in enumerate(optical_objects):
            # Check if ray intersects this object
            intersection_point = obj.check_ray_intersects(ray)
            
            if intersection_point:
                distance_sq = distance_squared(ray.p1, intersection_point)
                
                # ==== HANDLE SURFACE MERGING ====
                # When ray hits two objects at same point (within MIN_RAY_SEGMENT_LENGTH)
                if (nearest_point and 
                    distance_squared(intersection_point, nearest_point) < MIN_RAY_SEGMENT_LENGTH_SQ and
                    (obj is BaseGlass or nearest_obj is BaseGlass)):
                    
                    if nearest_obj is BaseGlass:
                        if obj is BaseGlass:
                            # Both are glass - merge them
                            surface_merging_objs.append(obj)
                        else:
                            # Only first is glass
                            if not obj.merges_with_glass:
                                undefined_behavior = True
                                undefined_behavior_objs = [nearest_obj, obj]
                            
                            # Let non-glass handle, pass glass as merged surface
                            surface_merging_objs.append(nearest_obj)
                            nearest_obj = obj
                            nearest_obj_index = i
                            nearest_point = intersection_point
                            nearest_distance_sq = distance_sq
                    else:
                        # Only second is glass
                        if not nearest_obj.merges_with_glass:
                            undefined_behavior = True
                            undefined_behavior_objs = [nearest_obj, obj]
                        
                        surface_merging_objs.append(obj)
                
                # ==== HANDLE SIMULTANEOUS HIT (NON-GLASS) ====
                elif (nearest_point and 
                      distance_squared(intersection_point, nearest_point) < MIN_RAY_SEGMENT_LENGTH_SQ):
                    # Two non-glass objects at same point = undefined
                    undefined_behavior = True
                    undefined_behavior_objs = [nearest_obj, obj]
                
                # ==== UPDATE NEAREST ====
                elif (distance_sq < nearest_distance_sq and 
                      distance_sq > MIN_RAY_SEGMENT_LENGTH_SQ):
                    nearest_obj = obj
                    nearest_obj_index = i
                    nearest_point = intersection_point
                    nearest_distance_sq = distance_sq
                    undefined_behavior = False
                    undefined_behavior_objs = []
                    surface_merging_objs = []
        
        # ==== HANDLE UNDEFINED BEHAVIOR ====
        if undefined_behavior:
            declare_undefined_behavior(ray, undefined_behavior_objs)
        
        # ==== CALCULATE RAY COLOR/ALPHA ====
        if scene.simulate_colors:
            color = wavelength_to_rgb(ray.wavelength, ray.brightness_s + ray.brightness_p)
        else:
            alpha = ray.brightness_s + ray.brightness_p
        
        # ====== CASE 1: RAY HITS NOTHING ======
        if nearest_distance_sq == Infinity:
            # Draw infinite ray
            if scene.mode == 'rays' or scene.mode == 'extended':
                if scene.simulate_colors:
                    canvas_renderer.draw_ray(ray, color, show_arrows=scene.show_ray_arrows)
                else:
                    canvas_renderer.draw_ray(ray, get_theme_ray_color('ray', alpha))
            
            # Draw extension (for extended ray mode)
            if scene.mode == 'extended' and not ray.is_new:
                extension_ray = line(ray.p1, point(2*ray.p1.x - ray.p2.x, 2*ray.p1.y - ray.p2.y))
                canvas_renderer.draw_ray(extension_ray, get_theme_ray_color('extendedRay', alpha))
            
            # Check if observer sees this ray
            if scene.mode == 'observer':
                observer_intersection = line_circle_intersection(ray, scene.observer)
                if observer_intersection and intersection_is_on_ray(observer_intersection, ray):
                    observed = True
        
        # ====== CASE 2: RAY HITS OBJECT ======
        else:
            # Draw ray segment from ray.p1 to intersection point
            if scene.mode == 'rays' or scene.mode == 'extended':
                ray_segment = line(ray.p1, nearest_point)
                
                if scene.simulate_colors:
                    canvas_renderer.draw_segment(ray_segment, color, show_arrows=scene.show_ray_arrows)
                else:
                    canvas_renderer.draw_segment(ray_segment, get_theme_ray_color('ray', alpha))
            
            # ==== CALL OBJECT'S RAY HANDLER ====
            incident_result = nearest_obj.on_ray_incident(
                ray=ray,
                ray_index=pending_rays_index,
                incident_point=nearest_point,
                surface_merging_objs=surface_merging_objs
            )
            
            # ==== HANDLE RESULT ====
            if incident_result:
                # Object may return new rays (refracted, reflected, etc.)
                if incident_result.new_rays:
                    for new_ray in incident_result.new_rays:
                        pending_rays.append(new_ray)
                
                # Check if ray was absorbed
                if incident_result.is_absorbed:
                    # Ray stops here
                    pass
                
                # Handle other return values...
                if incident_result.truncation:
                    total_truncation += incident_result.truncation
        
        # ==== UPDATE COUNTERS ====
        processed_ray_count += 1
        
        # ==== HANDLE IMAGE DETECTION ====
        # (Check if two rays intersect to form image - not shown here for brevity)
    
    # ====== SIMULATION COMPLETE ======
    flush_renderer()  # Push remaining rays to screen
    
    # Redraw "above light" layer with updated detector readings
    update_simulation(skip_light=True, skip_grid=True)
    
    emit_event('simulationComplete')
    validate()  # Check for errors/warnings
```
###### KEY ALGORITHMS
1. Intersection Detection
```
def check_ray_intersects(ray):
    """
    Each object implements this method.
    
    Returns:
        Point: Intersection point, or None if no intersection
    """
    # For LineObjMixin (lens, blocker, mirror):
    intersection = line_line_intersection(ray, self.line)
    if intersection and point_is_on_segment(intersection, self.line):
        if point_is_on_ray(intersection, ray):
            return intersection
    return None
    
    # For CircleObjMixin (circular lens, glass):
    intersections = line_circle_intersections(ray, self.circle)
    # Return nearest intersection that's on the ray
    return min(valid_intersections, key=lambda p: distance(ray.p1, p))
```
2. Surface Merging
```
def handle_surface_merging(obj, ray, surface_merging_objs):
    """
    When a ray hits multiple glass surfaces at once.
    
    Example: Ray exits glass A and enters glass B at same point
    
    The refractive indices are combined:
        n_combined = n_outside * (n_B / n_A)
    """
    if len(surface_merging_objs) > 0:
        # Combine refractive indices from all merged surfaces
        body_merging_obj = None
        for glass_obj in surface_merging_objs:
            if body_merging_obj is None:
                body_merging_obj = glass_obj.init_ref_index(ray)
            else:
                body_merging_obj = glass_obj.mult_ref_index(body_merging_obj)
        
        # Pass combined index to object handling the ray
        return obj.on_ray_incident(ray, ray_index, incident_point, body_merging_obj)
    else:
        return obj.on_ray_incident(ray, ray_index, incident_point, None)
```
3. Ray Data Structure
```
class Ray:
    """
    Ray representation used throughout simulation.
    """
    p1: Point              # Starting point
    p2: Point              # Direction point (p2-p1 = direction vector)
    brightness_s: float    # S-polarization intensity (0-1)
    brightness_p: float    # P-polarization intensity (0-1)
    wavelength: float      # Wavelength in nm (optional)
    gap: bool              # True if discontinuous from previous ray
    is_new: bool           # True if just emitted from source
    body_merging_obj: dict # For GRIN glass (gradient index)
```
###### OBJECT LIFECYCLE METHODS

1. on_simulation_start()
    Called on ALL optical objects before ray tracing begins

   - Example: PointSource
    ```
    def on_simulation_start():
        rays = generate_360_degree_rays()
        return {
            'newRays': rays,
            'brightnessScale': 0.5,
            'truncation': 0.01
        }
    ```
   - Example: Detector
    ```
    def on_simulation_start():
        # Reset readings
        self.power = 0
        self.normal = 0
        self.shear = 0
        self.bin_data = [0] * bin_count
        return None
    ```    
2. check_ray_intersects(ray)

    Called for EACH ray on EACH optical object

    -
    ``` 
    def check_ray_intersects(ray):
        """
        Returns:
            Point if ray intersects this object
            None if no intersection
        """
    ```
    - Implemented per object type
        pass

3. on_ray_incident(ray, ray_index, incident_point, surface_merging_objs=None)

    Called when a ray hits this object

   - IdealLens
   ```
        def on_ray_incident(ray, ray_index, incident_point):
            # Refract ray using thin lens formula
            ray.p1 = incident_point
            ray.p2 = calculate_refracted_direction()
            return None  # Ray continues (not absorbed)
    ```
    - Blocker
    ```
        def on_ray_incident(ray, ray_index, incident_point):
            return {'isAbsorbed': True}  # Ray stops
    ```
    - Mirror
    ```
        def on_ray_incident(ray, ray_index, incident_point):
            # Reflect ray
            ray.p1 = incident_point
            ray.p2 = calculate_reflected_direction()
            return None  # Ray continues
    ```
    - Example: Glass (with refraction)
    ```
        def on_ray_incident(ray, ray_index, incident_point, surface_merging_objs):
            # Apply Snell's law
            # Check for total internal reflection
            # Split into transmitted and reflected rays
            return {
                'newRays': [transmitted_ray, reflected_ray],
                'truncation': 0.001
            }
    ```
    - Example: Detector
    ```
        def on_ray_incident(ray, ray_index, incident_point):
            # Accumulate power
            self.power += ray.brightness_s + ray.brightness_p
            # Calculate force
            self.normal += calculate_normal_force(ray)
            self.shear += calculate_shear_force(ray)
            # Update irradiance map
            bin_index = calculate_bin_index(incident_point)
            self.bin_data[bin_index] += ray.brightness_s + ray.brightness_p
            return None  # Ray passes through
    ```        
##### RENDERING SYSTEM
Three-Layer Canvas System

###### Layer 1: BELOW LIGHT (drawn first)
- Optical elements (glass, mirrors, lenses)
- Uses color subtraction for depth effect
- Drawn with obj.draw(renderer, is_above_light=False)

###### Layer 2: LIGHT (rays - drawn second)
- Ray segments
- Uses additive blending ('screen' composite mode)
- Drawn during ray tracing loop

###### Layer 3: ABOVE LIGHT (drawn last)
- UI elements (detector readings, labels)
- Grid overlay
- Observer indicator
- Drawn with obj.draw(renderer, is_above_light=True)

##### PYTHON IMPLEMENTATION MAPPING
Based on this analysis, here's how we'll structure the Python version:

src_python/core/
1. simulator.py          [Main ray tracing engine]
    - class Simulator
        * __init__(scene, settings)
        * update_simulation()
        * process_rays()

2. scene.py              [Scene data structure]
    - class Scene
        * objects: List[BaseSceneObj]
        * optical_objects: List[BaseSceneObj]
        * ray_density: float
        * color_mode: str
        * settings...

3. renderer.py           [SVG/matplotlib backend]
    - class SVGRenderer
        * draw_ray(ray, color)
        * draw_segment(p1, p2, color)
        * draw_object(obj)
        * save(filename)

4. scene_objs/           [Already implemented!]
    - PointSource       
    - IdealLens         
    - Blocker

This is the complete architecture! The JavaScript implementation is very well-structured and we can closely follow it for the Python version. The key insight is that the simulator is just a ray queue processor - objects handle their own physics through the three lifecycle methods.