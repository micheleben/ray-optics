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


# Example usage and testing
if __name__ == "__main__":
    import math

    print("Testing Ray class...\n")

    # Test 1: Create a basic white light ray
    print("Test 1: Basic ray creation")
    ray1 = Ray(
        p1={'x': 0, 'y': 0},
        p2={'x': 100, 'y': 0},
        brightness_s=0.5,
        brightness_p=0.5
    )
    print(f"  {ray1}")
    print(f"  Total brightness: {ray1.total_brightness}")
    print(f"  Is new: {ray1.is_new}")
    print(f"  Is gap: {ray1.gap}")

    # Test 2: Create a colored ray (red light at 650nm)
    print("\nTest 2: Colored ray (red light)")
    ray2 = Ray(
        p1={'x': 0, 'y': 100},
        p2={'x': 100, 'y': 150},
        brightness_s=1.0,
        brightness_p=0.0,
        wavelength=650
    )
    print(f"  {ray2}")
    print(f"  Wavelength: {ray2.wavelength} nm")
    print(f"  S-polarization only: brightness_s={ray2.brightness_s}, brightness_p={ray2.brightness_p}")

    # Test 3: Ray copy
    print("\nTest 3: Ray copy")
    ray3 = ray1.copy()
    print(f"  Original: {ray1}")
    print(f"  Copy: {ray3}")
    print(f"  Are they the same object? {ray1 is ray3}")
    print(f"  Do they have the same values? p1={ray1.p1 == ray3.p1}, brightness={ray1.total_brightness == ray3.total_brightness}")

    # Modify copy and verify original is unchanged
    ray3.brightness_s = 0.1
    ray3.p1['x'] = 50
    print(f"  After modifying copy:")
    print(f"    Original brightness: {ray1.total_brightness}")
    print(f"    Copy brightness: {ray3.total_brightness}")
    print(f"    Original p1.x: {ray1.p1['x']}")
    print(f"    Copy p1.x: {ray3.p1['x']}")

    # Test 4: Ray with gap flag
    print("\nTest 4: Gap ray (not drawn)")
    ray4 = Ray(
        p1={'x': 100, 'y': 100},
        p2={'x': 200, 'y': 100}
    )
    ray4.gap = True
    print(f"  {ray4}")
    print(f"  Gap flag: {ray4.gap}")

    # Test 5: Calculate ray length
    print("\nTest 5: Ray length calculation")
    dx = ray1.p2['x'] - ray1.p1['x']
    dy = ray1.p2['y'] - ray1.p1['y']
    length = math.sqrt(dx*dx + dy*dy)
    print(f"  Ray: ({ray1.p1['x']}, {ray1.p1['y']}) -> ({ray1.p2['x']}, {ray1.p2['y']})")
    print(f"  Length: {length:.2f}")

    # Test 6: Different polarization states
    print("\nTest 6: Polarization states")
    rays = [
        Ray(p1={'x': 0, 'y': 0}, p2={'x': 1, 'y': 0}, brightness_s=1.0, brightness_p=0.0),  # S-polarized
        Ray(p1={'x': 0, 'y': 0}, p2={'x': 1, 'y': 0}, brightness_s=0.0, brightness_p=1.0),  # P-polarized
        Ray(p1={'x': 0, 'y': 0}, p2={'x': 1, 'y': 0}, brightness_s=0.5, brightness_p=0.5),  # Unpolarized
        Ray(p1={'x': 0, 'y': 0}, p2={'x': 1, 'y': 0}, brightness_s=0.0, brightness_p=0.0),  # Absorbed
    ]

    for i, ray in enumerate(rays):
        print(f"  Ray {i+1}: s={ray.brightness_s:.1f}, p={ray.brightness_p:.1f}, total={ray.total_brightness:.1f}")

    print("\nRay test completed successfully!")
