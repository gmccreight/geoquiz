"""Embeds the Canvas widget into a Sugar-specific Activity environment"""
import logging
logging.root.setLevel( logging.WARN )
log = logging.getLogger( 'olpcgames.activity' )
#log.setLevel( logging.INFO )

import pygtk
pygtk.require('2.0')
import gtk
import gtk.gdk

from sugar.activity import activity
from sugar.graphics import style
from olpcgames.canvas import PyGameCanvas
from olpcgames import mesh, util

__all__ = ['PyGameActivity']

class PyGameActivity(activity.Activity):
    """PyGame-specific activity type, provides boilerplate toolbar, creates canvas

    Subclass Overrides:

        game_name -- specifies a fully-qualified name for the game's main-loop
            format like so:
                'package.module:main'
            if not function name is provided, "main" is assumed.
        game_handler -- alternate specification via direct reference to a main-loop
            function

        game_size -- two-value tuple specifying the size of the display in pixels,
            this is currently static, so once the window is created it cannot be
            changed.

            If None, use the bulk of the screen for the PyGame surface based on
            the values reported by the gtk.gdk functions.  Note that None is
            *not* the default value.

        game_title -- title to be displayed in the Sugar Shell UI

        pygame_mode -- chooses the rendering engine used for handling the
            PyGame drawing mode, 'SDL' chooses the standard PyGame renderer,
            'Cairo' chooses the experimental pygamecairo renderer.

        PYGAME_CANVAS_CLASS -- normally PyGameCanvas, but can be overridden
            if you want to provide a different canvas class, e.g. to provide a different
            internal layout.  Note: only used where pygame_mode == 'SDL'

    The Activity, once created, will be made available as olpcgames.ACTIVITY,
    and that access mechanism should allow code to test for the presence of the
    activity before accessing Sugar-specific functionality.

    XXX Note that currently the toolbar and window layout are hard-coded into
    this super-class, with no easy way of overriding without completely rewriting
    the __init__ method.  We should allow for customising both the UI layout and
    the toolbar contents/layout/connection.
    
    XXX Note that if you change the title of your activity in the toolbar you may 
    see the same focus issues as we have patched around in the build_toolbar 
    method.  If so, please report them to Mike Fletcher.
    """
    game_name = None
    game_title = 'PyGame Game'
    game_handler = None
    game_size = (16 * style.GRID_CELL_SIZE,
                 11 * style.GRID_CELL_SIZE)
    pygame_mode = 'SDL'

    def __init__(self, handle):
        """Initialise the Activity with the activity-description handle"""
        super(PyGameActivity, self).__init__(handle)
        self.make_global()
        if self.game_size is None:
            width,height = gtk.gdk.screen_width(), gtk.gdk.screen_height()
            log.info( 'Total screen size: %s %s', width,height)
            # for now just fudge the toolbar size...
            self.game_size = width, height - (1*style.GRID_CELL_SIZE)
        self.set_title(self.game_title)
        toolbar = self.build_toolbar()
        log.debug( 'Toolbar size: %s', toolbar.get_size_request())
        canvas = self.build_canvas()

    def make_global( self ):
        """Hack to make olpcgames.ACTIVITY point to us
        """
        import weakref, olpcgames
        assert not olpcgames.ACTIVITY, """Activity.make_global called twice, have you created two Activity instances in a single process?"""
        olpcgames.ACTIVITY = weakref.proxy( self )

    def build_toolbar( self ):
        """Build our Activity toolbar for the Sugar system

        This is a customisation point for those games which want to
        provide custom toolbars when running under Sugar.
        """
        toolbar = activity.ActivityToolbar(self)
        toolbar.show()
        self.set_toolbox(toolbar)
        def shared_cb(*args, **kwargs):
            log.info( 'shared: %s, %s', args, kwargs )
            try:
                mesh.activity_shared(self)
            except Exception, err:
                log.error( """Failure signaling activity sharing to mesh module: %s""", util.get_traceback(err) )
            else:
                log.info( 'mesh activity shared message sent, trying to grab focus' )
            try:
                self._pgc.grab_focus()
            except Exception, err:
                log.warn( 'Focus failed: %s', err )
            else:
                log.info( 'asserting focus' )
                assert self._pgc.is_focus(), """Did not successfully set pygame canvas focus"""
            log.info( 'callback finished' )
            
        def joined_cb(*args, **kwargs):
            log.info( 'joined: %s, %s', args, kwargs )
            mesh.activity_joined(self)
            self._pgc.grab_focus()
        self.connect("shared", shared_cb)
        self.connect("joined", joined_cb)

        if self.get_shared():
            # if set at this point, it means we've already joined (i.e.,
            # launched from Neighborhood)
            joined_cb()

        toolbar.title.unset_flags(gtk.CAN_FOCUS)
        return toolbar

    PYGAME_CANVAS_CLASS = PyGameCanvas
    def build_canvas( self ):
        """Construct the PyGame or PyGameCairo canvas for drawing"""
        assert self.game_handler or self.game_name, 'You must specify a game_handler or game_name on your Activity (%r)'%(
            self.game_handler or self.game_name
        )
        if self.pygame_mode != 'Cairo':
            self._pgc = self.PYGAME_CANVAS_CLASS(*self.game_size)
            self.set_canvas(self._pgc)
            self._pgc.grab_focus()
            self._pgc.connect_game(self.game_handler or self.game_name)
            gtk.gdk.threads_init()
            return self._pgc
        else:
            import hippo
            self._drawarea = gtk.DrawingArea()
            canvas = hippo.Canvas()
            canvas.grab_focus()
            self.set_canvas(canvas)
            self.show_all()

            import pygamecairo
            pygamecairo.install()

            pygamecairo.display.init(canvas)
            app = self.game_handler or self.game_name
            if ':' not in app:
                app += ':main'
            mod_name, fn_name = app.split(':')
            mod = __import__(mod_name, globals(), locals(), [])
            fn = getattr(mod, fn_name)
            fn()
