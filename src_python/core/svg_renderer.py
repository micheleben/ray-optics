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

import svgwrite
import math


class SVGRenderer:
    """
    SVG renderer for ray optics simulation.

    This class creates descriptive SVG output with metadata attributes
    that describe the simulation elements. The SVG is organized into
    three layers (matching the JavaScript implementation):
    - objects: Optical elements (below rays)
    - rays: Light rays
    - labels: Text annotations (above everything)

    The SVG includes data attributes on elements for post-processing
    and analysis.

    Attributes:
        width (int): Canvas width in pixels
        height (int): Canvas height in pixels
        viewbox (tuple or None): SVG viewBox (min_x, min_y, width, height)
        dwg (svgwrite.Drawing): The SVG drawing object
        layer_objects (svgwrite.Group): Group for object elements
        layer_rays (svgwrite.Group): Group for ray elements
        layer_labels (svgwrite.Group): Group for label elements
    """

    def __init__(self, width=800, height=600, viewbox=None):
        """
        Initialize the SVG renderer.

        Args:
            width (int): Canvas width in pixels (default: 800)
            height (int): Canvas height in pixels (default: 600)
            viewbox (tuple or None): SVG viewBox as (min_x, min_y, width, height)
                                    If None, uses (0, 0, width, height)
        """
        self.width = width
        self.height = height
        self.viewbox = viewbox if viewbox is not None else (0, 0, width, height)

        # Create SVG drawing with profile='tiny' to disable strict validation
        # This allows custom data-* attributes
        self.dwg = svgwrite.Drawing(size=(f'{width}px', f'{height}px'), profile='tiny')
        self.dwg.viewbox(*self.viewbox)

        # Add white background
        self.dwg.add(self.dwg.rect(
            insert=(self.viewbox[0], self.viewbox[1]),
            size=(self.viewbox[2], self.viewbox[3]),
            fill='white'
        ))

        # Create layers as groups (bottom to top)
        self.layer_objects = self.dwg.add(self.dwg.g(id='objects'))
        self.layer_rays = self.dwg.add(self.dwg.g(id='rays'))
        self.layer_labels = self.dwg.add(self.dwg.g(id='labels'))

    def draw_ray_segment(self, ray, color='red', opacity=1.0, stroke_width=1.5, extend_to_edge=False):
        """
        Draw a ray segment.

        Args:
            ray (Ray): The ray segment to draw
            color (str): CSS color string (default: 'red')
            opacity (float): Opacity 0.0-1.0 (default: 1.0)
            stroke_width (float): Line width in pixels (default: 1.5)
            extend_to_edge (bool): If True, extend ray to viewport edge (default: False)
        """
        import math

        p1 = ray.p1
        p2 = ray.p2

        # Skip rays with invalid coordinates
        if (math.isnan(p1['x']) or math.isnan(p1['y']) or
            math.isnan(p2['x']) or math.isnan(p2['y']) or
            math.isinf(p1['x']) or math.isinf(p1['y']) or
            math.isinf(p2['x']) or math.isinf(p2['y'])):
            return

        if extend_to_edge:
            # Extend the ray to the edge of the viewbox
            p2 = self._extend_to_edge(p1, p2)

        # Create line element with id containing metadata
        # (data-* attributes are not supported in svgwrite tiny profile)
        ray_id = f'ray-b{ray.total_brightness:.3f}'
        if ray.wavelength is not None:
            ray_id += f'-w{ray.wavelength:.0f}'

        line = self.dwg.line(
            start=(p1['x'], p1['y']),
            end=(p2['x'], p2['y']),
            stroke=color,
            stroke_width=stroke_width,
            stroke_opacity=opacity,
            id=ray_id
        )

        # Don't draw if it's a gap
        if not ray.gap:
            self.layer_rays.add(line)

    def draw_point(self, point, color='black', radius=3, label=None):
        """
        Draw a point (circle).

        Args:
            point (dict): Point with 'x' and 'y' keys
            color (str): Fill color (default: 'black')
            radius (float): Circle radius in pixels (default: 3)
            label (str or None): Optional text label to show near point
        """
        circle = self.dwg.circle(
            center=(point['x'], point['y']),
            r=radius,
            fill=color
        )
        self.layer_objects.add(circle)

        if label:
            text = self.dwg.text(
                label,
                insert=(point['x'] + radius + 2, point['y'] - radius - 2),
                fill=color,
                font_size='12px',
                font_family='sans-serif'
            )
            self.layer_labels.add(text)

    def draw_line_segment(self, p1, p2, color='gray', stroke_width=2, label=None):
        """
        Draw a line segment (for optical elements like lenses, mirrors).

        Args:
            p1 (dict): Start point with 'x' and 'y' keys
            p2 (dict): End point with 'x' and 'y' keys
            color (str): Stroke color (default: 'gray')
            stroke_width (float): Line width in pixels (default: 2)
            label (str or None): Optional text label
        """
        line = self.dwg.line(
            start=(p1['x'], p1['y']),
            end=(p2['x'], p2['y']),
            stroke=color,
            stroke_width=stroke_width
        )
        self.layer_objects.add(line)

        if label:
            # Place label at midpoint
            mid_x = (p1['x'] + p2['x']) / 2
            mid_y = (p1['y'] + p2['y']) / 2
            text = self.dwg.text(
                label,
                insert=(mid_x, mid_y - 5),
                fill=color,
                font_size='12px',
                font_family='sans-serif',
                text_anchor='middle'
            )
            self.layer_labels.add(text)

    def draw_lens(self, p1, p2, focal_length, color='blue', label=None):
        """
        Draw an ideal lens with arrows indicating converging/diverging.

        Args:
            p1 (dict): First endpoint of lens
            p2 (dict): Second endpoint of lens
            focal_length (float): Focal length (positive=converging, negative=diverging)
            color (str): Color for lens (default: 'blue')
            label (str or None): Optional label
        """
        # Draw the main line
        self.draw_line_segment(p1, p2, color=color, stroke_width=3)

        # Calculate perpendicular direction
        dx = p2['x'] - p1['x']
        dy = p2['y'] - p1['y']
        length = math.sqrt(dx*dx + dy*dy)
        if length < 1e-6:
            return

        # Unit vectors parallel and perpendicular to lens
        par_x = dx / length
        par_y = dy / length
        per_x = par_y
        per_y = -par_x

        arrow_size = 10

        # Draw arrows at endpoints
        if focal_length > 0:
            # Converging lens - arrows point inward
            self._draw_arrow_inward(p1, par_x, par_y, per_x, per_y, arrow_size, color)
            self._draw_arrow_inward(p2, -par_x, -par_y, per_x, per_y, arrow_size, color)
        else:
            # Diverging lens - arrows point outward
            self._draw_arrow_outward(p1, par_x, par_y, per_x, per_y, arrow_size, color)
            self._draw_arrow_outward(p2, -par_x, -par_y, per_x, per_y, arrow_size, color)

        # Draw center mark
        mid_x = (p1['x'] + p2['x']) / 2
        mid_y = (p1['y'] + p2['y']) / 2
        center_size = 8
        center_line = self.dwg.line(
            start=(mid_x - per_x * center_size, mid_y - per_y * center_size),
            end=(mid_x + per_x * center_size, mid_y + per_y * center_size),
            stroke=color,
            stroke_width=2
        )
        self.layer_objects.add(center_line)

        if label:
            text = self.dwg.text(
                label,
                insert=(mid_x, mid_y - 15),
                fill=color,
                font_size='12px',
                font_family='sans-serif',
                text_anchor='middle'
            )
            self.layer_labels.add(text)

    def _draw_arrow_inward(self, pos, par_x, par_y, per_x, per_y, size, color):
        """Draw an arrow pointing inward (for converging lens)."""
        points = [
            (pos['x'] - par_x * size, pos['y'] - par_y * size),
            (pos['x'] + par_x * size + per_x * size, pos['y'] + par_y * size + per_y * size),
            (pos['x'] + par_x * size - per_x * size, pos['y'] + par_y * size - per_y * size)
        ]
        polygon = self.dwg.polygon(points=points, fill=color)
        self.layer_objects.add(polygon)

    def _draw_arrow_outward(self, pos, par_x, par_y, per_x, per_y, size, color):
        """Draw an arrow pointing outward (for diverging lens)."""
        points = [
            (pos['x'] + par_x * size, pos['y'] + par_y * size),
            (pos['x'] - par_x * size + per_x * size, pos['y'] - par_y * size + per_y * size),
            (pos['x'] - par_x * size - per_x * size, pos['y'] - par_y * size - per_y * size)
        ]
        polygon = self.dwg.polygon(points=points, fill=color)
        self.layer_objects.add(polygon)

    def _extend_to_edge(self, p1, p2):
        """
        Extend a ray from p1 through p2 to the edge of the viewbox.

        Args:
            p1 (dict): Start point
            p2 (dict): Direction point

        Returns:
            dict: Point at the edge of viewbox
        """
        dx = p2['x'] - p1['x']
        dy = p2['y'] - p1['y']

        if abs(dx) < 1e-10 and abs(dy) < 1e-10:
            return p2

        # Find intersection with viewbox edges
        min_x, min_y, width, height = self.viewbox
        max_x = min_x + width
        max_y = min_y + height

        # Calculate t values for each edge
        t_values = []

        if abs(dx) > 1e-10:
            t_left = (min_x - p1['x']) / dx
            t_right = (max_x - p1['x']) / dx
            if t_left > 0:
                t_values.append(t_left)
            if t_right > 0:
                t_values.append(t_right)

        if abs(dy) > 1e-10:
            t_top = (min_y - p1['y']) / dy
            t_bottom = (max_y - p1['y']) / dy
            if t_top > 0:
                t_values.append(t_top)
            if t_bottom > 0:
                t_values.append(t_bottom)

        if not t_values:
            return p2

        t = max(t_values)
        return {'x': p1['x'] + dx * t, 'y': p1['y'] + dy * t}

    def save(self, filename):
        """
        Save the SVG to a file.

        Args:
            filename (str): Output filename (e.g., 'output.svg')
        """
        self.dwg.saveas(filename)

    def to_string(self):
        """
        Get the SVG as a string.

        Returns:
            str: SVG content as XML string
        """
        return self.dwg.tostring()


