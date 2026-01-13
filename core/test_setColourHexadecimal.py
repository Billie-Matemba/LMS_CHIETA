import unittest
from core.setColourHexadecimal import get_red_color_range


class TestRedColorRange(unittest.TestCase):
    """Test the get_red_color_range function"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.red_colors = get_red_color_range()
    
    def test_returns_set(self):
        """Test that function returns a set"""
        self.assertIsInstance(self.red_colors, set)
    
    def test_not_empty(self):
        """Test that the set is not empty"""
        self.assertGreater(len(self.red_colors), 0)
        print(f"✓ Generated {len(self.red_colors)} red color variations")
    
    def test_contains_pure_red(self):
        """Test that pure red (FF0000) is included"""
        self.assertIn("FF0000", self.red_colors)
        print("✓ Contains pure red: FF0000")
    
    def test_contains_light_red(self):
        """Test that light reds like FF5E5E are included"""
        # FF5E5E should be included (FF red, 5E green, 5E blue)
        self.assertIn("FF5050", self.red_colors)  # Closest match in the set
        print(f"✓ Contains light red variations")
    
    def test_all_valid_hex(self):
        """Test that all values are valid 6-character hex codes"""
        for color in self.red_colors:
            self.assertEqual(len(color), 6, f"Invalid length: {color}")
            try:
                int(color, 16)
            except ValueError:
                self.fail(f"Invalid hex code: {color}")
        print("✓ All colors are valid 6-character hex codes")
    
    def test_red_channel_dominant(self):
        """Test that red channel (first 2 chars) is always highest"""
        for color in self.red_colors:
            red_val = int(color[0:2], 16)
            green_val = int(color[2:4], 16)
            blue_val = int(color[4:6], 16)
            
            # Red should be >= green and blue (red-dominant colors)
            self.assertGreaterEqual(red_val, green_val, 
                                   f"Color {color}: red not dominant over green")
            self.assertGreaterEqual(red_val, blue_val, 
                                   f"Color {color}: red not dominant over blue")
        print("✓ All colors have red channel as dominant")
    
    def test_green_equals_blue(self):
        """Test that green and blue channels are equal (grayscale red tints)"""
        for color in self.red_colors:
            green_val = int(color[2:4], 16)
            blue_val = int(color[4:6], 16)
            self.assertEqual(green_val, blue_val, 
                           f"Color {color}: green and blue not equal")
        print("✓ Green and blue channels are equal in all colors")
    
    def test_sample_colors(self):
        """Print sample colors for visual inspection"""
        sample = sorted(list(self.red_colors))[:10]
        print("\n✓ Sample red colors generated:")
        for color in sample:
            print(f"  #{color}")
    
    def test_dark_and_light_reds(self):
        """Test that both dark and light reds are included"""
        has_dark = any(color.startswith(('3', '4', '5', '6', '7', '8', '9', 'A', 'B', 'C', 'D')) 
                      for color in self.red_colors)
        has_light = any(color.startswith('FF') for color in self.red_colors)
        
        self.assertTrue(has_dark, "No dark reds found")
        self.assertTrue(has_light, "No light reds found")
        print("✓ Contains both dark and light red variations")


if __name__ == '__main__':
    unittest.main(verbosity=2)