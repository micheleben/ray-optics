### Simulator Implementation Plan
#### Phase 1: Core Infrastructure (Start Here!)
##### Step 1a: Scene Class
File: src_python/core/scene.py Why first? Every object needs a scene reference, and the simulator operates on a scene. What it needs:
```
class Scene:

    def __init__(self):
        self.objs = []              # All objects (optical + decorative)
        self.optical_objs = []      # Only optical objects
        self.ray_density = 0.1      # Default ray density
        self.color_mode = 'default' # 'default', 'waves', etc.
        self.mode = 'rays'          # 'rays', 'extended', 'observer'
        self.length_scale = 1.0     # Coordinate scale
        # Settings for compatibility with existing objects
        self.simulate_colors = False
        self.error = None
        self.warning = None
    
    def add_object(self, obj):
        """Add object to scene."""
        self.objs.append(obj)
        if hasattr(obj, 'is_optical') and obj.is_optical:
            self.optical_objs.append(obj)
```
Estimated effort: ~50 lines, 30 minutes
##### Step 1b: Simple Ray Class
File: src_python/core/ray.py (NEW) Why? We need a consistent ray representation for the simulator.
```
class Ray:
    """
    Represents a light ray in the simulation.
    
    Implemented as a simple object with dict-like attribute access
    for compatibility with existing object code.
    """
    def __init__(self, p1, p2, brightness_s=1.0, brightness_p=1.0, wavelength=None):
        self.p1 = p1  # Starting point (dict or Point)
        self.p2 = p2  # Direction point (dict or Point)
        self.brightness_s = brightness_s
        self.brightness_p = brightness_p
        self.wavelength = wavelength
        self.gap = False       # True if discontinuous from previous
        self.is_new = True     # True if just emitted
        self.body_merging_obj = None  # For GRIN glass
```
Estimated effort: ~30 lines, 15 minutes

#### Phase 2: Minimal Simulator (Core Ray Tracing)
Step 2: Simulator Class (Simplified Version)
- SKIP surface merging in Phase 2. Why:
    * Not needed for our collimation demo
    * Adds complexity without immediate benefit
    * Can be added cleanly later when needed
    * Won't block progress
- When to add it:
    * Phase 2.5 (after basic simulator works)
    * Or when implementing first glass object
