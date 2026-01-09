# Surface Merging Implementation Plan

## Overview

Surface merging is a critical feature for handling cases where a ray intersects multiple objects at nearly the same point. This commonly occurs when:
- Two glass objects share a common edge
- A ray hits the boundary between a glass object and another optical element
- Multiple surfaces are positioned very close together (within MIN_RAY_SEGMENT_LENGTH)

Without surface merging, these situations would cause undefined behavior warnings or incorrect ray propagation.

## Current State Analysis

### JavaScript Implementation (Simulator.js)

**Location**: Lines 596-655 in `processRays()` method

**Key Logic**:
```javascript
surfaceMergingObjs = []; // The glasses whose surface is to be merged with s_obj

for (var i = 0; i < opticalObjs.length; i++) {
    s_point_temp = opticalObjs[i].checkRayIntersects(this.pendingRays[j]);
    if (s_point_temp) {
        s_lensq_temp = geometry.distanceSquared(this.pendingRays[j].p1, s_point_temp);

        // Check if intersection is at nearly the same point as current nearest
        if (s_point &&
            geometry.distanceSquared(s_point_temp, s_point) < MIN_RAY_SEGMENT_LENGTH_SQUARED * lengthScale^2 &&
            (opticalObjs[i] instanceof BaseGlass || s_obj instanceof BaseGlass)) {

            // Handle surface merging based on object types:

            if (s_obj instanceof BaseGlass) {
                if (opticalObjs[i] instanceof BaseGlass) {
                    // Both are glasses - add to surface merging list
                    surfaceMergingObjs.push(opticalObjs[i]);
                }
                else {
                    // First is glass, second is not
                    if (!opticalObjs[i].constructor.mergesWithGlass) {
                        s_undefinedBehavior = true;
                        s_undefinedBehaviorObjs = [s_obj, opticalObjs[i]];
                    }
                    // Move glass to merging list, let non-glass handle ray
                    surfaceMergingObjs.push(s_obj);
                    s_obj = opticalObjs[i];
                    s_obj_index = i;
                    s_point = s_point_temp;
                    s_lensq = s_lensq_temp;
                }
            } else {
                // First is not glass, second is glass
                if (!s_obj.constructor.mergesWithGlass) {
                    s_undefinedBehavior = true;
                    s_undefinedBehaviorObjs = [s_obj, opticalObjs[i]];
                }
                // Add glass to merging list
                surfaceMergingObjs.push(opticalObjs[i]);
            }
        }
    }
}

// Later, pass surfaceMergingObjs to the object's onRayIncident method
const ret = s_obj.onRayIncident(this.pendingRays[j], j, s_point, surfaceMergingObjs);
```

**Merging Rules**:
1. **Glass + Glass**: Both added to `surfaceMergingObjs`, first one handles ray
2. **Glass + Non-Glass with `mergesWithGlass=true`**: Glass added to `surfaceMergingObjs`, non-glass handles ray
3. **Glass + Non-Glass with `mergesWithGlass=false`**: Undefined behavior declared, glass added to `surfaceMergingObjs`, non-glass handles ray
4. **Non-Glass + Non-Glass**: Undefined behavior (not mergeable)

### Python Implementation (simulator.py)

**Location**: Lines 117-205 in `_process_rays()` method and Lines 207-239 in `_find_nearest_intersection()` method

**Current Behavior**:
- Finds nearest intersection using simple distance comparison
- NO surface merging logic implemented
- Comment on line 128: "Note: Surface merging is NOT implemented in this phase (deferred to Phase 2.5)."
- Simply calls `on_ray_incident()` without any `surfaceMergingObjs` parameter

**Missing Features**:
1. Detection of multiple near-simultaneous intersections
2. Classification of objects as glass vs non-glass
3. Building `surfaceMergingObjs` list
4. Passing merged surfaces to `on_ray_incident()`
5. Undefined behavior tracking for incompatible merges

## Implementation Plan

### Phase 1: Add Glass Detection Infrastructure

**1.1 Verify/Add BaseGlass Class Attribute**
- Check `base_glass.py` for `merges_with_glass` class attribute
- If missing, add it to `BaseGlass` and any other optical elements that can merge

**1.2 Add Class-Level Attribute to Other Objects**
- Add `merges_with_glass = False` to objects like mirrors, blockers, etc.
- Add `merges_with_glass = True` to objects that are designed to work with glass boundaries

### Phase 2: Modify `_find_nearest_intersection()` Method

**Current signature**:
```python
def _find_nearest_intersection(self, ray):
    """Returns: tuple or None: (object, intersection_point)"""
```

**New signature**:
```python
def _find_nearest_intersection(self, ray):
    """
    Returns: tuple or None:
        (nearest_obj, nearest_point, surface_merging_objs, undefined_behavior, undefined_behavior_objs)
    """
```

