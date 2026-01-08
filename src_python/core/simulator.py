"""
Copyright 2024 The Ray Optics Simulation authors and contributors

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import math

# Handle both relative imports (when used as a module) and absolute imports (when run as script)
if __name__ == "__main__":
    from ray import Ray
    import geometry
else:
    from .ray import Ray
    from . import geometry


class Simulator:
    """
    Main ray tracing simulation engine.

    This class implements the core ray tracing algorithm that propagates
    rays through a scene containing optical objects. It maintains a queue
    of pending rays and processes them until all rays have either been
    absorbed or reached their maximum propagation distance.

    The simulation uses a breadth-first approach where rays are processed
    in the order they were created, ensuring proper handling of ray trees
    (e.g., a ray splitting at a beam splitter creates child rays).

    Attributes:
        scene (Scene): The scene containing objects and settings
        max_rays (int): Maximum number of ray segments to prevent infinite loops
        pending_rays (list): Queue of rays waiting to be processed
        processed_ray_count (int): Number of rays processed so far
        ray_segments (list): List of all ray segments for visualization
    """

    MIN_RAY_SEGMENT_LENGTH = 1e-6  # Minimum length to consider valid intersection

    def __init__(self, scene, max_rays=10000):
        """
        Initialize the simulator.

        Args:
            scene (Scene): The scene to simulate
            max_rays (int): Maximum ray segments to process (default: 10000)
        """
        self.scene = scene
        self.max_rays = max_rays
        self.pending_rays = []
        self.processed_ray_count = 0
        self.ray_segments = []

    def run(self):
        """
        Run the ray tracing simulation.

        This is the main entry point for simulation. It:
        1. Calls on_simulation_start() on all optical objects
        2. Processes all pending rays until the queue is empty
        3. Returns the list of ray segments for visualization

        Returns:
            list: List of ray segments (each is a Ray object)
        """
        # Reset simulation state (preserve any manually added pending_rays)
        # (i.e. we don't do self.pending_rays = [] here, to allow adding rays before run())
        # Note:  most users add rays via on_simulation_start() rather than manually
        self.processed_ray_count = 0
        self.ray_segments = []
        self.scene.error = None
        self.scene.warning = None

        # Step 1: Initialize all optical objects
        for obj in self.scene.optical_objs:
            if hasattr(obj, 'on_simulation_start'):
                result = obj.on_simulation_start()
                if result:
                    # Handle dict return format from PointSource
                    if isinstance(result, dict) and 'newRays' in result:
                        rays = result['newRays']
                    else:
                        rays = result

                    # Convert dict rays to Ray objects if needed
                    if rays:
                        if isinstance(rays, list):
                            for ray_data in rays:
                                ray = self._dict_to_ray(ray_data)
                                if ray:
                                    self.pending_rays.append(ray)
                        else:
                            ray = self._dict_to_ray(rays)
                            if ray:
                                self.pending_rays.append(ray)

        # Step 2: Process all rays
        self._process_rays()

        # Check if we hit the ray limit
        if self.processed_ray_count >= self.max_rays:
            self.scene.warning = f"Simulation stopped: maximum ray count ({self.max_rays}) reached"

        return self.ray_segments

    def _process_rays(self):
        """
        Process all rays in the pending queue.

        This implements the main ray tracing loop. For each ray:
        1. Find the nearest intersection with any optical object
        2. Truncate the ray at the intersection point
        3. Store the ray segment for visualization
        4. Call on_ray_incident() on the intersected object
        5. Continue until no more rays remain or max_rays is reached

        Note: Surface merging is NOT implemented in this phase (deferred to Phase 2.5).
        """
        while self.pending_rays and self.processed_ray_count < self.max_rays:
            ray = self.pending_rays.pop(0)  # FIFO queue
            ray.is_new = False

            # Extend ray p2 to represent an infinite ray
            # The ray's p2 from PointSource is just a direction (1 unit from p1)
            # We need to extend it to find intersections along the infinite ray
            dx = ray.p2['x'] - ray.p1['x']
            dy = ray.p2['y'] - ray.p1['y']
            length = math.sqrt(dx*dx + dy*dy)

            if length > 1e-10:
                # Extend to a large distance for intersection testing
                extension = 10000.0 / length
                ray.p2 = {
                    'x': ray.p1['x'] + dx * extension,
                    'y': ray.p1['y'] + dy * extension
                }

            # Find the nearest intersection
            intersection_info = self._find_nearest_intersection(ray)

            if intersection_info is None:
                # No intersection - ray continues to p2 (already extended above)
                self.ray_segments.append(ray)
            else:
                obj, incident_point = intersection_info

                # Save original p2 before truncation (needed for on_ray_incident)
                original_p2 = {'x': ray.p2['x'], 'y': ray.p2['y']}

                # Truncate ray at intersection point
                ray.p2 = incident_point

                # Store the ray segment
                self.ray_segments.append(ray)

                # Let the object handle the incident ray
                if hasattr(obj, 'on_ray_incident'):
                    # Create output ray compatible with existing objects
                    # They expect ray.p1/p2 to be dicts
                    class OutputRayGeom:
                        pass

                    output_ray_geom = OutputRayGeom()
                    output_ray_geom.p1 = incident_point
                    # p2 should be in the ray direction (use original p2, not incident point)
                    output_ray_geom.p2 = original_p2
                    output_ray_geom.brightness_s = ray.brightness_s
                    output_ray_geom.brightness_p = ray.brightness_p
                    output_ray_geom.wavelength = ray.wavelength

                    # Object modifies the ray (may change direction, brightness, etc.)
                    result = obj.on_ray_incident(output_ray_geom, self.processed_ray_count, incident_point)

                    # Handle different return types and convert back to Ray objects
                    if result is not None:
                        if isinstance(result, list):
                            # Multiple output rays (e.g., beam splitter)
                            for new_ray_geom in result:
                                new_ray = self._dict_to_ray(new_ray_geom)
                                if new_ray and new_ray.total_brightness > 1e-6:
                                    self.pending_rays.append(new_ray)
                        else:
                            # Single output ray
                            new_ray = self._dict_to_ray(result)
                            if new_ray and new_ray.total_brightness > 1e-6:
                                self.pending_rays.append(new_ray)
                    else:
                        # Object modified the ray in-place, convert back to Ray
                        new_ray = self._dict_to_ray(output_ray_geom)
                        if new_ray and new_ray.total_brightness > 1e-6:
                            self.pending_rays.append(new_ray)
                    # If brightness is zero or None returned, ray is absorbed

            self.processed_ray_count += 1

    def _find_nearest_intersection(self, ray):
        """
        Find the nearest intersection point between a ray and all optical objects.

        Args:
            ray (Ray): The ray to test for intersections

        Returns:
            tuple or None: (object, intersection_point) if intersection found,
                          None if no intersection
        """
        nearest_obj = None
        nearest_point = None
        nearest_distance_squared = float('inf')

        # Create a geometry-compatible ray object
        # The existing objects expect ray.p1 and ray.p2 to be dicts (not Point objects)
        class RayGeom:
            pass

        ray_geom = RayGeom()
        ray_geom.p1 = ray.p1  # Already a dict
        ray_geom.p2 = ray.p2  # Already a dict
        ray_geom.brightness_s = ray.brightness_s
        ray_geom.brightness_p = ray.brightness_p
        ray_geom.wavelength = ray.wavelength

        # Test intersection with all optical objects
        for obj in self.scene.optical_objs:
            if not hasattr(obj, 'check_ray_intersects'):
                continue

            intersection_point = obj.check_ray_intersects(ray_geom)

            if intersection_point is not None:
                # Convert Point to dict if needed
                if hasattr(intersection_point, 'x') and hasattr(intersection_point, 'y'):
                    intersection_dict = {'x': intersection_point.x, 'y': intersection_point.y}
                else:
                    intersection_dict = intersection_point

                # Calculate distance from ray start to intersection
                dx = intersection_dict['x'] - ray.p1['x']
                dy = intersection_dict['y'] - ray.p1['y']
                distance_squared = dx * dx + dy * dy

                # Check if this is a valid intersection (not too close to start)
                if distance_squared < self.MIN_RAY_SEGMENT_LENGTH ** 2:
                    continue

                # Check if this is the nearest intersection so far
                if distance_squared < nearest_distance_squared:
                    nearest_distance_squared = distance_squared
                    nearest_point = intersection_dict
                    nearest_obj = obj

        if nearest_obj is None:
            return None

        return (nearest_obj, nearest_point)

    def add_ray(self, ray):
        """
        Add a ray to the pending queue.

        This is useful for adding rays during simulation (e.g., from
        user interaction or from objects that emit rays dynamically).

        Args:
            ray (Ray): The ray to add
        """
        if self.processed_ray_count < self.max_rays:
            self.pending_rays.append(ray)

    def _dict_to_ray(self, ray_data):
        """
        Convert a ray dictionary/object to a Ray object.

        The existing scene objects use geometry.line() which returns objects.
        This method converts them to Ray objects for the simulator.

        Args:
            ray_data (dict, object, or Ray): Ray data to convert

        Returns:
            Ray or None: Converted Ray object, or None if invalid
        """
        if isinstance(ray_data, Ray):
            return ray_data

        # Handle geometry.line() objects (have p1, p2 as attributes)
        if hasattr(ray_data, 'p1') and hasattr(ray_data, 'p2'):
            # Extract p1 and p2 (convert Point objects to dicts if needed)
            p1 = ray_data.p1
            p2 = ray_data.p2

            # Convert Point objects to dicts
            if hasattr(p1, 'x') and hasattr(p1, 'y'):
                p1 = {'x': p1.x, 'y': p1.y}
            if hasattr(p2, 'x') and hasattr(p2, 'y'):
                p2 = {'x': p2.x, 'y': p2.y}

            ray = Ray(
                p1=p1,
                p2=p2,
                brightness_s=getattr(ray_data, 'brightness_s', 0.0),
                brightness_p=getattr(ray_data, 'brightness_p', 0.0),
                wavelength=getattr(ray_data, 'wavelength', None)
            )

            # Copy additional properties if present
            if hasattr(ray_data, 'gap'):
                ray.gap = ray_data.gap
            if hasattr(ray_data, 'isNew'):
                ray.is_new = ray_data.isNew

            return ray

        # Handle dictionary format
        if isinstance(ray_data, dict) and 'p1' in ray_data and 'p2' in ray_data:
            ray = Ray(
                p1=ray_data['p1'],
                p2=ray_data['p2'],
                brightness_s=ray_data.get('brightness_s', 0.0),
                brightness_p=ray_data.get('brightness_p', 0.0),
                wavelength=ray_data.get('wavelength', None)
            )

            # Copy additional properties if present
            if 'gap' in ray_data:
                ray.gap = ray_data['gap']
            if 'isNew' in ray_data:
                ray.is_new = ray_data['isNew']

            return ray

        return None


# Example usage and testing
if __name__ == "__main__":
    print("Testing Simulator class...\n")

    # Import required modules for testing
    try:
        from .scene import Scene
        from .ray import Ray
        from . import geometry
    except ImportError:
        # Handle running as script
        import sys
        import os
        sys.path.insert(0, os.path.dirname(__file__))
        from scene import Scene
        from ray import Ray
        import geometry

    # Mock optical objects for testing
    class MockLightSource:
        """Mock light source that emits a single ray."""
        def __init__(self, position, direction):
            self.position = position
            self.direction = direction
            self.is_optical = True

        def on_simulation_start(self):
            """Emit initial ray."""
            return Ray(
                p1=self.position,
                p2={'x': self.position['x'] + self.direction['x'],
                    'y': self.position['y'] + self.direction['y']},
                brightness_s=0.5,
                brightness_p=0.5
            )

        def check_ray_intersects(self, ray):
            """Light sources don't intersect rays."""
            return None

    class MockMirror:
        """Mock mirror that reflects rays."""
        def __init__(self, p1, p2):
            self.p1 = p1
            self.p2 = p2
            self.is_optical = True

        def check_ray_intersects(self, ray):
            """Find intersection with mirror line segment."""
            # Simple line-segment intersection
            mirror_line = geometry.Geometry.line(
                geometry.Geometry.point(self.p1['x'], self.p1['y']),
                geometry.Geometry.point(self.p2['x'], self.p2['y'])
            )
            ray_line = geometry.Geometry.line(
                geometry.Geometry.point(ray.p1['x'], ray.p1['y']),
                geometry.Geometry.point(ray.p2['x'], ray.p2['y'])
            )

            intersection = geometry.Geometry.lines_intersection(mirror_line, ray_line)

            # Check if intersection is within the segment bounds
            if math.isinf(intersection.x) or math.isinf(intersection.y):
                return None

            # Check if point is on the mirror segment
            min_x = min(self.p1['x'], self.p2['x'])
            max_x = max(self.p1['x'], self.p2['x'])
            min_y = min(self.p1['y'], self.p2['y'])
            max_y = max(self.p1['y'], self.p2['y'])

            epsilon = 1e-6
            if (min_x - epsilon <= intersection.x <= max_x + epsilon and
                min_y - epsilon <= intersection.y <= max_y + epsilon):
                # Check if intersection is forward along the ray
                dx = intersection.x - ray.p1['x']
                dy = intersection.y - ray.p1['y']
                if dx * (ray.p2['x'] - ray.p1['x']) + dy * (ray.p2['y'] - ray.p1['y']) > 0:
                    return {'x': intersection.x, 'y': intersection.y}

            return None

        def on_ray_incident(self, ray, ray_index, incident_point):
            """Reflect the ray."""
            # Calculate mirror normal
            dx = self.p2['x'] - self.p1['x']
            dy = self.p2['y'] - self.p1['y']
            length = math.sqrt(dx*dx + dy*dy)

            # Normal is perpendicular to mirror
            normal_x = -dy / length
            normal_y = dx / length

            # Incident direction
            inc_dx = ray.p2['x'] - ray.p1['x']
            inc_dy = ray.p2['y'] - ray.p1['y']
            inc_len = math.sqrt(inc_dx*inc_dx + inc_dy*inc_dy)
            inc_dx /= inc_len
            inc_dy /= inc_len

            # Reflect: r = d - 2(d·n)n
            dot = inc_dx * normal_x + inc_dy * normal_y
            ref_dx = inc_dx - 2 * dot * normal_x
            ref_dy = inc_dy - 2 * dot * normal_y

            # Update ray
            ray.p1 = incident_point
            ray.p2 = {
                'x': incident_point['x'] + ref_dx,
                'y': incident_point['y'] + ref_dy
            }

    class MockAbsorber:
        """Mock absorber that stops rays."""
        def __init__(self, p1, p2):
            self.p1 = p1
            self.p2 = p2
            self.is_optical = True

        def check_ray_intersects(self, ray):
            """Find intersection with absorber line segment."""
            absorber_line = geometry.Geometry.line(
                geometry.Geometry.point(self.p1['x'], self.p1['y']),
                geometry.Geometry.point(self.p2['x'], self.p2['y'])
            )
            ray_line = geometry.Geometry.line(
                geometry.Geometry.point(ray.p1['x'], ray.p1['y']),
                geometry.Geometry.point(ray.p2['x'], ray.p2['y'])
            )

            intersection = geometry.Geometry.lines_intersection(absorber_line, ray_line)

            if math.isinf(intersection.x) or math.isinf(intersection.y):
                return None

            # Check if point is on the absorber segment
            min_x = min(self.p1['x'], self.p2['x'])
            max_x = max(self.p1['x'], self.p2['x'])
            min_y = min(self.p1['y'], self.p2['y'])
            max_y = max(self.p1['y'], self.p2['y'])

            epsilon = 1e-6
            if (min_x - epsilon <= intersection.x <= max_x + epsilon and
                min_y - epsilon <= intersection.y <= max_y + epsilon):
                dx = intersection.x - ray.p1['x']
                dy = intersection.y - ray.p1['y']
                if dx * (ray.p2['x'] - ray.p1['x']) + dy * (ray.p2['y'] - ray.p1['y']) > 0:
                    return {'x': intersection.x, 'y': intersection.y}

            return None

        def on_ray_incident(self, ray, ray_index, incident_point):
            """Absorb the ray (set brightness to zero)."""
            ray.brightness_s = 0.0
            ray.brightness_p = 0.0
            return None  # Ray is absorbed, no output ray

    # Test 1: Basic simulation with no objects
    print("Test 1: Empty scene simulation")
    scene = Scene()
    simulator = Simulator(scene, max_rays=100)
    ray_segments = simulator.run()
    print(f"  Scene with no objects")
    print(f"  Ray segments: {len(ray_segments)}")
    print(f"  Processed rays: {simulator.processed_ray_count}")
    print(f"  Expected: 0 segments (no light sources)")

    # Test 2: Single ray with no obstacles
    print("\nTest 2: Single ray, no obstacles")
    scene2 = Scene()
    source = MockLightSource(
        position={'x': 0, 'y': 0},
        direction={'x': 1, 'y': 0}
    )
    scene2.add_object(source)

    simulator2 = Simulator(scene2, max_rays=100)
    ray_segments2 = simulator2.run()
    print(f"  Light source at (0, 0) pointing right")
    print(f"  Ray segments: {len(ray_segments2)}")
    print(f"  Processed rays: {simulator2.processed_ray_count}")
    print(f"  First ray: {ray_segments2[0].p1} -> {ray_segments2[0].p2}")
    print(f"  Expected: 1 segment extending to infinity")

    # Test 3: Ray hitting a mirror
    # Geometry: 45° ray (direction 1,1) hits vertical mirror at x=50,y=50
    # Reflects to 135° (direction -1,1), going left-up
    # Large coordinates are due to ray extension (10000 units for intersection testing)
    print("\nTest 3: Ray reflection by mirror")
    scene3 = Scene()
    source3 = MockLightSource(
        position={'x': 0, 'y': 0},
        direction={'x': 1, 'y': 1}
    )
    mirror = MockMirror(
        p1={'x': 50, 'y': 0},
        p2={'x': 50, 'y': 100}
    )
    scene3.add_object(source3)
    scene3.add_object(mirror)

    simulator3 = Simulator(scene3, max_rays=100)
    ray_segments3 = simulator3.run()
    print(f"  Light source at (0, 0) at 45° angle")
    print(f"  Vertical mirror at x=50")
    print(f"  Ray segments: {len(ray_segments3)}")
    print(f"  Processed rays: {simulator3.processed_ray_count}")
    if len(ray_segments3) >= 2:
        print(f"  Incident ray: ({ray_segments3[0].p1['x']:.1f}, {ray_segments3[0].p1['y']:.1f}) -> ({ray_segments3[0].p2['x']:.1f}, {ray_segments3[0].p2['y']:.1f})")
        print(f"  Reflected ray: ({ray_segments3[1].p1['x']:.1f}, {ray_segments3[1].p1['y']:.1f}) -> ({ray_segments3[1].p2['x']:.1f}, {ray_segments3[1].p2['y']:.1f})")
        # Verify reflection angle: should be 135° (left-up at 45°)
        dx = ray_segments3[1].p2['x'] - ray_segments3[1].p1['x']
        dy = ray_segments3[1].p2['y'] - ray_segments3[1].p1['y']
        print(f"  Reflected direction ratio dy/dx = {dy/dx:.2f} (expected: -1.0 for 135°)")
    print(f"  Expected: 2 segments (incident + reflected)")

    # Test 4: Ray absorption
    # Note:The ray segment traveling to the absorber should show full brightness (the light was bright until it hit the absorber)
    # The absorber prevents further propagation by returning None or setting brightness to 0
    print("\nTest 4: Ray absorption")
    scene4 = Scene()
    source4 = MockLightSource(
        position={'x': 0, 'y': 0},
        direction={'x': 1, 'y': 0}
    )
    absorber = MockAbsorber(
        p1={'x': 50, 'y': -10},
        p2={'x': 50, 'y': 10}
    )
    scene4.add_object(source4)
    scene4.add_object(absorber)

    simulator4 = Simulator(scene4, max_rays=100)
    ray_segments4 = simulator4.run()
    print(f"  Light source at (0, 0) pointing right")
    print(f"  Absorber at x=50")
    print(f"  Ray segments: {len(ray_segments4)}")
    print(f"  Processed rays: {simulator4.processed_ray_count}")
    if len(ray_segments4) >= 1:
        print(f"  Ray: ({ray_segments4[0].p1['x']:.1f}, {ray_segments4[0].p1['y']:.1f}) -> ({ray_segments4[0].p2['x']:.1f}, {ray_segments4[0].p2['y']:.1f})")
        print(f"  Incident brightness: {ray_segments4[0].total_brightness:.2f} (before absorption)")
    print(f"  Expected: 1 segment (ray travels to absorber with full brightness, then stops)")

    # Test 5: Max ray limit
    print("\nTest 5: Maximum ray limit")
    scene5 = Scene()
    # Create multiple sources
    for i in range(10):
        source = MockLightSource(
            position={'x': 0, 'y': i * 10},
            direction={'x': 1, 'y': 0}
        )
        scene5.add_object(source)

    simulator5 = Simulator(scene5, max_rays=5)  # Limit to 5 rays
    ray_segments5 = simulator5.run()
    print(f"  Scene with 10 light sources")
    print(f"  Max rays limit: 5")
    print(f"  Ray segments: {len(ray_segments5)}")
    print(f"  Processed rays: {simulator5.processed_ray_count}")
    print(f"  Warning: {scene5.warning}")
    print(f"  Expected: 5 segments, warning about ray limit")

    # Test 6: Ray conversion (_dict_to_ray)
    print("\nTest 6: Ray conversion")
    test_ray = Ray(
        p1={'x': 10, 'y': 20},
        p2={'x': 30, 'y': 40},
        brightness_s=0.7,
        brightness_p=0.3,
        wavelength=550
    )
    test_ray.gap = True

    # Test Ray object passthrough
    converted1 = simulator._dict_to_ray(test_ray)
    print(f"  Ray object passthrough: {converted1 is test_ray}")

    # Test dict conversion
    ray_dict = {
        'p1': {'x': 5, 'y': 10},
        'p2': {'x': 15, 'y': 20},
        'brightness_s': 0.6,
        'brightness_p': 0.4,
        'wavelength': 650,
        'gap': False
    }
    converted2 = simulator._dict_to_ray(ray_dict)
    print(f"  Dict conversion: p1={converted2.p1}, brightness={converted2.total_brightness:.1f}, wavelength={converted2.wavelength}")

    # Test geometry object conversion
    class GeomRay:
        def __init__(self):
            self.p1 = geometry.Geometry.point(1, 2)
            self.p2 = geometry.Geometry.point(3, 4)
            self.brightness_s = 0.5
            self.brightness_p = 0.5
            self.wavelength = None

    geom_ray = GeomRay()
    converted3 = simulator._dict_to_ray(geom_ray)
    print(f"  Geometry object conversion: p1={converted3.p1}, p2={converted3.p2}")

    # Test 7: Pending rays queue
    print("\nTest 7: Pending rays and add_ray")
    scene7 = Scene()
    simulator7 = Simulator(scene7, max_rays=10)

    # Add rays manually
    for i in range(3):
        ray = Ray(
            p1={'x': i * 10, 'y': 0},
            p2={'x': i * 10 + 1, 'y': 1},
            brightness_s=0.5,
            brightness_p=0.5
        )
        simulator7.add_ray(ray)

    print(f"  Added 3 rays manually")
    print(f"  Pending rays: {len(simulator7.pending_rays)}")

    ray_segments7 = simulator7.run()
    print(f"  After simulation:")
    print(f"  Ray segments: {len(ray_segments7)}")
    print(f"  Processed rays: {simulator7.processed_ray_count}")

    print("\nSimulator test completed successfully!")