Estimate: +2 hours of work later
File: src_python/core/simulator.py Start with minimal version - just the ray tracing loop:
```
class Simulator:
    """Minimal ray optics simulator."""
    
    MIN_RAY_SEGMENT_LENGTH = 1e-6
    
    def __init__(self, scene, max_rays=10000):
        self.scene = scene
        self.max_rays = max_rays
        self.pending_rays = []
        self.processed_ray_count = 0
        self.ray_segments = []  # Store for visualization
        
    def run(self):
        """Run the simulation."""
        # Step 1: Initialize - call on_simulation_start()
        for obj in self.scene.optical_objs:
            result = obj.on_simulation_start()
            if result and 'newRays' in result:
                self.pending_rays.extend(result['newRays'])
        
        # Step 2: Process rays
        self._process_rays()
        
        return {
            'ray_segments': self.ray_segments,
            'processed_ray_count': self.processed_ray_count
        }
    
    def _process_rays(self):
        """Main ray tracing loop (simplified).

        NOTE: This simplified version does NOT handle surface merging
        (when rays hit two objects at the same point). This is fine for
        IdealLens and Blocker, but will need to be added when implementing
        glass objects with refraction. See JavaScript Simulator.js lines 596-655
        for reference implementation
        """
        pending_index = -1
        
        while True:
            # Termination checks
            if self.processed_ray_count > self.max_rays:
                break
            
            pending_index += 1
            if pending_index >= len(self.pending_rays):
                break
            
            ray = self.pending_rays[pending_index]
            if not ray:
                continue
            
            # Find nearest intersection
            nearest_obj = None
            nearest_point = None
            nearest_dist_sq = float('inf')
            
            for obj in self.scene.optical_objs:
                intersection = obj.check_ray_intersects(ray)
                if intersection:
                    dist_sq = self._distance_squared(ray.p1, intersection)
                    if dist_sq < nearest_dist_sq and dist_sq > self.MIN_RAY_SEGMENT_LENGTH**2:
                        nearest_obj = obj
                        nearest_point = intersection
                        nearest_dist_sq = dist_sq
            
            # Handle intersection
            if nearest_obj:
                # Store ray segment for visualization
                self.ray_segments.append({
                    'p1': ray.p1,
                    'p2': nearest_point,
                    'brightness_s': ray.brightness_s,
                    'brightness_p': ray.brightness_p,
                    'wavelength': ray.wavelength
                })
                
                # Call object's handler
                result = nearest_obj.on_ray_incident(ray, pending_index, nearest_point)
                
                # Handle result
                if result:
                    if 'newRays' in result:
                        self.pending_rays.extend(result['newRays'])
                    if not result.get('isAbsorbed', False):
                        # Ray continues - add to pending
                        self.pending_rays.append(ray)
            else:
                # Ray hits nothing - draw to infinity
                self.ray_segments.append({
                    'p1': ray.p1,
                    'p2': ray.p2,
                    'brightness_s': ray.brightness_s,
                    'brightness_p': ray.brightness_p,
                    'wavelength': ray.wavelength,
                    'infinite': True
                })
            
            self.processed_ray_count += 1
    
    def _distance_squared(self, p1, p2):
        """Calculate squared distance between two points."""
        if isinstance(p1, dict):
            dx = p1['x'] - p2['x'] if isinstance(p2, dict) else p1['x'] - p2.x
            dy = p1['y'] - p2['y'] if isinstance(p2, dict) else p1['y'] - p2.y
        else:
            dx = p1.x - (p2['x'] if isinstance(p2, dict) else p2.x)
            dy = p1.y - (p2['y'] if isinstance(p2, dict) else p2.y)
        return dx**2 + dy**2
```
Estimated effort: ~150 lines, 2 hours
#### Phase 3: SVG Renderer
Step 3: SVG Renderer
File: src_python/core/svg_renderer.py Why SVG? we want descriptive, version-controllable output.
```
import svgwrite
from typing import List, Dict, Any

class SVGRenderer:
    """Render simulation results to SVG."""
    
    def __init__(self, width=800, height=600, viewbox=None):
        self.dwg = svgwrite.Drawing(size=(width, height))
        if viewbox:
            self.dwg.viewbox(*viewbox)
        
        # Create layers as groups
        self.layer_objects = self.dwg.add(self.dwg.g(id='objects'))
        self.layer_rays = self.dwg.add(self.dwg.g(id='rays'))
        self.layer_labels = self.dwg.add(self.dwg.g(id='labels'))
    
    def draw_ray_segment(self, p1, p2, brightness=1.0, wavelength=None, infinite=False):
        """Draw a ray segment."""
        # Convert points to coordinates
        x1, y1 = self._point_to_coords(p1)
        x2, y2 = self._point_to_coords(p2)
        
        # Determine color
        if wavelength:
            color = self._wavelength_to_rgb(wavelength)
        else:
            # Default red
            color = 'rgb(255,0,0)'
        
        # Calculate opacity from brightness
        opacity = min(brightness, 1.0)
        
        # Draw line
        line = self.dwg.line(
            start=(x1, y1),
            end=(x2, y2),
            stroke=color,
            stroke_width=1,
            stroke_opacity=opacity
        )
        
        if infinite:
            line['stroke-dasharray'] = '5,5'
        
        # Add metadata
        line['class'] = 'ray'
        line['data-brightness'] = str(brightness)
        if wavelength:
            line['data-wavelength'] = str(wavelength)
        
        self.layer_rays.add(line)
    
    def draw_lens(self, p1, p2, focal_length):
        """Draw an ideal lens."""
        x1, y1 = self._point_to_coords(p1)
        x2, y2 = self._point_to_coords(p2)
        
        line = self.dwg.line(
            start=(x1, y1),
            end=(x2, y2),
            stroke='blue',
            stroke_width=2
        )
        line['class'] = 'lens'
        line['data-focal-length'] = str(focal_length)
        self.layer_objects.add(line)
    
    def draw_blocker(self, p1, p2):
        """Draw a blocker."""
        x1, y1 = self._point_to_coords(p1)
        x2, y2 = self._point_to_coords(p2)
        
        line = self.dwg.line(
            start=(x1, y1),
            end=(x2, y2),
            stroke='black',
            stroke_width=3
        )
        line['class'] = 'blocker'
        self.layer_objects.add(line)
    
    def draw_point_source(self, x, y, brightness, wavelength=None):
        """Draw a point source."""
        cx, cy = self._point_to_coords({'x': x, 'y': y})
        
        if wavelength:
            color = self._wavelength_to_rgb(wavelength)
        else:
            color = 'yellow'
        
        circle = self.dwg.circle(
            center=(cx, cy),
            r=5,
            fill=color,
            stroke='orange',
            stroke_width=1
        )
        circle['class'] = 'source'
        circle['data-brightness'] = str(brightness)
        self.layer_objects.add(circle)
    
    def add_label(self, x, y, text):
        """Add text label."""
        cx, cy = self._point_to_coords({'x': x, 'y': y})
        text_elem = self.dwg.text(
            text,
            insert=(cx, cy),
            font_size='12px',
            font_family='Arial'
        )
        self.layer_labels.add(text_elem)
    
    def save(self, filename):
        """Save SVG to file."""
        self.dwg.saveas(filename)
    
    def _point_to_coords(self, point):
        """Convert point to SVG coordinates."""
        if isinstance(point, dict):
            return (point['x'], point['y'])
        else:
            return (point.x, point.y)
    
    def _wavelength_to_rgb(self, wavelength):
        """Convert wavelength (nm) to RGB color."""
        # Simplified wavelength to color conversion
        if wavelength < 450:
            return 'rgb(138,43,226)'  # Violet
        elif wavelength < 495:
            return 'rgb(0,0,255)'     # Blue
        elif wavelength < 570:
            return 'rgb(0,255,0)'     # Green
        elif wavelength < 590:
            return 'rgb(255,255,0)'   # Yellow
        elif wavelength < 620:
            return 'rgb(255,165,0)'   # Orange
        else:
            return 'rgb(255,0,0)'     # Red
```            
Estimated effort: ~200 lines, 2 hours Dependency: pip install svgwrite

