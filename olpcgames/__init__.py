"""Wrapper/adaptation system for writing/porting PyGame games to OLPC/Sugar

The wrapper system attempts to substitute various pieces of the PyGame 
implementation in order to make code written without knowledge of the
OLPC/Sugar environment run "naturally" under the GTK environment of 
Sugar.  It also provides some convenience mechanisms for dealing with 
e.g. the Camera and Mesh Network system.

Considerations for Developers:

PyGame programs running under OLPCGames will generally not have
"hardware" surfaces, and will not be able to have a reduced-resolution 
full-screen view to optimise rendering.  The PyGame code will run in 
a secondary thread, with the main GTK UI running in the primary thread.
A third "mainloop" thread will occasionally be created to handle the 
GStreamer interface to the camera.

Attributes of Note:

    ACTIVITY -- if not None, then the activity instance which represents
        this activity at the Sugar shell level.
    WIDGET -- PygameCanvas instance, a GTK widget with an embedded
        socket object which is a proxy for the SDL window Pygame to which
        pygame renders.
"""
# XXX handle configurations that are not running under Sugar and 
# report proper errors to describe the problem, rather than letting the 
# particular errors propagate outward.
# XXX allow use of a particular feature within the library without needing
# to be running under sugar.  e.g. allow importing mesh or camera without 
# needing to import the activity machinery.
from olpcgames.canvas import *
try:
    from olpcgames.activity import *
except ImportError, err:
    PyGameActivity = None
from olpcgames import camera
from olpcgames import pangofont
from olpcgames import mesh

ACTIVITY = None
widget = WIDGET = None
