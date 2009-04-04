"""Implement Pygame's font interface using Pango for international support

Depends on:

    pygtk (to get the pango context)
    pycairo (for the pango rendering context)
    python-pango (obviously)
    pygame (obviously)
"""
import pango
import logging
import cairo
import pangocairo
import pygame.rect, pygame.image
import gtk
import struct
from pygame import surface
from olpcgames import _cairoimage

log = logging.getLogger( 'olpcgames.pangofont' )
#log.setLevel( logging.DEBUG )

# Install myself on top of pygame.font
def install():
    """Replace Pygame's font module with this module"""
    log.info( 'installing' )
    from olpcgames import pangofont
    import pygame
    pygame.font = pangofont
    import sys
    sys.modules["pygame.font"] = pangofont
    print "loading..."

class PangoFont(object):
    """Base class for a pygame.font.Font-like object drawn by Pango
    
    Attributes of note:
    
        fd -- instances Pango FontDescription object 
        WEIGHT_* -- parameters for use with set_weight
        STYLE_* -- parameters for use with set_style
        
    """
    WEIGHT_BOLD = pango.WEIGHT_BOLD
    WEIGHT_HEAVY = pango.WEIGHT_HEAVY
    WEIGHT_LIGHT = pango.WEIGHT_LIGHT
    WEIGHT_NORMAL = pango.WEIGHT_NORMAL
    WEIGHT_SEMIBOLD = pango.WEIGHT_SEMIBOLD
    WEIGHT_ULTRABOLD = pango.WEIGHT_ULTRABOLD
    WEIGHT_ULTRALIGHT = pango.WEIGHT_ULTRALIGHT
    STYLE_NORMAL = pango.STYLE_NORMAL
    STYLE_ITALIC = pango.STYLE_ITALIC
    STYLE_OBLIQUE = pango.STYLE_OBLIQUE
    def __init__(self, family=None, size=None, bold=False, italic=False, underline=False, fd=None):
        """If you know what pango.FontDescription (fd) you want, pass it in as
        'fd'.  Otherwise, specify any number of family, size, bold, or italic,
        and we will try to match something up for you."""

        # Always set the FontDescription (FIXME - only set it if the user wants
        # to change something?)
        if fd is None:
            fd = pango.FontDescription()
            if family is not None:
                fd.set_family(family)
            if size is not None:
                fd.set_size(size*1000)
        self.fd = fd
        self.set_bold( bold )
        self.set_italic( italic )
        self.set_underline( underline )

    def render(self, text, antialias=True, color=(255,255,255), background=None ):
        """Render the font onto a new Surface and return it.
        We ignore 'antialias' and use system settings.
        
        text -- (unicode) string with the text to render
        antialias -- attempt to antialias the text or not
        color -- three or four-tuple of 0-255 values specifying rendering 
            colour for the text 
        background -- three or four-tuple of 0-255 values specifying rendering 
            colour for the background, or None for trasparent background
        
        returns a pygame image instance
        """
        log.info( 'render: %r, antialias = %s, color=%s, background=%s', text, antialias, color, background )

        # create layout
        layout = pango.Layout(gtk.gdk.pango_context_get())
        layout.set_font_description(self.fd)
        if self.underline:
            attrs = layout.get_attributes()
            if not attrs:
                attrs = pango.AttrList()
            attrs.insert(pango.AttrUnderline(pango.UNDERLINE_SINGLE, 0, 32767))
            layout.set_attributes( attrs )
        layout.set_text(text)

        # determine pixel size
        (logical, ink) = layout.get_pixel_extents()
        ink = pygame.rect.Rect(ink)

        # Create a new Cairo ImageSurface
        csrf,cctx = _cairoimage.newContext( ink.w, ink.h )
        cctx = pangocairo.CairoContext(cctx)

        # Mangle the colors on little-endian machines. The reason for this 
        # is that Cairo writes native-endian 32-bit ARGB values whereas
        # Pygame expects endian-independent values in whatever format. So we
        # tell our users not to expect transparency here (avoiding the A issue)
        # and we swizzle all the colors around.

        # render onto it
        if background is not None:
            background = _cairoimage.mangle_color( background )
            cctx.set_source_rgba(*background)
            cctx.paint()
        
        log.debug( 'incoming color: %s', color )
        color = _cairoimage.mangle_color( color )
        log.debug( '  translated color: %s', color )

        cctx.new_path()
        cctx.layout_path(layout)
        cctx.set_source_rgba(*color)
        cctx.fill()

        # Create and return a new Pygame Image derived from the Cairo Surface
        return _cairoimage.asImage( csrf )
    
    def set_bold( self, bold=True):
        """Set our font description's weight to "bold" or "normal"
        
        bold -- boolean, whether to set the value to "bold" weight or not 
        """
        if bold:
            self.set_weight(  self.WEIGHT_BOLD )
        else:
            self.set_weight(  self.WEIGHT_NORMAL )
    def set_weight( self, weight ):
        """Explicitly set our pango-style weight value"""
        self.fd.set_weight(  weight )
        return self.get_weight()
    def get_weight( self ):
        """Explicitly get our pango-style weight value"""
        return self.fd.get_weight()
    def get_bold( self ):
        """Return whether our font's weight is bold (or above)"""
        return self.fd.get_weight() >= pango.WEIGHT_BOLD
    
    def set_italic( self, italic=True ):
        """Set our "italic" value (style)"""
        if italic:
            self.set_style( self.STYLE_ITALIC )
        else:
            self.set_style( self.STYLE_NORMAL )
    def set_style( self, style ):
        """Set our font description's pango-style"""
        self.fd.set_style( style )
        return self.fd.get_style()
    def get_style( self ):
        """Get our font description's pango-style"""
        return self.fd.get_style()
    def get_italic( self ):
        """Return whether we are currently italicised"""
        return self.fd.get_style() == self.STYLE_ITALIC # what about oblique?
    
    def set_underline( self, underline=True ):
        """Set our current underlining properly"""
        self.underline = underline
    def get_underline( self ):
        return self.underline

