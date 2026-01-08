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
