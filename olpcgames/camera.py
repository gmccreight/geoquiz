"""Accesses OLPC Camera functionality via gstreamer

Depends upon:
    pygame 
    python-gstreamer
"""
import threading
import logging
import time
import os
import pygame
import gst
from olpcgames.util import get_activity_root

log = logging.getLogger( 'olpcgames.camera' )
#log.setLevel( logging.DEBUG )

CAMERA_LOAD = 9917
CAMERA_LOAD_FAIL = 9918

class CameraSprite(object):
    """Create gstreamer surface for the camera."""
    def __init__(self, x, y):
        import olpcgames
        if olpcgames.WIDGET:
            self._init_video(olpcgames.WIDGET, x, y)
            
    def _init_video(self, widget, x, y):
        from olpcgames import video
        self._vid = video.VideoWidget()
        widget._fixed.put(self._vid, x, y)
        self._vid.show()
        
        self.player = video.Player(self._vid)
        self.player.play()
        
class Camera(object):
    """A class representing a still-picture camera
    
    Produces a simple gstreamer bus that terminates in a filesink, that is, 
    it stores the results in a file.  When a picture is "snapped" the gstreamer
    stream is iterated until it finishes processing and then the file can be 
    read.
    
    There are two APIs available, a synchronous API which can potentially 
    stall your activity's GUI (and is NOT recommended) and an 
    asynchronous API which returns immediately and delivers the captured 
    camera image via a Pygame event.  To be clear, it is recommended 
    that you use the snap_async method, *not* the snap method.
    
    Note:
    
        The Camera class is simply a convenience wrapper around a fairly 
        straightforward gstreamer bus.  If you have more involved 
        requirements for your camera manipulations you will probably 
        find it easier to write your own camera implementation than to 
        use this one.  Basically we provide here the "normal" use case of 
        snapping a picture into a pygame image.
    """
    _aliases = {
        'camera': 'v4l2src',
        'test': 'videotestsrc',
        'testing': 'videotestsrc',
        'png': 'pngenc',
        'jpeg': 'jpegenc',
        'jpg': 'jpegenc',
    }
    def __init__(self, source='camera', format='png', filename='snap.png', directory = None):
        """Initialises the Camera's internal description
        
        source -- the gstreamer source for the video to capture, useful values:
            'v4l2src','camera' -- the camera
            'videotestsrc','test' -- test pattern generator source
        format -- the gstreamer encoder to use for the capture, useful values:
            'pngenc','png' -- PNG format graphic
            'jpegenc','jpg','jpeg' -- JPEG format graphic
        filename -- the filename to use for the capture
        directory -- the directory in which to create the temporary file, defaults 
            to get_activity_root() + 'tmp'
        """
        self.source = self._aliases.get( source, source )
        self.format = self._aliases.get( format, format )
        self.filename = filename 
        self.directory = directory
    SNAP_PIPELINE = '%(source)s ! ffmpegcolorspace ! %(format)s ! filesink location="%(filename)s"'
    def _create_pipe( self ):
        """Method to create the cstreamer pipe from our settings"""
        if not self.directory:
            path = os.path.join( get_activity_root(), 'tmp' )
            try:
                os.makedirs( path )
                log.info( 'Created temporary directory: %s', path )
            except (OSError,IOError), err:
                pass
        else:
            path = self.directory
        filename = os.path.join( path, self.filename )
        format = self.format 
        source = self.source 
        pipeline = self.SNAP_PIPELINE % locals()
        log.debug( 'Background thread processing: %s', pipeline )
        return filename, gst.parse_launch(pipeline)
        
    def snap(self):
        """Snap a picture via the camera by iterating gstreamer until finished
        
        Note: this is an unsafe implementation, it will cause the whole 
        activity to hang if the operation happens to fail!  It is strongly 
        recommended that you use snap_async instead of snap!
        """
        log.debug( 'Starting snap' )
        filename, pipe = self._create_pipe()
        pipe.set_state(gst.STATE_PLAYING)
        bus = pipe.get_bus()
        tmp = False
        while True:
            event = self.bus.poll(gst.MESSAGE_STATE_CHANGED, 5)
            if event:
                old, new, pending = event.parse_state_changed()
                if pending == gst.STATE_VOID_PENDING:
                    if tmp:
                        break
                    else:
                        tmp = True
            else:
                break
        log.log( 'Ending snap, loading: %s', filename )
        return self._load_and_clean( filename )
    def _load_and_clean( self, filename ):
        """Use pygame to load given filename, delete after loading/attempt"""
        try:
            log.info( 'Loading snapshot file: %s', filename )
            return pygame.image.load(filename)
        finally:
            try:
                os.remove( filename )
            except (IOError,OSError), err:
                pass
    def snap_async( self, token=None ):
        """Snap a picture asynchronously generating event on success/failure
        
        token -- passed back as attribute of the event which signals that capture
            is finished
        
        We return two types of events CAMERA_LOAD and CAMERA_LOAD_FAIL,
        depending on whether we succeed or not.  Attributes of the events which 
        are returned:
        
            token -- as passed to this method 
            filename -- the filename in our temporary directory we used to store 
                the file temporarily 
            image -- pygame image.load result if successful, None otherwise
            err -- Exception instance if failed, None otherwise
        
        Basically identical to the snap method, save that it posts a message 
        to the event bus in eventwrap instead of blocking and returning...
        """
        log.debug( 'beginning async snap')
        t = threading.Thread(target=self._background_snap, args=(token,))
        t.start()
        log.debug( 'background thread started for gstreamer' )
        return token

    def _background_snap( 
        self,
        token = None,
    ):
        """Process gst messages until pipe is finished
        
        pipe -- gstreamer pipe definition for parse_launch, normally it will 
            produce a file into which the camera should store an image
        
        We consider pipe to be finished when we have had two "state changed"
        gstreamer events where the pending state is VOID, the first for when 
        we begin playing, the second for when we finish.
        """
        log.debug( 'Background thread kicking off gstreamer capture begun' )
        from olpcgames import eventwrap 
        from pygame.event import Event
        filename, pipe = self._create_pipe()
        bus = pipe.get_bus()
        bus.add_signal_watch()
        def _background_snap_onmessage( bus, message ):
            """Handle messages from the picture-snapping bus"""
            log.debug( 'Message handler for gst messages: %s', message )
            t = message.type
            if t == gst.MESSAGE_EOS:
                pipe.set_state(gst.STATE_NULL)
                try:
                    image = self._load_and_clean( filename )
                    success = True
                except Exception, err:
                    success = False
                    image = None 
                else:
                    err = None
                log.debug( 'Success loading file %r', token )
                eventwrap.post(Event(
                    CAMERA_LOAD, 
                    filename=filename, 
                    success = success,
                    token = token, 
                    image=image, 
                    err=err
                ))
                
            elif t == gst.MESSAGE_ERROR:
                log.warn( 'Failure loading file %r: %s', token, message )
                pipe.set_state(gst.STATE_NULL)
                err, debug = message.parse_error()
                eventwrap.post(Event(
                    CAMERA_LOAD_FAIL, 
                    filename=filename, 
                    success = False,
                    token = token, 
                    image=None, 
                    err=err
                ))
                return False
        bus.connect('message', _background_snap_onmessage)
        pipe.set_state(gst.STATE_PLAYING)

def snap():
    """Dump a snapshot from the camera to a pygame surface in background thread
    
    See Camera.snap
    """
    return Camera().snap()

def snap_async( token=None, **named ):
    """Dump snapshot from camera return asynchronously as event in Pygame
    
    See Camera.snap_async
    """
    return Camera(**named).snap_async( token )