**Implementation**:
```python
def _find_nearest_intersection(self, ray):
    nearest_obj = None
    nearest_point = None
    nearest_distance_squared = float('inf')
    surface_merging_objs = []
    undefined_behavior = False
    undefined_behavior_objs = []

    for obj in self.scene.optical_objs:
        if not hasattr(obj, 'check_ray_intersects'):
            continue

        intersection_point = obj.check_ray_intersects(ray_geom)

        if intersection_point is not None:
            intersection_dict = self._normalize_intersection_point(intersection_point)

            dx = intersection_dict['x'] - ray.p1['x']
            dy = intersection_dict['y'] - ray.p1['y']
            distance_squared = dx * dx + dy * dy

            # Check if this is a valid intersection (not too close to start)
            if distance_squared < self.MIN_RAY_SEGMENT_LENGTH ** 2:
                continue

            # Check if this intersection is at nearly the same point as the current nearest
            if nearest_point is not None:
                dx_near = intersection_dict['x'] - nearest_point['x']
                dy_near = intersection_dict['y'] - nearest_point['y']
                dist_to_nearest = dx_near * dx_near + dy_near * dy_near

                threshold = (self.MIN_RAY_SEGMENT_LENGTH ** 2) * (self.scene.length_scale ** 2)

                if dist_to_nearest < threshold:
                    # Near-simultaneous intersection - handle surface merging
                    is_obj_glass = self._is_glass(obj)
                    is_nearest_glass = self._is_glass(nearest_obj)

                    if is_nearest_glass or is_obj_glass:
                        # At least one is glass - can merge

                        if is_nearest_glass:
                            if is_obj_glass:
                                # Both are glasses
                                surface_merging_objs.append(obj)
                            else:
                                # Nearest is glass, obj is not
                                if not self._can_merge_with_glass(obj):
                                    undefined_behavior = True
                                    undefined_behavior_objs = [nearest_obj, obj]

                                # Move glass to merging list
                                surface_merging_objs.append(nearest_obj)

                                # Let non-glass handle ray
                                nearest_obj = obj
                                nearest_point = intersection_dict
                                nearest_distance_squared = distance_squared
                        else:
                            # Nearest is not glass, obj is glass
                            if not self._can_merge_with_glass(nearest_obj):
                                undefined_behavior = True
                                undefined_behavior_objs = [nearest_obj, obj]

                            # Add glass to merging list
                            surface_merging_objs.append(obj)
                    else:
                        # Neither is glass - undefined behavior
                        undefined_behavior = True
                        undefined_behavior_objs = [nearest_obj, obj]

                    continue

            # This is a new nearest intersection
            if distance_squared < nearest_distance_squared:
                nearest_distance_squared = distance_squared
                nearest_point = intersection_dict
                nearest_obj = obj
                undefined_behavior = False
                undefined_behavior_objs = []
                surface_merging_objs = []

    if nearest_obj is None:
        return None

    return (nearest_obj, nearest_point, surface_merging_objs, undefined_behavior, undefined_behavior_objs)
```

### Phase 3: Add Helper Methods

```python
def _is_glass(self, obj):
    """Check if an object is a glass object."""
    from .scene_objs.base_glass import BaseGlass
    return isinstance(obj, BaseGlass)

def _can_merge_with_glass(self, obj):
    """Check if an object can merge with glass surfaces."""
    return getattr(obj.__class__, 'merges_with_glass', False)

def _normalize_intersection_point(self, point):
    """Convert Point objects to dict format."""
    if hasattr(point, 'x') and hasattr(point, 'y'):
        return {'x': point.x, 'y': point.y}
    return point
```

### Phase 4: Add Undefined Behavior Tracking

```python
class Simulator:
    def __init__(self, scene, max_rays=10000):
        # ... existing code ...
        self.total_undefined_behavior = 0
        self.undefined_behavior_objs = []
        self.UNDEFINED_BEHAVIOR_THRESHOLD = 0.001

    def declare_undefined_behavior(self, ray, objs):
        """Declare that the ray encounters an undefined behavior."""
        self.total_undefined_behavior += ray.total_brightness
        if not self.undefined_behavior_objs:
            self.undefined_behavior_objs = objs
```

### Phase 5: Update `_process_rays()` Method

```python
def _process_rays(self):
    """Process all rays in the pending queue."""
    while self.pending_rays and self.processed_ray_count < self.max_rays:
        ray = self.pending_rays.pop(0)
        ray.is_new = False

        # Extend ray for intersection testing
        # ... existing code ...

        # Find the nearest intersection (now returns surface merging info)
        intersection_result = self._find_nearest_intersection(ray)

        if intersection_result is None:
            # No intersection
            self.ray_segments.append(ray)
        else:
            obj, incident_point, surface_merging_objs, undefined_behavior, undefined_behavior_objs = intersection_result

            if undefined_behavior:
                self.declare_undefined_behavior(ray, undefined_behavior_objs)

            # ... existing truncation and ray storage code ...

            if hasattr(obj, 'on_ray_incident'):
                # ... existing OutputRayGeom setup ...

                # Pass surface_merging_objs to on_ray_incident
                result = obj.on_ray_incident(
                    output_ray_geom,
                    self.processed_ray_count,
                    incident_point,
                    surface_merging_objs  # NEW PARAMETER
                )

                # Handle result, check for undefined behavior flag
                if result is not None:
                    if isinstance(result, dict):
                        if result.get('is_undefined_behavior'):
                            self.declare_undefined_behavior(ray, [obj])
                    # ... existing result handling ...

        self.processed_ray_count += 1
```