# Example usage and testing
if __name__ == "__main__":
    import os
    import tempfile

    print("Testing SVGRenderer class...\n")

    # Test 1: Basic renderer creation
    print("Test 1: Create basic renderer")
    renderer = SVGRenderer(width=400, height=300)
    print(f"  Canvas size: {renderer.width}x{renderer.height}")
    print(f"  Viewbox: {renderer.viewbox}")
    print(f"  Layers created: objects, rays, labels")

    # Test 2: Custom viewbox
    print("\nTest 2: Custom viewbox")
    renderer2 = SVGRenderer(width=800, height=600, viewbox=(-100, -100, 400, 400))
    print(f"  Canvas size: {renderer2.width}x{renderer2.height}")
    print(f"  Custom viewbox: {renderer2.viewbox}")

    # Test 3: Draw points
    print("\nTest 3: Draw points")
    renderer.draw_point({'x': 50, 'y': 50}, color='red', radius=5, label='Point A')
    renderer.draw_point({'x': 150, 'y': 100}, color='blue', radius=3, label='Point B')
    renderer.draw_point({'x': 250, 'y': 150}, color='green', radius=4)
    print("  Drew 3 points: red (labeled), blue (labeled), green (unlabeled)")

    # Test 4: Draw line segments
    print("\nTest 4: Draw line segments")
    renderer.draw_line_segment(
        {'x': 50, 'y': 200},
        {'x': 250, 'y': 200},
        color='black',
        stroke_width=2,
        label='Screen'
    )
    renderer.draw_line_segment(
        {'x': 150, 'y': 50},
        {'x': 150, 'y': 250},
        color='gray',
        stroke_width=1
    )
    print("  Drew 2 line segments: black (labeled), gray (unlabeled)")

    # Test 5: Draw lenses
    print("\nTest 5: Draw lenses")
    # Converging lens
    renderer.draw_lens(
        {'x': 100, 'y': 50},
        {'x': 100, 'y': 150},
        focal_length=50,
        color='blue',
        label='Converging'
    )
    # Diverging lens
    renderer.draw_lens(
        {'x': 200, 'y': 50},
        {'x': 200, 'y': 150},
        focal_length=-50,
        color='purple',
        label='Diverging'
    )
    print("  Drew converging lens (f=50) and diverging lens (f=-50)")

    # Test 6: Draw ray segments
    print("\nTest 6: Draw ray segments")
    # Mock Ray class for testing
    class MockRay:
        def __init__(self, p1, p2, brightness_s=1.0, brightness_p=0.0, wavelength=None, gap=False):
            self.p1 = p1
            self.p2 = p2
            self.brightness_s = brightness_s
            self.brightness_p = brightness_p
            self.wavelength = wavelength
            self.gap = gap
            self.total_brightness = brightness_s + brightness_p

    # Normal ray
    ray1 = MockRay({'x': 10, 'y': 100}, {'x': 90, 'y': 100})
    renderer.draw_ray_segment(ray1, color='red', opacity=1.0, stroke_width=2)

    # Ray with wavelength
    ray2 = MockRay({'x': 10, 'y': 120}, {'x': 90, 'y': 120}, wavelength=650)
    renderer.draw_ray_segment(ray2, color='red', opacity=0.8, stroke_width=2)

    # Faint ray
    ray3 = MockRay({'x': 10, 'y': 140}, {'x': 90, 'y': 140}, brightness_s=0.3, brightness_p=0.2)
    renderer.draw_ray_segment(ray3, color='red', opacity=0.5, stroke_width=1)

    # Gap ray (should not be drawn)
    ray4 = MockRay({'x': 10, 'y': 160}, {'x': 90, 'y': 160}, gap=True)
    renderer.draw_ray_segment(ray4, color='red', opacity=1.0, stroke_width=2)

    print("  Drew 4 rays: normal, wavelength-specific, faint, gap (gap not drawn)")

    # Test 7: Invalid ray handling (NaN, Inf)
    print("\nTest 7: Invalid ray handling")
    ray_nan = MockRay({'x': float('nan'), 'y': 100}, {'x': 90, 'y': 100})
    ray_inf = MockRay({'x': 10, 'y': float('inf')}, {'x': 90, 'y': 100})
    renderer.draw_ray_segment(ray_nan, color='red')
    renderer.draw_ray_segment(ray_inf, color='red')
    print("  Attempted to draw NaN and Inf rays (skipped automatically)")

    # Test 8: Save to file
    print("\nTest 8: Save SVG to file")
    temp_dir = tempfile.gettempdir()
    output_file = os.path.join(temp_dir, 'test_renderer_output.svg')
    renderer.save(output_file)
    file_exists = os.path.exists(output_file)
    file_size = os.path.getsize(output_file) if file_exists else 0
    print(f"  Saved to: {output_file}")
    print(f"  File exists: {file_exists}")
    print(f"  File size: {file_size} bytes")

    # Test 9: SVG as string
    print("\nTest 9: Get SVG as string")
    svg_string = renderer.to_string()
    print(f"  SVG string length: {len(svg_string)} characters")
    objects_present = 'id="objects"' in svg_string
    rays_present = 'id="rays"' in svg_string
    labels_present = 'id="labels"' in svg_string
    print(f"  Contains 'objects' layer: {objects_present}")
    print(f"  Contains 'rays' layer: {rays_present}")
    print(f"  Contains 'labels' layer: {labels_present}")

    # Test 10: Complete example scene
    print("\nTest 10: Create a complete example scene")
    scene_renderer = SVGRenderer(width=600, height=400, viewbox=(0, 0, 300, 200))

    # Add a point source
    scene_renderer.draw_point({'x': 50, 'y': 100}, color='orange', radius=6, label='Source')

    # Add a lens
    scene_renderer.draw_lens(
        {'x': 150, 'y': 50},
        {'x': 150, 'y': 150},
        focal_length=50,
        color='blue',
        label='Lens (f=50)'
    )

    # Add a screen
    scene_renderer.draw_line_segment(
        {'x': 250, 'y': 30},
        {'x': 250, 'y': 170},
        color='black',
        stroke_width=3,
        label='Screen'
    )

    # Add some rays
    rays = [
        MockRay({'x': 50, 'y': 100}, {'x': 150, 'y': 80}),
        MockRay({'x': 150, 'y': 80}, {'x': 250, 'y': 100}),
        MockRay({'x': 50, 'y': 100}, {'x': 150, 'y': 100}),
        MockRay({'x': 150, 'y': 100}, {'x': 250, 'y': 100}),
        MockRay({'x': 50, 'y': 100}, {'x': 150, 'y': 120}),
        MockRay({'x': 150, 'y': 120}, {'x': 250, 'y': 100}),
    ]

    for ray in rays:
        scene_renderer.draw_ray_segment(ray, color='red', opacity=0.7, stroke_width=1.5)

    scene_output = os.path.join(temp_dir, 'test_complete_scene.svg')
    scene_renderer.save(scene_output)
    print(f"  Complete scene saved to: {scene_output}")
    print(f"  Scene contains: 1 source, 1 lens, 1 screen, {len(rays)} rays")

    print("\nSVGRenderer test completed successfully!")
    print(f"\nTest files created in: {temp_dir}")
    print(f"  - test_renderer_output.svg")
    print(f"  - test_complete_scene.svg")
