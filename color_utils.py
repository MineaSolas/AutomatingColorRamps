import colorsys

def get_highlight_color(color):
    r, g, b = [c / 255.0 for c in color[:3]]
    h, _, _ = colorsys.rgb_to_hsv(r, g, b)
    return "cyan" if h < 0.125 or h > 0.7 else "red"

def get_text_descriptions(color):
    r, g, b = [int(c) for c in color[:3]]
    h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    h_deg, s_pct, v_pct = int(h * 360), int(s * 100), int(v * 100)
    hex_str = f"#{r:02X}{g:02X}{b:02X}"
    return {
        "rgb": f"RGB: ({r}, {g}, {b})",
        "hex": f"HEX: {hex_str}",
        "hsv": f"HSV: ({h_deg}°, {s_pct}%, {v_pct}%)",
        "hex_raw": hex_str
    }
