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


class Ray:
    """
    Representation of a light ray for ray tracing simulation.

    A ray is defined by two points (p1 and p2) representing a line segment
    or infinite ray. The ray carries brightness information for both
    polarization states (s and p) and optionally wavelength information.

    Attributes:
        p1 (dict): Starting point with keys 'x' and 'y'
        p2 (dict): Direction point with keys 'x' and 'y'
        brightness_s (float): Brightness for s-polarization (0.0 to 1.0)
        brightness_p (float): Brightness for p-polarization (0.0 to 1.0)
        wavelength (float or None): Wavelength in nm, or None for white light
        gap (bool): If True, this ray segment is not drawn (gap in ray path)
        is_new (bool): If True, this ray has not been processed yet
        body_merging_obj (object or None): Object for surface merging (Phase 2.5)
    """

    def __init__(self, p1, p2, brightness_s=1.0, brightness_p=1.0, wavelength=None):
        """
        Initialize a ray.

        Args:
            p1 (dict): Starting point {'x': float, 'y': float}
            p2 (dict): Direction point {'x': float, 'y': float}
            brightness_s (float): S-polarization brightness (default: 1.0)
            brightness_p (float): P-polarization brightness (default: 1.0)
            wavelength (float or None): Wavelength in nm (default: None for white)
        """
        self.p1 = p1
        self.p2 = p2
        self.brightness_s = brightness_s
        self.brightness_p = brightness_p
        self.wavelength = wavelength
        self.gap = False
        self.is_new = True
        self.body_merging_obj = None  # Reserved for Phase 2.5 surface merging

    def copy(self):
        """
        Create a copy of this ray.

        Returns:
            Ray: A new Ray object with the same properties
        """
        new_ray = Ray(
            p1={'x': self.p1['x'], 'y': self.p1['y']},
            p2={'x': self.p2['x'], 'y': self.p2['y']},
            brightness_s=self.brightness_s,
            brightness_p=self.brightness_p,
            wavelength=self.wavelength
        )
        new_ray.gap = self.gap
        new_ray.is_new = self.is_new
        new_ray.body_merging_obj = self.body_merging_obj
        return new_ray

    @property
    def total_brightness(self):
        """
        Get the total brightness (sum of both polarizations).

        Returns:
            float: brightness_s + brightness_p
        """
        return self.brightness_s + self.brightness_p

    def __repr__(self):
        """String representation for debugging."""
        return (f"Ray(p1={self.p1}, p2={self.p2}, "
                f"brightness=({self.brightness_s:.3f}, {self.brightness_p:.3f}), "
                f"wavelength={self.wavelength})")
