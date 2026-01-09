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
from typing import Dict, Any, Optional, List

# Handle both relative imports (when used as a module) and absolute imports (when run as script)
if __name__ == "__main__":
    from core.scene_objs.base_glass import BaseGlass
    from core.constants import MIN_RAY_SEGMENT_LENGTH
    from core import geometry
else:
    from ..base_glass import BaseGlass
    from ...constants import MIN_RAY_SEGMENT_LENGTH
    from ... import geometry


class Glass(BaseGlass):
    """
    Glass of arbitrary shape consisting of line segments and circular arcs.

    The glass shape is defined by a path of points. Each point has coordinates (x, y)
    and an 'arc' flag. If path[i].arc is True, then the segment path[i-1]→path[i]→path[i+1]
    forms a circular arc. Otherwise, path[i-1]→path[i] and path[i]→path[i+1] are line segments.

    Attributes:
        path: List of points defining the glass boundary. Each point is a dict with:
              - x, y: Coordinates
              - arc: Boolean flag (True = circular arc, False = line segment)
        not_done: Whether the user is still drawing the glass (UI construction mode).
        ref_index: The refractive index, or Cauchy coefficient A if "Simulate Colors" is on.
        cauchy_b: The Cauchy coefficient B if "Simulate Colors" is on (in μm²).

    Usage:
        Glass objects are useful for:
        - Prisms with arbitrary polygon shapes
        - Lenses with curved surfaces (circular arcs)
        - Complex optical elements combining straight and curved surfaces
        - Custom glass shapes for specific optical designs

    Notes:
        - The path forms a closed polygon when not_done=False
        - Circular arcs are defined by three consecutive points
        - Supports surface merging with other glass objects
        - Refractive index can be wavelength-dependent (Cauchy equation)
    """

    type = 'Glass'
    is_optical = True
    merges_with_glass = True
    serializable_defaults = {
        'path': [],
        'not_done': False,
        'ref_index': 1.5,
        'cauchy_b': 0.004
    }

    def __init__(self, scene, json_obj=None):
        """
        Initialize the glass object.

        Args:
            scene: The scene this glass belongs to.
            json_obj: Optional JSON object with glass properties.
        """
        super().__init__(scene, json_obj)

        # Ensure path points have proper structure
        if hasattr(self, 'path') and self.path:
            for point in self.path:
                if 'arc' not in point:
                    point['arc'] = False

    def populate_obj_bar(self, obj_bar):
        """
        Populate the object bar with glass controls.

        Args:
            obj_bar: The object bar to populate.
        """
        obj_bar.set_title('Glass')
        super().populate_obj_bar(obj_bar)

    def draw(self, canvas_renderer, is_above_light, is_hovered):
        """
        Draw the glass on the canvas.

        Args:
            canvas_renderer: The canvas renderer.
            is_above_light: Whether rendering above the light layer.
            is_hovered: Whether the glass is hovered by the mouse.
        """
        if not self.path:
            return

        if self.not_done:
            # Still under construction - draw partial path
            self._draw_path(canvas_renderer, is_hovered, closed=False)
        else:
            # Completed glass - draw filled shape
            self._draw_path(canvas_renderer, is_hovered, closed=True)
            self.fill_glass(canvas_renderer, is_above_light, is_hovered)

        # Draw control points if hovered
        if is_hovered:
            for point in self.path:
                if 'arc' in point:
                    color = [255, 0, 255, 255] if point['arc'] else [255, 0, 0, 255]
                    canvas_renderer.draw_rect(
                        point['x'] - 1.5 * canvas_renderer.length_scale,
                        point['y'] - 1.5 * canvas_renderer.length_scale,
                        3 * canvas_renderer.length_scale,
                        3 * canvas_renderer.length_scale,
                        color
                    )

    def _draw_path(self, canvas_renderer, is_hovered, closed=True):
        """
        Helper method to draw the glass path.

        Args:
            canvas_renderer: The canvas renderer.
            is_hovered: Whether the glass is hovered.
            closed: Whether to close the path (connect last to first point).
        """
        if len(self.path) < 2:
            return

        # Implementation would use canvas_renderer to draw lines and arcs
        # For now, this is a placeholder for the complex drawing logic
        pass

    def move(self, diff_x, diff_y):
        """
        Move the glass.

        Args:
            diff_x: X displacement.
            diff_y: Y displacement.

        Returns:
            True to indicate the move was successful.
        """
        for point in self.path:
            point['x'] += diff_x
            point['y'] += diff_y
        return True

    def rotate(self, angle, center=None):
        """
        Rotate the glass around a center.

        Args:
            angle: Rotation angle in radians.
            center: Center of rotation (defaults to geometric center).

        Returns:
            True to indicate the rotation was successful.
        """
        if center is None:
            center = self.get_default_center()

        cos_a = math.cos(angle)
        sin_a = math.sin(angle)

        for point in self.path:
            dx = point['x'] - center['x']
            dy = point['y'] - center['y']
            point['x'] = center['x'] + dx * cos_a - dy * sin_a
            point['y'] = center['y'] + dx * sin_a + dy * cos_a

        return True

    def scale(self, scale_factor, center=None):
        """
        Scale the glass relative to a center.

        Args:
            scale_factor: The scale factor.
            center: Center of scaling (defaults to geometric center).

        Returns:
            True to indicate the scaling was successful.
        """
        if center is None:
            center = self.get_default_center()

        for point in self.path:
            point['x'] = center['x'] + (point['x'] - center['x']) * scale_factor
            point['y'] = center['y'] + (point['y'] - center['y']) * scale_factor

        return True

    def get_default_center(self):
        """
        Get the default center for rotation/scaling.

        Returns:
            The geometric center (average of all path points).
        """
        if not self.path:
            return {'x': 0, 'y': 0}

        sum_x = sum(p['x'] for p in self.path)
        sum_y = sum(p['y'] for p in self.path)

        return {
            'x': sum_x / len(self.path),
            'y': sum_y / len(self.path)
        }

    def check_ray_intersects(self, ray):
        """
        Check if a ray intersects with the glass.

        Args:
            ray: The ray to check.

        Returns:
            The nearest intersection point, or None if no intersection.
        """
        if self.not_done or self.ref_index <= 0 or not self.path:
            return None

        min_distance_sq = float('inf')
        nearest_point = None

        # Check each segment (line or arc) in the path
        for i in range(len(self.path)):
            intersection = self._check_segment_intersection(ray, i)
            if intersection:
                dist_sq = geometry.distance_squared(ray.p1, intersection)
                if dist_sq < min_distance_sq and dist_sq > MIN_RAY_SEGMENT_LENGTH ** 2 * self.scene.length_scale ** 2:
                    min_distance_sq = dist_sq
                    nearest_point = intersection

        return nearest_point

    def _check_segment_intersection(self, ray, i):
        """
        Check intersection with a single segment of the path.

        Args:
            ray: The ray to check.
            i: Index of the current path segment.

        Returns:
            Intersection point or None.
        """
        next_i = (i + 1) % len(self.path)
        next_next_i = (i + 2) % len(self.path)

        if self.path[next_i].get('arc') and not self.path[i].get('arc'):
            # Circular arc from path[i] through path[i+1] to path[i+2]
            return self._check_arc_intersection(ray, i, next_i, next_next_i)
        elif not self.path[next_i].get('arc') and not self.path[i].get('arc'):
            # Line segment from path[i] to path[i+1]
            return self._check_line_segment_intersection(ray, i, next_i)

        return None

    def _check_line_segment_intersection(self, ray, i, next_i):
        """
        Check intersection with a line segment.

        Args:
            ray: The ray to check.
            i: Start point index.
            next_i: End point index.

        Returns:
            Intersection point or None.
        """
        p1 = geometry.point(self.path[i]['x'], self.path[i]['y'])
        p2 = geometry.point(self.path[next_i]['x'], self.path[next_i]['y'])

        intersection = geometry.lines_intersection(
            geometry.line(ray.p1, ray.p2),
            geometry.line(p1, p2)
        )

        if (geometry.intersection_is_on_segment(intersection, geometry.line(p1, p2)) and
            geometry.intersection_is_on_ray(intersection, ray)):
            return intersection

        return None

    def _check_arc_intersection(self, ray, i, mid_i, next_i):
        """
        Check intersection with a circular arc.

        Args:
            ray: The ray to check.
            i: First point index.
            mid_i: Middle point index (defines the arc).
            next_i: Last point index.

        Returns:
            Nearest valid intersection point or None.
        """
        p1 = geometry.point(self.path[i]['x'], self.path[i]['y'])
        p2 = geometry.point(self.path[next_i]['x'], self.path[next_i]['y'])
        p3 = geometry.point(self.path[mid_i]['x'], self.path[mid_i]['y'])

        # Find center of circle passing through p1, p3, p2
        center = geometry.lines_intersection(
            geometry.perpendicular_bisector(geometry.line(p1, p3)),
            geometry.perpendicular_bisector(geometry.line(p2, p3))
        )

        if not (math.isfinite(center.x) and math.isfinite(center.y)):
            # Collinear points - treat as line segment
            return self._check_line_segment_intersection(ray, i, next_i)

        r = geometry.distance(center, p3)
        intersections = geometry.line_circle_intersections(
            geometry.line(ray.p1, ray.p2),
            geometry.circle(center, p2)
        )

        # Find nearest valid intersection on the arc
        nearest = None
        min_dist_sq = float('inf')

        for intersection in [intersections[1], intersections[2]]:
            if self._point_is_on_arc(intersection, center, p1, p2, p3):
                if geometry.intersection_is_on_ray(intersection, ray):
                    dist_sq = geometry.distance_squared(ray.p1, intersection)
                    if dist_sq < min_dist_sq:
                        min_dist_sq = dist_sq
                        nearest = intersection

        return nearest

    def _point_is_on_arc(self, point, center, p1, p2, p3):
        """
        Check if a point is on the arc defined by p1→p3→p2.

        Args:
            point: Point to check.
            center: Center of the circle.
            p1: Start point of arc.
            p2: End point of arc.
            p3: Middle point defining the arc.

        Returns:
            True if point is on the arc.
        """
        # Check if the intersection point is actually part of the arc segment
        # This uses the logic from the JavaScript: the point should not be on the line p1-p2
        line_p1_p2 = geometry.line(p1, p2)
        line_p3_point = geometry.line(p3, point)
        test_intersection = geometry.lines_intersection(line_p1_p2, line_p3_point)

        return not geometry.intersection_is_on_segment(test_intersection, line_p3_point)

    def on_ray_incident(self, ray, ray_index, incident_point, surface_merging_objs=None):
        """
        Handle ray incidence on the glass.

        Args:
            ray: The incident ray.
            ray_index: Index of the ray.
            incident_point: The point where the ray hits the glass.
            surface_merging_objs: List of glass objects to merge with.

        Returns:
            Dict with ray behavior (refracted, reflected, or absorbed).
        """
        if self.not_done:
            return None

        incident_data = self.get_incident_data(ray)
        incident_type = incident_data['incident_type']

        if incident_type == 1:
            # From inside to outside
            n1 = self.get_ref_index_at(incident_point, ray)
        elif incident_type == -1:
            # From outside to inside
            n1 = 1 / self.get_ref_index_at(incident_point, ray)
        elif incident_type == 0:
            # Equivalent to not intersecting (e.g., overlapping interfaces)
            n1 = 1
        else:
            # Undefined behavior (e.g., incident on edge point)
            return {
                'isAbsorbed': True,
                'isUndefinedBehavior': True
            }

        body_merging_obj = ray.body_merging_obj if hasattr(ray, 'body_merging_obj') else None
        return self.refract(
            ray, ray_index, incident_point, incident_data['normal'],
            n1, surface_merging_objs, body_merging_obj
        )

    def get_incident_type(self, ray):
        """
        Get the incident type for a ray.

        Args:
            ray: The ray.

        Returns:
            Incident type: 1 (inside to outside), -1 (outside to inside),
            0 (overlapping surfaces), or NaN (edge incident).
        """
        return self.get_incident_data(ray)['incident_type']

    def get_incident_data(self, ray):
        """
        Get detailed incident data for a ray.

        This method determines:
        - The intersection point
        - The surface normal at the intersection
        - The incident type (inside/outside/edge)

        Args:
            ray: The ray to analyze.

        Returns:
            Dict with keys: s_point, normal, incident_type
        """
        if not self.path:
            return {'s_point': None, 'normal': {'x': 0, 'y': 0}, 'incident_type': 0}

        min_distance_sq = float('inf')
        nearest_point = None
        normal_x = 0
        normal_y = 0
        near_edge = False
        surface_multiplicity = 1

        # Create a test ray with slight perturbation for inside/outside test
        ray2 = geometry.line(
            ray.p1,
            geometry.point(
                ray.p2.x + self.scene.rng() * 1e-5,
                ray.p2.y + self.scene.rng() * 1e-5
            )
        )
        ray_intersect_count = 0

        # Check each segment
        for i in range(len(self.path)):
            segment_data = self._get_segment_incident_data(ray, ray2, i)

            if segment_data['point']:
                if (nearest_point and
                    geometry.distance_squared(segment_data['point'], nearest_point) <
                    MIN_RAY_SEGMENT_LENGTH ** 2 * self.scene.length_scale ** 2):
                    # Self surface merging
                    surface_multiplicity += 1
                elif segment_data['distance_sq'] < min_distance_sq:
                    min_distance_sq = segment_data['distance_sq']
                    nearest_point = segment_data['point']
                    normal_x = segment_data['normal_x']
                    normal_y = segment_data['normal_y']
                    near_edge = segment_data['near_edge']
                    surface_multiplicity = 1

            ray_intersect_count += segment_data['ray2_intersect_count']

        # Determine incident type
        if near_edge:
            incident_type = float('nan')  # Incident on an edge point
        elif surface_multiplicity % 2 == 0:
            incident_type = 0  # Overlapping surfaces
        elif ray_intersect_count % 2 == 1:
            incident_type = 1  # From inside to outside
        else:
            incident_type = -1  # From outside to inside

        return {
            's_point': nearest_point,
            'normal': {'x': normal_x, 'y': normal_y},
            'incident_type': incident_type
        }

    def _get_segment_incident_data(self, ray, ray2, i):
        """
        Get incident data for a single segment.

        Args:
            ray: The main ray.
            ray2: The test ray for inside/outside determination.
            i: Segment index.

        Returns:
            Dict with segment incident data.
        """
        next_i = (i + 1) % len(self.path)
        next_next_i = (i + 2) % len(self.path)

        result = {
            'point': None,
            'distance_sq': float('inf'),
            'normal_x': 0,
            'normal_y': 0,
            'near_edge': False,
            'ray2_intersect_count': 0
        }

        if self.path[next_i].get('arc') and not self.path[i].get('arc'):
            # Circular arc
            self._process_arc_segment(ray, ray2, i, next_i, next_next_i, result)
        elif not self.path[next_i].get('arc') and not self.path[i].get('arc'):
            # Line segment
            self._process_line_segment(ray, ray2, i, next_i, result)

        return result

    def _process_line_segment(self, ray, ray2, i, next_i, result):
        """Process a line segment for incident data."""
        p1 = self.path[i]
        p2 = self.path[next_i]

        # Check main ray intersection
        rp = geometry.lines_intersection(
            geometry.line(ray.p1, ray.p2),
            geometry.line(geometry.point(p1['x'], p1['y']), geometry.point(p2['x'], p2['y']))
        )

        seg_line = geometry.line(geometry.point(p1['x'], p1['y']), geometry.point(p2['x'], p2['y']))
        min_seg_len_sq = MIN_RAY_SEGMENT_LENGTH ** 2 * self.scene.length_scale ** 2

        if (geometry.intersection_is_on_segment(rp, seg_line) and
            geometry.intersection_is_on_ray(rp, ray) and
            geometry.distance_squared(ray.p1, rp) > min_seg_len_sq):

            result['point'] = rp
            result['distance_sq'] = geometry.distance_squared(ray.p1, rp)

            # Calculate normal
            dx = p2['x'] - p1['x']
            dy = p2['y'] - p1['y']
            rdot = (ray.p2.x - ray.p1.x) * dx + (ray.p2.y - ray.p1.y) * dy
            ssq = dx * dx + dy * dy

            result['normal_x'] = rdot * dx - ssq * (ray.p2.x - ray.p1.x)
            result['normal_y'] = rdot * dy - ssq * (ray.p2.y - ray.p1.y)

            # Check if near edge
            if (geometry.distance_squared(rp, geometry.point(p1['x'], p1['y'])) < min_seg_len_sq or
                geometry.distance_squared(rp, geometry.point(p2['x'], p2['y'])) < min_seg_len_sq):
                result['near_edge'] = True

        # Check test ray intersection for inside/outside determination
        rp2 = geometry.lines_intersection(
            geometry.line(ray2.p1, ray2.p2),
            geometry.line(geometry.point(p1['x'], p1['y']), geometry.point(p2['x'], p2['y']))
        )

        if (geometry.intersection_is_on_segment(rp2, seg_line) and
            geometry.intersection_is_on_ray(rp2, ray2) and
            geometry.distance_squared(ray2.p1, rp2) > min_seg_len_sq):
            result['ray2_intersect_count'] = 1

    def _process_arc_segment(self, ray, ray2, i, mid_i, next_i, result):
        """Process a circular arc segment for incident data."""
        p1 = geometry.point(self.path[i]['x'], self.path[i]['y'])
        p2 = geometry.point(self.path[next_i]['x'], self.path[next_i]['y'])
        p3 = geometry.point(self.path[mid_i]['x'], self.path[mid_i]['y'])

        center = geometry.lines_intersection(
            geometry.perpendicular_bisector(geometry.line(p1, p3)),
            geometry.perpendicular_bisector(geometry.line(p2, p3))
        )

        if not (math.isfinite(center.x) and math.isfinite(center.y)):
            # Collinear - treat as line segment
            self._process_line_segment(ray, ray2, i, next_i, result)
            return

        # Find intersections with circle
        rp_temp = geometry.line_circle_intersections(
            geometry.line(ray.p1, ray.p2),
            geometry.circle(center, p2)
        )
        rp2_temp = geometry.line_circle_intersections(
            geometry.line(ray2.p1, ray2.p2),
            geometry.circle(center, p2)
        )

        min_seg_len_sq = MIN_RAY_SEGMENT_LENGTH ** 2 * self.scene.length_scale ** 2

        # Check both intersection points
        for ii in [1, 2]:
            rp = rp_temp[ii]
            if (self._point_is_on_arc(rp, center, p1, p2, p3) and
                geometry.intersection_is_on_ray(rp, ray) and
                geometry.distance_squared(ray.p1, rp) > min_seg_len_sq):

                dist_sq = geometry.distance_squared(ray.p1, rp)
                if dist_sq < result['distance_sq']:
                    result['point'] = rp
                    result['distance_sq'] = dist_sq

                    # Determine normal direction based on ray direction relative to arc
                    other_ii = 2 if ii == 1 else 1
                    rp_other = rp_temp[other_ii]
                    dist_sq_other = geometry.distance_squared(ray.p1, rp_other)

                    if (geometry.intersection_is_on_ray(rp_other, ray) and
                        dist_sq < dist_sq_other):
                        # From outside to inside
                        result['normal_x'] = rp.x - center.x
                        result['normal_y'] = rp.y - center.y
                    else:
                        # From inside to outside
                        result['normal_x'] = center.x - rp.x
                        result['normal_y'] = center.y - rp.y

                    # Check if near edge
                    if (geometry.distance_squared(rp, p1) < min_seg_len_sq or
                        geometry.distance_squared(rp, p2) < min_seg_len_sq):
                        result['near_edge'] = True

            # Check test ray
            rp2 = rp2_temp[ii]
            if (self._point_is_on_arc(rp2, center, p1, p2, p3) and
                geometry.intersection_is_on_ray(rp2, ray2) and
                geometry.distance_squared(ray2.p1, rp2) > min_seg_len_sq):
                result['ray2_intersect_count'] += 1