class SysFont(PangoFont):
    """Construct a PangoFont from a font description (name), size in pixels,
    bold, and italic designation. Similar to SysFont from Pygame."""
    def __init__(self, name, size, bold=False, italic=False):
        fd = pango.FontDescription(name)
        fd.set_absolute_size(size*pango.SCALE)
        if bold:
            fd.set_weight(pango.WEIGHT_BOLD)
        if italic:
            fd.set_style(pango.STYLE_OBLIQUE)
        super(SysFont, self).__init__(fd=fd)

# originally defined a new class, no reason for that...
NotImplemented = NotImplementedError

class Font(PangoFont):
    """Abstract class, do not use"""
    def __init__(self, *args, **kwargs):
        raise NotImplementedError("PangoFont doesn't support Font directly, use SysFont or .fontByDesc")

def match_font(name,bold=False,italic=False):
    """Stub, does not work, use fontByDesc instead"""
    raise NotImplementedError("PangoFont doesn't support match_font directly, use SysFont or .fontByDesc")

def fontByDesc(desc="",bold=False,italic=False):
    """Constructs a FontDescription from the given string representation.
The format of the string representation is:

  "[FAMILY-LIST] [STYLE-OPTIONS] [SIZE]"

where FAMILY-LIST is a comma separated list of families optionally terminated by a comma, STYLE_OPTIONS is a whitespace separated list of words where each WORD describes one of style, variant, weight, or stretch, and SIZE is an decimal number (size in points). For example the following are all valid string representations:

  "sans bold 12"
  "serif,monospace bold italic condensed 16"
  "normal 10"

The commonly available font families are: Normal, Sans, Serif and Monospace. The available styles are:
Normal	the font is upright.
Oblique	the font is slanted, but in a roman style.
Italic	the font is slanted in an italic style.

The available weights are:
Ultra-Light	the ultralight weight (= 200)
Light	the light weight (=300)
Normal	the default weight (= 400)
Bold	the bold weight (= 700)
Ultra-Bold	the ultra-bold weight (= 800)
Heavy	the heavy weight (= 900)

The available variants are:
Normal	
Small-Caps	

The available stretch styles are:
Ultra-Condensed	the smallest width
Extra-Condensed	
Condensed	
Semi-Condensed	
Normal	the normal width
Semi-Expanded	
Expanded	
Extra-Expanded	
Ultra-Expanded	the widest width
    """
    fd = pango.FontDescription(name)
    if bold:
        fd.set_weight(pango.WEIGHT_BOLD)
    if italic:
        fd.set_style(pango.STYLE_OBLIQUE)
    return PangoFont(fd=fd)

def get_init():
    """Return boolean indicating whether we are initialised
    
    Always returns True 
    """
    return True

def init():
    """Initialise the module (null operation)"""
    pass

def quit():
    """De-initialise the module (null operation)"""
    pass

def get_default_font():
    """Return default-font specification to be passed to e.g. fontByDesc"""
    return "sans"

def get_fonts():
    """Return the set of all fonts available (currently just 3 generic types)"""
    return ["sans","serif","monospace"]


def stdcolor(color):
    """Produce a 4-element 0.0-1.0 color value from input"""
    def fixlen(color):
        if len(color) == 3:
            return tuple(color) + (255,)
        elif len(color) == 4:
            return color
        else:
            raise TypeError("What sort of color is this: %s" % (color,))
    return [_fixColorBase(x) for x in fixlen(color)]
def _fixColorBase( v ):
    """Return a properly clamped colour in floating-point space"""
    return max((0,min((v,255.0))))/255.0
