"""Provides substitute for Pygame's "event" module using gtkEvent

Provides methods which will be substituted into Pygame in order to 
provide the synthetic events that we will feed into the Pygame queue.
These methods are registered by the "install" method.

Extension:

    last_event_time() -- returns period since the last event was produced
        in seconds.  This can be used to create "pausing" effects for games.
"""
import pygame
import gtk
import Queue
import thread
import logging

log = logging.getLogger( 'olpcgames.eventwrap' )

# This module reuses Pygame's Event, but
# reimplements the event queue.
from pygame.event import Event, event_name, pump as pygame_pump, get as pygame_get

class Event(object):
    """Mock pygame events"""
    def __init__(self, type, **named):
        self.type = type
        self.__dict__.update( named )

#print "Initializing own event.py"

# Install myself on top of pygame.event
def install():
    """Installs this module (eventwrap) as an in-place replacement for the pygame.event module.
   
    Use install() when you need to interact with Pygame code written
    without reference to the olpcgames wrapper mechanisms to have the 
    code use this module's event queue.
    
    XXX Really, use it everywhere you want to use olpcgames, as olpcgames
    registers the handler itself, so you will always wind up with it registered when 
    you use olpcgames (the gtkEvent.Translator.hook_pygame method calls it).
    """
    import eventwrap,pygame
    pygame.event = eventwrap
    import sys
    sys.modules["pygame.event"] = eventwrap
    

# Event queue:
g_events = Queue.Queue()

# Set of blocked events as set by set
g_blocked = set()
g_blockedlock = thread.allocate_lock()
g_blockAll = False

def pump():
    """Handle any window manager and other external events that aren't passed to the user. Call this periodically (once a frame) if you don't call get(), poll() or wait()."""
    pygame_pump()

def get():
    """Get a list of all pending events. (Unlike pygame, there's no option to filter by event type; you should use set_blocked() if you don't want to see certain events.)"""
    pump()
    eventlist = []
    try:
        while True:
            eventlist.append(g_events.get(block=False))
    except Queue.Empty:
        pass
    
    pygameEvents = pygame_get()
    if pygameEvents:
        log.info( 'Raw Pygame events: %s', pygameEvents)
        eventlist.extend( pygameEvents )
    if eventlist:
        _set_last_event_time()
    return eventlist

_LAST_EVENT_TIME = 0
    
def _set_last_event_time( time=None ):
    """Set this as the last event time"""
    global _LAST_EVENT_TIME
    if time is None:
        time = pygame.time.get_ticks()
    _LAST_EVENT_TIME = time 
    return time 
    
def last_event_time( ):
    """Return the last event type for pausing operations in seconds"""
    global _LAST_EVENT_TIME
    return (pygame.time.get_ticks() - _LAST_EVENT_TIME)/1000.

def poll():
    """Get the next pending event if exists. Otherwise, return pygame.NOEVENT."""
    pump()
    try:
        result = g_events.get(block=False)
        _set_last_event_time()
        return result
    except Queue.Empty:
        return Event(pygame.NOEVENT)


def wait( timeout = None):
    """Get the next pending event, wait up to timeout if none
    
    timeout -- if present, only wait up to timeout seconds, if we 
        do not find an event before then, return None
    """
    pump()
    try:
        result = g_events.get(block=True, timeout=timeout)
        _set_last_event_time()
        return result
    except Queue.Empty, err:
        return None

def peek(types=None):
    """True if there is any pending event. (Unlike pygame, there's no option to
    filter by event type)"""
    return not g_events.empty()
    
def clear():
    """Dunno why you would do this, but throws every event out of the queue"""
    try:
        while True:
            g_events.get(block=False)
    except Queue.Empty:
        pass

def set_blocked(item):
    g_blockedlock.acquire()
    try:
        # FIXME: we do not currently know how to block all event types when
        # you set_blocked(none).
        [g_blocked.add(x) for x in makeseq(item)]
    finally:
        g_blockedlock.release()
    
def set_allowed(item):
    g_blockedlock.acquire()
    try:
        if item is None:
            # Allow all events when you set_allowed(none). Strange, eh?
            # Pygame is a wonderful API.
            g_blocked.clear()
        else:
            [g_blocked.remove(x) for x in makeseq(item)]
    finally:
        g_blockedlock.release()

def get_blocked(*args, **kwargs):
    g_blockedlock.acquire()
    try:
        blocked = frozenset(g_blocked)
        return blocked
    finally:
        g_blockedlock.release()

def set_grab(grabbing):
    # We don't do this.
    pass

def get_grab():
    # We don't do this.
    return False

def post(event):
    #print "posting on own"
    g_blockedlock.acquire()
    try:
        if event.type not in g_blocked:
            g_events.put(event, block=False)
    finally:
        g_blockedlock.release()

def makeseq(obj):
    """Accept either a scalar object or a sequence, and return a sequence
    over which we can iterate. If we were passed a sequence, return it
    unchanged. If we were passed a scalar, return a tuple containing only
    that scalar. This allows the caller to easily support one-or-many.
    """
    # Strings are the exception because you can iterate over their chars
    # -- yet, for all the purposes I've ever cared about, I want to treat
    # a string as a scalar.
    if isinstance(obj, basestring):
        return (obj,)
    try:
        # Except as noted above, if you can get an iter() from an object,
        # it's a collection.
        iter(obj)
        return obj
    except TypeError:
        # obj is a scalar. Wrap it in a tuple so we can iterate over the
        # one item.
        return (obj,)
