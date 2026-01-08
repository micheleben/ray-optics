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


class Scene:
    """
    Container for scene objects and simulation settings.

    This class manages all objects in the simulation and provides
    scene-level configuration parameters like ray density, color mode,
    and length scale.

    Attributes:
        objs (list): All objects in the scene
        optical_objs (list): Only optical objects (those with is_optical=True)
        ray_density (float): Angular density of rays (radians between rays)
        color_mode (str): Color rendering mode ('default', 'wavelength', etc.)
        mode (str): Simulation mode ('rays', 'extended_rays', 'images', etc.)
        length_scale (float): Scale factor for all lengths in the scene
        simulate_colors (bool): Whether to simulate wavelength-dependent behavior
        error (str or None): Error message if simulation encountered an error
        warning (str or None): Warning message if simulation has warnings
    """

    def __init__(self):
        """Initialize an empty scene with default settings."""
        self.objs = []
        self.optical_objs = []
        self.ray_density = 0.1  # radians between rays
        self.color_mode = 'default'
        self.mode = 'rays'
        self.length_scale = 1.0
        self.simulate_colors = False
        self.error = None
        self.warning = None

    def add_object(self, obj):
        """
        Add an object to the scene.

        Automatically adds optical objects (those with is_optical=True)
        to the optical_objs list for efficient simulation.

        Args:
            obj: The scene object to add
        """
        self.objs.append(obj)
        if hasattr(obj, 'is_optical') and obj.is_optical:
            self.optical_objs.append(obj)

    def remove_object(self, obj):
        """
        Remove an object from the scene.

        Args:
            obj: The scene object to remove
        """
        if obj in self.objs:
            self.objs.remove(obj)
        if obj in self.optical_objs:
            self.optical_objs.remove(obj)

    def clear(self):
        """Remove all objects from the scene."""
        self.objs.clear()
        self.optical_objs.clear()
        self.error = None
        self.warning = None


# Example usage and testing
if __name__ == "__main__":
    print("Testing Scene class...\n")

    # Mock optical object
    class MockLightSource:
        def __init__(self, name):
            self.name = name
            self.is_optical = True

        def __repr__(self):
            return f"MockLightSource({self.name})"

    # Mock non-optical object (e.g., annotation)
    class MockAnnotation:
        def __init__(self, text):
            self.text = text
            self.is_optical = False

        def __repr__(self):
            return f"MockAnnotation({self.text})"

    # Mock object without is_optical attribute (treated as non-optical)
    class MockDecorator:
        def __init__(self, label):
            self.label = label

        def __repr__(self):
            return f"MockDecorator({self.label})"

    # Test 1: Create empty scene
    print("Test 1: Create empty scene")
    scene = Scene()
    print(f"  Objects: {len(scene.objs)}")
    print(f"  Optical objects: {len(scene.optical_objs)}")
    print(f"  Ray density: {scene.ray_density}")
    print(f"  Color mode: {scene.color_mode}")
    print(f"  Mode: {scene.mode}")
    print(f"  Length scale: {scene.length_scale}")
    print(f"  Simulate colors: {scene.simulate_colors}")

    # Test 2: Add optical objects
    print("\nTest 2: Add optical objects")
    source1 = MockLightSource("Source1")
    source2 = MockLightSource("Source2")
    scene.add_object(source1)
    scene.add_object(source2)
    print(f"  Added: {source1}, {source2}")
    print(f"  Total objects: {len(scene.objs)}")
    print(f"  Optical objects: {len(scene.optical_objs)}")
    print(f"  Optical objects list: {scene.optical_objs}")

    # Test 3: Add non-optical objects
    print("\nTest 3: Add non-optical objects")
    annotation = MockAnnotation("Note")
    decorator = MockDecorator("Grid")
    scene.add_object(annotation)
    scene.add_object(decorator)
    print(f"  Added: {annotation}, {decorator}")
    print(f"  Total objects: {len(scene.objs)}")
    print(f"  Optical objects: {len(scene.optical_objs)} (should not include non-optical)")
    print(f"  All objects: {scene.objs}")

    # Test 4: Remove objects
    print("\nTest 4: Remove objects")
    scene.remove_object(source1)
    print(f"  Removed: {source1}")
    print(f"  Total objects: {len(scene.objs)}")
    print(f"  Optical objects: {len(scene.optical_objs)}")
    print(f"  Remaining objects: {scene.objs}")

    # Test 5: Scene settings
    print("\nTest 5: Modify scene settings")
    scene.ray_density = 0.05
    scene.simulate_colors = True
    scene.color_mode = 'wavelength'
    scene.length_scale = 10.0
    print(f"  Ray density: {scene.ray_density} (more rays)")
    print(f"  Simulate colors: {scene.simulate_colors}")
    print(f"  Color mode: {scene.color_mode}")
    print(f"  Length scale: {scene.length_scale}")

    # Test 6: Error and warning messages
    print("\nTest 6: Error and warning messages")
    scene.warning = "Ray count limit reached"
    scene.error = None
    print(f"  Warning: {scene.warning}")
    print(f"  Error: {scene.error}")

    # Test 7: Clear scene
    print("\nTest 7: Clear scene")
    print(f"  Before clear - objects: {len(scene.objs)}, optical: {len(scene.optical_objs)}")
    scene.clear()
    print(f"  After clear - objects: {len(scene.objs)}, optical: {len(scene.optical_objs)}")
    print(f"  Warning cleared: {scene.warning}")
    print(f"  Error cleared: {scene.error}")

    # Test 8: Build a simple scene
    print("\nTest 8: Build a simple optical scene")
    scene2 = Scene()
    scene2.ray_density = 0.2
    scene2.simulate_colors = False

    # Add multiple optical objects
    for i in range(3):
        scene2.add_object(MockLightSource(f"Source{i+1}"))

    # Add a non-optical annotation
    scene2.add_object(MockAnnotation("Experiment Setup"))

    print(f"  Scene configuration:")
    print(f"    Total objects: {len(scene2.objs)}")
    print(f"    Optical objects: {len(scene2.optical_objs)}")
    print(f"    Ray density: {scene2.ray_density} radians")
    print(f"    Objects: {scene2.objs}")

    # Test 9: Remove non-existent object (should not raise error)
    print("\nTest 9: Remove non-existent object")
    fake_obj = MockLightSource("NonExistent")
    scene2.remove_object(fake_obj)
    print(f"  Attempted to remove non-existent object: {fake_obj}")
    print(f"  Total objects (unchanged): {len(scene2.objs)}")

    print("\nScene test completed successfully!")
