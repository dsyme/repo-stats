#!/usr/bin/env python3
"""
Shared chart theme module for Plotly-based graphs.

Provides centralized theming, color palettes, and export utilities
so all report graphs have a consistent, presentation-quality look.

Usage:
    from chart_theme import get_theme, save_figure, add_adoption_line, COLORS
"""

import os
import plotly.graph_objects as go
import plotly.io as pio


# ---------------------------------------------------------------------------
# Color palettes — Ocean Sunset (coolors.co/palette/001219-005f73-…-9b2226)
# ---------------------------------------------------------------------------

# The 10-color ocean sunset gradient
OCEAN_SUNSET = [
    "#001219",  # rich black (deep ocean)
    "#005f73",  # dark cyan
    "#0a9396",  # teal
    "#94d2bd",  # light teal
    "#e9d8a6",  # wheat / sand
    "#ee9b00",  # amber
    "#ca6702",  # burnt orange
    "#bb3e03",  # rust
    "#ae2012",  # dark red
    "#9b2226",  # deep red (sunset)
]

# Semantic color roles mapped from the palette
COLORS = {
    "primary": "#005f73",       # dark cyan
    "secondary": "#0a9396",     # teal
    "accent": "#ee9b00",        # amber
    "danger": "#ae2012",        # dark red
    "muted": "#94d2bd",         # light teal
    "dark": "#001219",          # rich black
    "warm": "#ca6702",          # burnt orange
    "rust": "#bb3e03",          # rust
    "sand": "#e9d8a6",          # wheat / sand
    "deep_red": "#9b2226",      # deep red
}

# Qualitative palette for multi-line/multi-category charts
# Ordered for maximum visual contrast between adjacent items
PALETTE = [
    "#005f73",  # dark cyan
    "#ee9b00",  # amber
    "#ae2012",  # dark red
    "#0a9396",  # teal
    "#ca6702",  # burnt orange
    "#9b2226",  # deep red
    "#94d2bd",  # light teal
    "#bb3e03",  # rust
    "#001219",  # rich black
    "#e9d8a6",  # wheat / sand
]

# Status colors for bottleneck analysis (mapped from ocean sunset)
STATUS_COLORS = {
    "BLOCKED": "#ae2012",       # dark red
    "CONSTRAINED": "#ca6702",   # burnt orange
    "MINOR": "#ee9b00",         # amber
    "FLOWING": "#0a9396",       # teal
    "IDLE": "#94d2bd",          # light teal
}

# Before/after comparison colors
BEFORE_COLOR = "#e9d8a6"   # sand (muted, past)
AFTER_COLOR = "#005f73"    # dark cyan (strong, present)
AFTER_COLOR_ALT = "#0a9396"  # teal (alternative for second metric)

# Stacked bar category colors (invocation analysis)
CATEGORY_COLORS = {
    "scheduled": "#005f73",     # dark cyan
    "extra": "#0a9396",         # teal
    "repo_assist": "#ee9b00",   # amber
}


# ---------------------------------------------------------------------------
# Theme presets
# ---------------------------------------------------------------------------

_FONT_FAMILY = "Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif"

_SHARED = dict(
    margin=dict(l=60, r=30, t=80, b=60),
    hovermode="x unified",
    hoverlabel=dict(font_size=12),
)

_LIGHT_LAYOUT = {
    **_SHARED,
    "font": dict(family=_FONT_FAMILY, size=14),
    "title": dict(font=dict(size=20, color="#212121"), x=0.5, xanchor="center"),
    "legend": dict(font=dict(size=12), borderwidth=0, bgcolor="rgba(255,255,255,0.7)"),
    "paper_bgcolor": "#FFFFFF",
    "plot_bgcolor": "#FAFAFA",
    "xaxis": dict(gridcolor="#E0E0E0", linecolor="#BDBDBD", zerolinecolor="#E0E0E0",
                  title=dict(font=dict(size=14, color="#424242")),
                  tickfont=dict(size=12, color="#616161")),
    "yaxis": dict(gridcolor="#E0E0E0", linecolor="#BDBDBD", zerolinecolor="#E0E0E0",
                  title=dict(font=dict(size=14, color="#424242")),
                  tickfont=dict(size=12, color="#616161")),
}