#### Phase 4: Integration Example
Step 4: Collimation Demo
File: src_python/examples/collimation_demo.py
```
"""
Demonstration: Point source at focal point produces collimated beam.
"""

import sys
sys.path.insert(0, '../')

from core.scene import Scene
from core.simulator import Simulator
from core.svg_renderer import SVGRenderer
from core.scene_objs import PointSource, IdealLens, Blocker

### Create scene
scene = Scene()
scene.ray_density = 0.1

### Add point source at focal point
source = PointSource(scene, {
    'x': 0,
    'y': 0,
    'brightness': 0.5
})
scene.add_object(source)

### Add lens at x=100 with focal length 100
lens = IdealLens(scene, {
    'p1': {'x': 100, 'y': -100},
    'p2': {'x': 100, 'y': 100},
    'focalLength': 100
})
scene.add_object(lens)

### Add blocker/screen at x=300
blocker = Blocker(scene, {
    'p1': {'x': 300, 'y': -150},
    'p2': {'x': 300, 'y': 150}
})
scene.add_object(blocker)

### Run simulation
print("Running simulation...")
simulator = Simulator(scene, max_rays=10000)
result = simulator.run()

print(f"Processed {result['processed_ray_count']} rays")
print(f"Generated {len(result['ray_segments'])} ray segments")

### Render to SVG

print("Rendering to SVG...")
renderer = SVGRenderer(width=800, height=600, viewbox=(−50, −200, 400, 400))

### Draw objects

renderer.draw_point_source(source.x, source.y, source.brightness)
renderer.draw_lens(lens.p1, lens.p2, lens.focalLength)
renderer.draw_blocker(blocker.p1, blocker.p2)

### Draw rays

for segment in result['ray_segments']:
    renderer.draw_ray_segment(
        segment['p1'],
        segment['p2'],
        brightness=segment['brightness_s'] + segment['brightness_p'],
        wavelength=segment.get('wavelength'),
        infinite=segment.get('infinite', False)
    )

### Add labels
renderer.add_label(0, -20, 'Point Source')
renderer.add_label(100, -120, f'Lens (f={lens.focalLength})')
renderer.add_label(300, -170, 'Screen')

### Save
renderer.save('collimation_demo.svg')
print("Saved to collimation_demo.svg")
```
Estimated effort: ~80 lines, 1 hour
#### Phase 5: Testing
Step 5: Unit Tests for Simulator
File: src_python/tests/test_simulator.py
```
import unittest
from core.scene import Scene
from core.simulator import Simulator
from core.scene_objs import PointSource, Blocker

class TestSimulator(unittest.TestCase):
    
    def test_basic_simulation(self):
        """Test that simulation runs without errors."""
        scene = Scene()
        scene.ray_density = 0.1
        
        source = PointSource(scene, {'x': 0, 'y': 0, 'brightness': 0.5})
        scene.add_object(source)
        
        sim = Simulator(scene, max_rays=1000)
        result = sim.run()
        
        self.assertGreater(result['processed_ray_count'], 0)
        self.assertGreater(len(result['ray_segments']), 0)
    
    def test_ray_absorption(self):
        """Test that blocker absorbs rays."""
        scene = Scene()
        scene.ray_density = 0.1
        
        source = PointSource(scene, {'x': 0, 'y': 0, 'brightness': 0.5})
        blocker = Blocker(scene, {'p1': {'x': 50, 'y': -100}, 'p2': {'x': 50, 'y': 100}})
        
        scene.add_object(source)
        scene.add_object(blocker)
        
        sim = Simulator(scene, max_rays=1000)
        result = sim.run()
        
        # All rays should hit blocker and stop
        self.assertGreater(result['processed_ray_count'], 0)

if __name__ == '__main__':
    unittest.main()
```    
Estimated effort: ~100 lines, 1.5 hours

#### Summary: Implementation Order
Start: scene.py (30 min)
Then: ray.py (15 min)
Core: simulator.py - simplified version (2 hours)
Render: svg_renderer.py (2 hours)
Demo: collimation_demo.py (1 hour)
Test: test_simulator.py (1.5 hours)
Total estimated time: ~8 hours for MVP
#### Recommendation: Start with Step 1a - Scene Class
Why?
Smallest, simplest component
Required by everything else
Quick win to build momentum
Validates our approach

