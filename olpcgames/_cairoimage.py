"""Utility functions for cairo-specific operations"""
import cairo, pygame, struct
big_endian = struct.pack( '=i', 1 ) == struct.pack( '>i', 1 )

def newContext( width, height ):
    """Create a new render-to-image context
    
    width, height -- pixel dimensions to be rendered
    
    returns surface, context for rendering
    """
    csrf = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    return csrf, cairo.Context (csrf)

def mangle_color(color):
    """Mange a colour depending on endian-ness, and swap-necessity
    
    This implementation has only been tested on an AMD64
    machine with a get_data implementation (rather than 
    a get_data_as_rgba implementation).
    """
    r,g,b = color[:3]
    if len(color) > 3:
        a = color[3]
    else:
        a = 255.0
    return map(_fixColorBase, (r,g,b,a) )

def _fixColorBase( v ):
    """Return a properly clamped colour in floating-point space"""
    return max((0,min((v,255.0))))/255.0

def asImage( csrf ):
    """Get the pixels in csrf as a Pygame image"""
    # Create and return a new Pygame Image derived from the Cairo Surface
    format = 'ARGB'
    if hasattr(csrf,'get_data'):
        # more recent API, native-format, but have to (potentially) convert the format...
        data = csrf.get_data()
        if not big_endian:
            import numpy
            data = numpy.frombuffer( data, 'I' ).astype( '>I4' ).tostring()
        else:
            data = str(data) # there's one copy
    else:
        # older api, not native, but we know what it is...
        data = csrf.get_data_as_rgba()
        data = str(data) # there's one copy
    width, height = csrf.get_width(),csrf.get_height()
    try:
        return pygame.image.fromstring(
            data, 
            (width,height), 
            format
        ) # there's the next
    except ValueError, err:
        err.args += (len(data), (width,height), width*height*4,format )
        raise
