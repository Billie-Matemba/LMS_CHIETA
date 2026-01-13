import re


def debug_html_red_detection(html_content):
    """Diagnose why red text isn't being detected/removed"""
    
    target_colors = get_red_color_range()
    target_colors_lower = {color.lower() for color in target_colors}
    
    print("\n" + "="*60)
    print("🔍 HTML RED TEXT DETECTION DIAGNOSIS")
    print("="*60)
    
    # Pattern 1: Inline style with hex color
    hex_pattern = r'style\s*=\s*["\']([^"\']*color\s*:\s*#?([A-Fa-f0-9]{6})[^"\']*)["\']'
    hex_matches = re.findall(hex_pattern, html_content, re.IGNORECASE)
    
    if hex_matches:
        print(f"\n✓ Found {len(hex_matches)} inline hex color styles:")
        for full_style, color_code in hex_matches:
            is_red = color_code.upper() in target_colors_lower
            status = "🔴 RED" if is_red else "⚪ NOT RED"
            print(f"  {status}: style='{full_style}' → color: #{color_code.upper()}")
    
    # Pattern 2: RGB colors
    rgb_pattern = r'color\s*:\s*rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)'
    rgb_matches = re.findall(rgb_pattern, html_content, re.IGNORECASE)
    
    if rgb_matches:
        print(f"\n✓ Found {len(rgb_matches)} RGB color styles:")
        for r, g, b in rgb_matches:
            hex_val = f"{int(r):02X}{int(g):02X}{int(b):02X}"
            is_red = hex_val in target_colors_lower
            status = "🔴 RED" if is_red else "⚪ NOT RED"
            print(f"  {status}: rgb({r}, {g}, {b}) → #{hex_val}")
    
    # Pattern 3: Named colors
    named_color_pattern = r'color\s*:\s*(red|crimson|maroon|darkred|indianred|lightcoral)\b'
    named_matches = re.findall(named_color_pattern, html_content, re.IGNORECASE)
    
    if named_matches:
        print(f"\n✓ Found {len(named_matches)} named color styles:")
        for color_name in set(named_matches):
            print(f"  🔴 RED: color: {color_name}")
    
    # Pattern 4: Word-generated span tags
    word_span_pattern = r'<span\s+([^>]*?)>(.*?)</span>'
    span_matches = re.findall(word_span_pattern, html_content, re.IGNORECASE)
    
    if span_matches:
        print(f"\n✓ Found {len(span_matches)} span tags:")
        for attrs, content in span_matches[:5]:  # Show first 5
            print(f"  <span {attrs}>{content[:30]}...</span>")
    
    # Pattern 5: Font color attribute (old HTML)
    font_color_pattern = r'<font\s+color\s*=\s*["\']?([A-Fa-f0-9]{6}|red|crimson)["\']?'
    font_matches = re.findall(font_color_pattern, html_content, re.IGNORECASE)
    
    if font_matches:
        print(f"\n✓ Found {len(font_matches)} <font color> tags (old HTML):")
        for color in set(font_matches):
            print(f"  <font color='{color}'>")
    
    print("\n" + "="*60)
    return {
        "hex_styles": len(hex_matches),
        "rgb_styles": len(rgb_matches),
        "named_colors": len(named_matches),
        "span_tags": len(span_matches),
        "font_tags": len(font_matches)
    }


def strip_all_red_text_improved(html_content, target_colors=None):
    """
    Improved red text removal - handles ALL red format variations
    """
    if target_colors is None:
        target_colors = get_red_color_range()
    
    # Normalize target colors: remove # and uppercase
    target_colors_normalized = {
        color.lstrip('#').upper() for color in target_colors
    }
    
    def is_red_color(color_value):
        """Check if a color value is in our red set"""
        # Remove hash and uppercase for comparison
        normalized = color_value.lstrip('#').upper()[:6]
        return normalized in target_colors_normalized
    
    # 1. Remove inline style attributes with any red format
    html_content = re.sub(
        r'style\s*=\s*"([^"]*?)color\s*:\s*(?:#)?([A-Fa-f0-9]{6})([^"]*?)"',
        lambda m: (
            f'style="{m.group(1)}color: transparent{m.group(3)}"'
            if is_red_color(m.group(2))
            else m.group(0)
        ),
        html_content,
        flags=re.IGNORECASE
    )
    
    # 2. Remove RGB format colors
    html_content = re.sub(
        r'color\s*:\s*rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)',
        lambda m: (
            'color: transparent'
            if is_red_color(f"{int(m.group(1)):02X}{int(m.group(2)):02X}{int(m.group(3)):02X}")
            else m.group(0)
        ),
        html_content,
        flags=re.IGNORECASE
    )
    
    # 3. Remove named red colors
    html_content = re.sub(
        r'color\s*:\s*(red|crimson|maroon|darkred|indianred|lightcoral|tomato|orangered)\b',
        'color: transparent',
        html_content,
        flags=re.IGNORECASE
    )
    
    # 4. Remove <font color> tags
    html_content = re.sub(
        r'<font\s+color\s*=\s*["\']?([A-Fa-f0-9]{6}|red|crimson)["\']?\s*>(.*?)</font>',
        lambda m: m.group(2) if is_red_color(m.group(1)) else m.group(0),
        html_content,
        flags=re.IGNORECASE
    )
    
    # 5. Remove colored spans, divs, etc
    for tag in ['span', 'div', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
        html_content = re.sub(
            rf'<{tag}\s+style\s*=\s*"([^"]*?)color\s*:\s*(?:#)?([A-Fa-f0-9]{{6}})([^"]*)"\s*>(.*?)</{tag}>',
            lambda m: (
                m.group(4)  # Keep content, remove tag
                if is_red_color(m.group(2))
                else m.group(0)
            ),
            html_content,
            flags=re.IGNORECASE
        )
    
    return html_content, True

def get_red_color_range():
    """Generate all red variations (red channel dominant)"""
    reds = set()
    
    # Red channel: FF down to 33 (bright to darker reds)
    for red_val in range(255, 50, -1):  # Changed step from -10 to -1 for ALL variations
        red_hex = f"{red_val:02X}"
        
        # Green/Blue channels: 0 to red_val (creates red family)
        for gb_val in range(0, min(red_val + 1, 256), 1):  # step by 1
            gb_hex = f"{gb_val:02X}"
            color_code = f"{red_hex}{gb_hex}{gb_hex}"
            
            # Add BOTH versions: with and without hash
            reds.add(color_code)          # FF0000 (without hash)
            reds.add(f"#{color_code}")    # #FF0000 (with hash)
            reds.add(color_code.lower())  # ff0000 (lowercase without hash)
            reds.add(f"#{color_code.lower()}")  # #ff0000 (lowercase with hash)
    
    return reds