### Phase 6: Update Object Signatures

All optical objects' `on_ray_incident()` methods need to accept the new parameter:

**Old signature**:
```python
def on_ray_incident(self, ray, ray_index, incident_point):
```

**New signature**:
```python
def on_ray_incident(self, ray, ray_index, incident_point, surface_merging_objs=None):
```

**Objects to update**:
- `ideal_lens.py`
- `blocker.py`
- Any glass objects (they'll actually use the parameter)
- Any future optical elements

**Default behavior**: Most objects will ignore `surface_merging_objs` (just add the parameter with default `None`)

### Phase 7: Update Glass Objects to Use Surface Merging

Glass objects should check `surface_merging_objs` to determine refractive indices on both sides of the surface. This affects:
- Refraction calculations
- Reflection coefficients (Fresnel equations)
- Total internal reflection conditions

**Example for a glass refractor**:
```python
def on_ray_incident(self, ray, ray_index, incident_point, surface_merging_objs=None):
    # Determine refractive indices
    n1 = self._get_refractive_index_before(surface_merging_objs)
    n2 = self._get_refractive_index_after(surface_merging_objs)

    # Apply Snell's law with correct indices
    # ...
```

### Phase 8: Add Validation and Warnings

```python
def validate(self):
    """Check simulation and display warnings if necessary."""
    if self.total_undefined_behavior > self.UNDEFINED_BEHAVIOR_THRESHOLD:
        involved_types = [obj.__class__.__name__ for obj in self.undefined_behavior_objs]
        if len(involved_types) == 1:
            self.scene.warning = f"Undefined behavior detected with {involved_types[0]}"
        else:
            self.scene.warning = f"Undefined behavior: overlapping {involved_types[0]} and {involved_types[1]}"
```

## Testing Strategy

### Test 1: Two Adjacent Glass Objects
Create two glass blocks sharing a common edge:
```python
glass1 = Glass(...)  # Left block
glass2 = Glass(...)  # Right block, shares edge with glass1
```
**Expected**: Ray passes through both without warnings

### Test 2: Glass + Mirror at Common Edge
```python
glass = Glass(...)
mirror = Mirror(...)  # Edge aligned with glass boundary
```
**Expected**: Proper refraction/reflection, possibly undefined behavior warning if mirror doesn't merge with glass

### Test 3: Glass + Blocker
```python
glass = Glass(...)
blocker = Blocker(...)  # Blocking part of glass surface
```
**Expected**: Ray is blocked at surface, no warnings if blocker has `merges_with_glass=True`

### Test 4: Two Non-Glass Objects Overlapping
```python
mirror1 = Mirror(...)
mirror2 = Mirror(...)  # Overlapping with mirror1
```
**Expected**: Undefined behavior warning

## Implementation Order

1. **Phase 1-3**: Infrastructure (30 min)
   - Add glass detection attributes
   - Add helper methods

2. **Phase 2**: Modify `_find_nearest_intersection()` (1 hour)
   - Core surface merging logic
   - Most complex phase

3. **Phase 4-5**: Update simulator (30 min)
   - Undefined behavior tracking
   - Update `_process_rays()`

4. **Phase 6**: Update object signatures (20 min)
   - Add parameter to all `on_ray_incident()` methods
   - Backward compatible (default None)

5. **Phase 7**: Glass implementation (deferred)
   - Can be done later when implementing actual glass refraction
   - For now, just pass the parameter through

6. **Phase 8**: Validation (15 min)
   - Add warning generation

7. **Testing**: Create test cases (30 min)

**Total estimated time**: 3.5 hours

## Benefits

1. **Correctness**: Properly handles edge cases in optical simulations
2. **Compatibility**: Matches JavaScript implementation behavior
3. **Extensibility**: Framework ready for complex glass interactions
4. **User Experience**: Clear warnings for undefined behavior instead of silent errors
5. **Future-Ready**: Sets up infrastructure for full glass refraction implementation

## Notes

- Surface merging is essential for multi-element optical systems
- The JavaScript implementation is battle-tested with real optical simulations
- This is a prerequisite for implementing proper glass refraction (which requires knowing refractive indices on both sides of a surface)
- The implementation should be backward compatible - existing code without glass objects will work unchanged