# Example usage and testing
if __name__ == "__main__":
    print("Testing Glass class...\n")

    # Mock scene
    class MockScene:
        def __init__(self):
            self.error = None
            self.simulate_colors = False
            self.length_scale = 1.0
            self._rng_counter = 0

        def rng(self):
            """Simple random number generator for testing."""
            self._rng_counter += 1
            return (self._rng_counter * 0.123456789) % 1.0

    # Test 1: Create a simple triangular prism
    print("Test 1: Triangular prism")
    scene = MockScene()
    prism = Glass(scene, {
        'path': [
            {'x': 0, 'y': 0, 'arc': False},
            {'x': 100, 'y': 0, 'arc': False},
            {'x': 50, 'y': 86.6, 'arc': False}  # Equilateral triangle
        ],
        'not_done': False,
        'ref_index': 1.5,
        'cauchy_b': 0.004
    })

    print(f"  Number of points: {len(prism.path)}")
    print(f"  Refractive index: {prism.ref_index}")
    print(f"  Construction complete: {not prism.not_done}")

    center = prism.get_default_center()
    print(f"  Geometric center: ({center['x']:.1f}, {center['y']:.1f})")

    # Test 2: Transformations
    print("\nTest 2: Transformations")
    prism_test = Glass(scene, {
        'path': [
            {'x': 0, 'y': 0, 'arc': False},
            {'x': 10, 'y': 0, 'arc': False},
            {'x': 10, 'y': 10, 'arc': False},
            {'x': 0, 'y': 10, 'arc': False}
        ],
        'not_done': False,
        'ref_index': 1.5
    })

    print(f"  Initial path:")
    for i, p in enumerate(prism_test.path):
        print(f"    Point {i}: ({p['x']}, {p['y']})")

    # Move
    prism_test.move(5, 5)
    print(f"  After move(5, 5):")
    for i, p in enumerate(prism_test.path):
        print(f"    Point {i}: ({p['x']}, {p['y']})")

    # Test 3: Ray intersection with simple rectangle
    print("\nTest 3: Ray intersection")
    rect_glass = Glass(scene, {
        'path': [
            {'x': 10, 'y': 10, 'arc': False},
            {'x': 20, 'y': 10, 'arc': False},
            {'x': 20, 'y': 20, 'arc': False},
            {'x': 10, 'y': 20, 'arc': False}
        ],
        'not_done': False,
        'ref_index': 1.5
    })

    # Create a mock ray
    class MockRay:
        def __init__(self, p1, p2):
            self.p1 = geometry.point(p1['x'], p1['y'])
            self.p2 = geometry.point(p2['x'], p2['y'])

    ray = MockRay({'x': 0, 'y': 15}, {'x': 30, 'y': 15})
    intersection = rect_glass.check_ray_intersects(ray)

    if intersection:
        print(f"  Ray intersects at: ({intersection.x:.2f}, {intersection.y:.2f})")
    else:
        print(f"  No intersection found")

    # Test 4: Scale
    print("\nTest 4: Scale transformation")
    prism_scale = Glass(scene, {
        'path': [
            {'x': 0, 'y': 0, 'arc': False},
            {'x': 10, 'y': 0, 'arc': False},
            {'x': 5, 'y': 10, 'arc': False}
        ],
        'not_done': False
    })

    print(f"  Before scale:")
    for i, p in enumerate(prism_scale.path):
        print(f"    Point {i}: ({p['x']}, {p['y']})")

    prism_scale.scale(2.0)
    print(f"  After scale(2.0):")
    for i, p in enumerate(prism_scale.path):
        print(f"    Point {i}: ({p['x']:.1f}, {p['y']:.1f})")

    # Test 5: Rotate
    print("\nTest 5: Rotation transformation")
    prism_rotate = Glass(scene, {
        'path': [
            {'x': 10, 'y': 0, 'arc': False},
            {'x': 20, 'y': 0, 'arc': False},
            {'x': 15, 'y': 10, 'arc': False}
        ],
        'not_done': False
    })

    center_before = prism_rotate.get_default_center()
    print(f"  Center before: ({center_before['x']:.1f}, {center_before['y']:.1f})")

    prism_rotate.rotate(math.pi / 2)  # 90 degrees
    print(f"  After 90° rotation:")
    for i, p in enumerate(prism_rotate.path):
        print(f"    Point {i}: ({p['x']:.1f}, {p['y']:.1f})")

    center_after = prism_rotate.get_default_center()
    print(f"  Center after: ({center_after['x']:.1f}, {center_after['y']:.1f})")
    print(f"  Center preserved: {abs(center_before['x'] - center_after['x']) < 0.1 and abs(center_before['y'] - center_after['y']) < 0.1}")

    print("\nGlass test completed successfully!")