_DARK_LAYOUT = {
    **_SHARED,
    "font": dict(family=_FONT_FAMILY, size=14, color="#CDD6F4"),
    "title": dict(font=dict(size=20, color="#CDD6F4"), x=0.5, xanchor="center"),
    "legend": dict(font=dict(size=12, color="#CDD6F4"), borderwidth=0, bgcolor="rgba(30,30,46,0.8)"),
    "paper_bgcolor": "#1E1E2E",
    "plot_bgcolor": "#262637",
    "xaxis": dict(gridcolor="#45475A", linecolor="#585B70", zerolinecolor="#45475A",
                  title=dict(font=dict(size=14, color="#A6ADC8")),
                  tickfont=dict(size=12, color="#A6ADC8")),
    "yaxis": dict(gridcolor="#45475A", linecolor="#585B70", zerolinecolor="#45475A",
                  title=dict(font=dict(size=14, color="#A6ADC8")),
                  tickfont=dict(size=12, color="#A6ADC8")),
}

_PRESENTATION_LAYOUT = {
    **_SHARED,
    "font": dict(family=_FONT_FAMILY, size=16),
    "title": dict(font=dict(size=26, color="#212121"), x=0.5, xanchor="center"),
    "legend": dict(font=dict(size=14), borderwidth=0, bgcolor="rgba(255,255,255,0.85)"),
    "paper_bgcolor": "#FFFFFF",
    "plot_bgcolor": "#FAFAFA",
    "margin": dict(l=70, r=40, t=100, b=70),
    "xaxis": dict(gridcolor="#E0E0E0", linecolor="#BDBDBD", zerolinecolor="#E0E0E0",
                  title=dict(font=dict(size=16, color="#424242")),
                  tickfont=dict(size=14, color="#616161")),
    "yaxis": dict(gridcolor="#E0E0E0", linecolor="#BDBDBD", zerolinecolor="#E0E0E0",
                  title=dict(font=dict(size=16, color="#424242")),
                  tickfont=dict(size=14, color="#616161")),
}

THEMES = {
    "light": _LIGHT_LAYOUT,
    "dark": _DARK_LAYOUT,
    "presentation": _PRESENTATION_LAYOUT,
}

# Default theme — can be overridden via CHART_THEME env var
_current_theme = os.environ.get("CHART_THEME", "light")


def get_theme(name=None):
    """Return a layout dict for the given theme name."""
    theme = name or _current_theme
    return THEMES.get(theme, THEMES["light"])


def set_theme(name):
    """Set the default theme globally."""
    global _current_theme
    _current_theme = name


def apply_theme(fig, theme=None):
    """Apply a theme to an existing Plotly figure."""
    layout = get_theme(theme)
    fig.update_layout(**layout)
    return fig


# ---------------------------------------------------------------------------
# Figure factory
# ---------------------------------------------------------------------------

def make_figure(title="", width=1200, height=600, theme=None):
    """Create a themed Plotly figure."""
    layout = get_theme(theme)
    fig = go.Figure()
    fig.update_layout(
        **layout,
        title_text=title,
        width=width,
        height=height,
    )
    return fig


# ---------------------------------------------------------------------------
# Adoption line helper
# ---------------------------------------------------------------------------

def add_adoption_line(fig, adoption_date, label="repo-assist"):
    """Add a vertical dashed line marking adoption date."""
    if adoption_date is None:
        return fig
    fig.add_shape(
        type="line",
        x0=adoption_date, x1=adoption_date,
        y0=0, y1=1, yref="paper",
        line=dict(color=COLORS["secondary"], width=2, dash="dash"),
    )
    fig.add_annotation(
        x=adoption_date, y=1, yref="paper",
        text=f" {label}",
        showarrow=False,
        font=dict(size=11, color=COLORS["secondary"], family="Inter, sans-serif"),
        xanchor="left", yanchor="top",
    )
    return fig


def add_adoption_vline_at_zero(fig, label="Adoption day"):
    """Add a vertical line at x=0 for normalized charts."""
    fig.add_vline(
        x=0,
        line_dash="solid",
        line_color=COLORS["danger"],
        line_width=2,
        opacity=0.6,
        annotation_text=label,
        annotation_position="top right",
        annotation_font=dict(size=11, color=COLORS["danger"]),
    )
    return fig


# ---------------------------------------------------------------------------
# Export utilities
# ---------------------------------------------------------------------------

def save_figure(fig, output_path, write_html=True):
    """Save figure as PNG and optionally as interactive HTML.

    Args:
        fig: Plotly figure
        output_path: path ending in .png
        write_html: if True, also save an .html alongside
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    fig.write_image(output_path, scale=2)
    print(f"  Saved: {output_path}")

    if write_html:
        html_path = output_path.rsplit(".", 1)[0] + ".html"
        fig.write_html(html_path, include_plotlyjs="cdn")
        print(f"  Saved: {html_path}")
