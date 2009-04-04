"""Implements bridge connection between Sugar/GTK and PyGame"""
import os
import sys
import logging
log = logging.getLogger( 'olpcgames.canvas' )
#log.setLevel( logging.DEBUG )
import threading
from pprint import pprint

import pygtk
pygtk.require('2.0')
import gtk
import gobject
import pygame

from olpcgames import gtkEvent, util

__all__ = ['PyGameCanvas']

class PyGameCanvas(gtk.Layout):
    """Canvas providing bridge methods to run PyGame in GTK
    
    The PyGameCanvas creates a secondary thread in which the Pygame instance will 
    live, providing synthetic PyGame events to that thread via a Queue.  The GUI 
    connection is  done by having the PyGame canvas use a GTK Port object as it's 
    window pointer, it draws to that X-level window in order to produce output.
    """
    def __init__(self, width, height):
        """Initializes the Canvas Object
        
        width,height -- passed to the inner EventBox in order to request a given size,
            the Socket is the only child of this EventBox, and the PyGame commands
            will be writing to the Window ID of the socket.  The internal EventBox is 
            centered via an Alignment instance within the PyGameCanvas instance.
            
        XXX Should refactor so that the internal setup can be controlled by the 
        sub-class, e.g. to get size from the host window, or something similar.
        """
        # Build the main widget
        super(PyGameCanvas,self).__init__()
        self.set_flags(gtk.CAN_FOCUS)
        
        # Build the sub-widgets
        self._align = gtk.Alignment(0.5, 0.5)
        self._inner_evb = gtk.EventBox()
        self._socket = gtk.Socket()

        
        # Add internal widgets
        self._inner_evb.set_size_request(width, height)
        self._inner_evb.add(self._socket)
        
        self._socket.show()
        
        self._align.add(self._inner_evb)
        self._inner_evb.show()
        
        self._align.show()
        
        self.put(self._align, 0,0)
        
        # Construct a gtkEvent.Translator
        self._translator = gtkEvent.Translator(self, self._inner_evb)
        # <Cue Thus Spract Zarathustra>
        self.show()
    def connect_game(self, app):
        """Imports the given main-loop and starts processing in secondary thread 
        
        app -- fully-qualified Python path-name for the game's main-loop, with 
            name within module as :functionname, if no : character is present then 
            :main will be assumed.
        
        Side effects:
        
            Sets the SDL_WINDOWID variable to our socket's window ID 
            Calls PyGame init
            Causes the gtkEvent.Translator to "hook" PyGame
            Creates and starts secondary thread for Game/PyGame event processing.
        """
        # Setup the embedding
        os.environ['SDL_WINDOWID'] = str(self._socket.get_id())
        #print 'Socket ID=%s'%os.environ['SDL_WINDOWID']
        pygame.init()

        self._translator.hook_pygame()
        
        # Load the modules
        # NOTE: This is delayed because pygame.init() must come after the embedding is up
        if ':' not in app:
            app += ':main'
        mod_name, fn_name = app.split(':')
        mod = __import__(mod_name, globals(), locals(), [])
        fn = getattr(mod, fn_name)
        
        # Start Pygame
        self.__thread = threading.Thread(target=self._start, args=[fn])
        self.__thread.start()

    def _start(self, fn):
        """The method that actually runs in the background thread"""
        import olpcgames
        olpcgames.widget = olpcgames.WIDGET = self
        try:
            import sugar.activity.activity,os
        except ImportError, err:
            log.info( """Running outside Sugar""" )
        else:
            try:
                os.chdir(sugar.activity.activity.get_bundle_path())
            except KeyError, err:
                pass
        
        try:
            try:
                log.info( '''Running mainloop: %s''', fn )
                fn()
            except Exception, err:
                log.error(
                    """Uncaught top-level exception: %s""",
                    util.get_traceback( err ),
                )
                raise
        finally:
            gtk.main_quit()
