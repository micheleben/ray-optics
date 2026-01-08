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
