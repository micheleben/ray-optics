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
from .ray import Ray

# Import geometry to convert between formats
try:
    from . import geometry
except ImportError:
    import geometry


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
        # Reset simulation state
        self.pending_rays = []
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
