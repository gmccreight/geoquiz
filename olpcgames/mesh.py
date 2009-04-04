'''mesh.py: utilities for wrapping the mesh and making it accessible to Pygame'''
import logging
log = logging.getLogger( 'olpcgames.mesh' )
#log.setLevel( logging.DEBUG )
try:
    from sugar.presence.tubeconn import TubeConnection
except ImportError, err:
    TubeConnection = object
try:
    from dbus.gobject_service import ExportedGObject
except ImportError, err:
    ExportedGObject = object
from dbus.service import method, signal

try:
    import telepathy
except ImportError, err:
    telepathy = None

class OfflineError( Exception ):
    """Raised when we cannot complete an operation due to being offline"""

DBUS_IFACE="org.laptop.games.pygame"
DBUS_PATH="/org/laptop/games/pygame"
DBUS_SERVICE = None


### NEW PYGAME EVENTS ###

'''The tube connection was started. (i.e., the user clicked Share or started
the activity from the Neighborhood screen).
Event properties:
  id: a unique identifier for this connection. (shouldn't be needed for anything)'''
CONNECT            = 9912

'''A participant joined the activity. This will trigger for the local user
as well as any arriving remote users.
Event properties:
  handle: the arriving user's handle.'''
PARTICIPANT_ADD    = 9913

'''A participant quit the activity.
Event properties:
  handle: the departing user's handle.'''
PARTICIPANT_REMOVE = 9914

'''A message was sent to you.
Event properties:
   content: the content of the message (a string)
   handle: the handle of the sending user.'''
MESSAGE_UNI        = 9915

'''A message was sent to everyone.
Event properties:
   content: the content of the message (a string)
   handle: the handle of the sending user.'''
MESSAGE_MULTI      = 9916


# Private objects for useful purposes!
pygametubes = []
text_chan, tubes_chan = (None, None)
conn = None
initiating = False
joining = False

connect_callback = None

def is_initiating():
    '''A version of is_initiator that's a bit less goofy, and can be used
    before the Tube comes up.'''
    global initiating
    return initiating

def is_joining():
    '''Returns True if the activity was started up by means of the
    Neighbourhood mesh view.'''
    global joining
    return joining

def set_connect_callback(cb):
    '''Just the same as the Pygame event loop can listen for CONNECT,
    this is just an ugly callback that the glib side can use to be aware
    of when the Tube is ready.'''
    global connect_callback
    connect_callback = cb

def activity_shared(activity):
    '''Called when the user clicks Share.'''

    global initiating
    initiating = True

    _setup(activity)


    log.debug('This is my activity: making a tube...')
    channel = tubes_chan[telepathy.CHANNEL_TYPE_TUBES]
    if hasattr( channel, 'OfferDBusTube' ):
        id = channel.OfferDBusTube(
            DBUS_SERVICE, {})
    else:
        id = channel.OfferTube(
            telepathy.TUBE_TYPE_DBUS, DBUS_SERVICE, {})

    global connect_callback
    if connect_callback is not None:
        connect_callback()

def activity_joined(activity):
    '''Called at the startup of our Activity, when the user started it via Neighborhood intending to join an existing activity.'''

    # Find out who's already in the shared activity:
    log.debug('Joined an existing shared activity')

    for buddy in activity._shared_activity.get_joined_buddies():
        log.debug('Buddy %s is already in the activity' % buddy.props.nick)


    global initiating
    global joining
    initiating = False
    joining = True


    _setup(activity)

    tubes_chan[telepathy.CHANNEL_TYPE_TUBES].ListTubes(
        reply_handler=_list_tubes_reply_cb,
        error_handler=_list_tubes_error_cb)

    global connect_callback
    if connect_callback is not None:
        connect_callback()

def _getConn():
    log.info( '_getConn' )
    pservice = _get_presence_service()
    name, path = pservice.get_preferred_connection()
    global conn
    conn = telepathy.client.Connection(name, path)
    return conn



def _setup(activity):
    '''Determines text and tube channels for the current Activity. If no tube
channel present, creates one. Updates text_chan and tubes_chan.

setup(sugar.activity.Activity, telepathy.client.Connection)'''
    global text_chan, tubes_chan, DBUS_SERVICE
    if not DBUS_SERVICE:
        DBUS_SERVICE = activity.get_bundle_id()
    if not activity.get_shared():
        log.error('Failed to share or join activity')
        raise "Failure"

    bus_name, conn_path, channel_paths = activity._shared_activity.get_channels()
    _getConn()

    # Work out what our room is called and whether we have Tubes already
    room = None
    tubes_chan = None
    text_chan = None
    for channel_path in channel_paths:
        channel = telepathy.client.Channel(bus_name, channel_path)
        htype, handle = channel.GetHandle()
        if htype == telepathy.HANDLE_TYPE_ROOM:
            log.debug('Found our room: it has handle#%d "%s"',
                handle, conn.InspectHandles(htype, [handle])[0])
            room = handle
            ctype = channel.GetChannelType()
            if ctype == telepathy.CHANNEL_TYPE_TUBES:
                log.debug('Found our Tubes channel at %s', channel_path)
                tubes_chan = channel
            elif ctype == telepathy.CHANNEL_TYPE_TEXT:
                log.debug('Found our Text channel at %s', channel_path)
                text_chan = channel

    if room is None:
        log.error("Presence service didn't create a room")
        raise "Failure"
    if text_chan is None:
        log.error("Presence service didn't create a text channel")
        raise "Failure"

    # Make sure we have a Tubes channel - PS doesn't yet provide one
    if tubes_chan is None:
        log.debug("Didn't find our Tubes channel, requesting one...")
        tubes_chan = conn.request_channel(telepathy.CHANNEL_TYPE_TUBES,
            telepathy.HANDLE_TYPE_ROOM, room, True)

    tubes_chan[telepathy.CHANNEL_TYPE_TUBES].connect_to_signal('NewTube',
        new_tube_cb)

    return (text_chan, tubes_chan)

def new_tube_cb(id, initiator, type, service, params, state):
    log.debug("New_tube_cb called: %s %s %s" % (id, initiator, type))
    if (type == telepathy.TUBE_TYPE_DBUS and service == DBUS_SERVICE):
        if state == telepathy.TUBE_STATE_LOCAL_PENDING:
            channel = tubes_chan[telepathy.CHANNEL_TYPE_TUBES]
            if hasattr( channel, 'AcceptDBusTube' ):
                channel.AcceptDBusTube( id )
            else:
                channel.AcceptTube(id)

        tube_conn = TubeConnection(conn,
            tubes_chan[telepathy.CHANNEL_TYPE_TUBES],
            id, group_iface=text_chan[telepathy.CHANNEL_INTERFACE_GROUP])

        global pygametubes, initiating
        pygametubes.append(PygameTube(tube_conn, initiating, len(pygametubes)))


def _list_tubes_reply_cb(tubes):
    for tube_info in tubes:
        new_tube_cb(*tube_info)

def _list_tubes_error_cb(e):
    log.error('ListTubes() failed: %s', e)



def get_buddy(dbus_handle):
    """Get a Buddy from a handle."""
    log.debug('Trying to find owner of handle %s...', dbus_handle)
    cs_handle = instance().tube.bus_name_to_handle[dbus_handle]
    log.debug('Trying to find my handle in %s...', cs_handle)
    group = text_chan[telepathy.CHANNEL_INTERFACE_GROUP]
    log.debug( 'Calling GetSelfHandle' )
    my_csh = group.GetSelfHandle()
    log.debug('My handle in that group is %s', my_csh)
    if my_csh == cs_handle:
        handle = conn.GetSelfHandle()
        log.debug('CS handle %s belongs to me, %s', cs_handle, handle)
    elif group.GetGroupFlags() & telepathy.CHANNEL_GROUP_FLAG_CHANNEL_SPECIFIC_HANDLES:
        handle = group.GetHandleOwners([cs_handle])[0]
        log.debug('CS handle %s belongs to %s', cs_handle, handle)
    else:
        handle = cs_handle
        log.debug('non-CS handle %s belongs to itself', handle)

    # XXX: we're assuming that we have Buddy objects for all contacts -
    # this might break when the server becomes scalable.
    pservice = _get_presence_service()
    name, path = pservice.get_preferred_connection()
    return pservice.get_buddy_by_telepathy_handle(name, path, handle)

def _get_presence_service( ):
    """Attempt to retrieve the presence service (check for offline condition)

    The presence service, when offline, has no preferred connection type,
    so we check that before returning the object...
    """
    import sugar.presence.presenceservice
    pservice = sugar.presence.presenceservice.get_instance()
    try:
        name, path = pservice.get_preferred_connection()
    except (TypeError,ValueError), err:
        log.warn('Working in offline mode, cannot retrieve buddy information for %s: %s', handle, err )
        raise OfflineError( """Unable to retrieve buddy information, currently offline""" )
    else:
        return pservice

def instance(idx=0):
    return pygametubes[idx]

import eventwrap,pygame.event as PEvent

class PygameTube(ExportedGObject):
    '''The object whose instance is shared across D-bus

    Call instance() to get the instance of this object for your activity service.
    Its 'tube' property contains the underlying D-bus Connection.
    '''
    def __init__(self, tube, is_initiator, tube_id):
        super(PygameTube, self).__init__(tube, DBUS_PATH)
        log.info( 'PygameTube init' )
        self.tube = tube
        self.is_initiator = is_initiator
        self.entered = False
        self.ordered_bus_names = []
        eventwrap.post(PEvent.Event(CONNECT, id=tube_id))

        if not self.is_initiator:
            self.tube.add_signal_receiver(self.new_participant_cb, 'NewParticipants', DBUS_IFACE, path=DBUS_PATH)
        self.tube.watch_participants(self.participant_change_cb)
        self.tube.add_signal_receiver(self.broadcast_cb, 'Broadcast', DBUS_IFACE, path=DBUS_PATH, sender_keyword='sender')


    def participant_change_cb(self, added, removed):
        log.debug( 'participant_change_cb: %s %s', added, removed )
        def nick(buddy):
            if buddy is not None:
                return buddy.props.nick
            else:
                return 'Unknown'

        for handle, bus_name in added:
            dbus_handle = self.tube.participants[handle]
            self.ordered_bus_names.append(dbus_handle)
            eventwrap.post(PEvent.Event(PARTICIPANT_ADD, handle=dbus_handle))

        for handle in removed:
            dbus_handle = self.tube.participants[handle]
            self.ordered_bus_names.remove(dbus_handle)
            eventwrap.post(PEvent.Event(PARTICIPANT_REMOVE, handle=dbus_handle))

        if self.is_initiator:
            if not self.entered:
                # Initiator will broadcast a new ordered_bus_names each time
                # a participant joins.
                self.ordered_bus_names = [self.tube.get_unique_name()]
            self.NewParticipants(self.ordered_bus_names)

        self.entered = True

    @signal(dbus_interface=DBUS_IFACE, signature='as')
    def NewParticipants(self, ordered_bus_names):
        '''This is the NewParticipants signal, sent when the authoritative list of ordered_bus_names changes.'''
        log.debug("sending NewParticipants: %s" % ordered_bus_names)
        pass

    @signal(dbus_interface=DBUS_IFACE, signature='s')
    def Broadcast(self, content):
        '''This is the Broadcast signal; it sends a message to all other activity participants.'''
        pass

    @method(dbus_interface=DBUS_IFACE, in_signature='s', out_signature='', sender_keyword='sender')
    def Tell(self, content, sender=None):
        '''This is the targeted-message interface; called when a message is received that was sent directly to me.'''
        eventwrap.post(PEvent.Event(MESSAGE_UNI, handle=sender, content=content))

    def broadcast_cb(self, content, sender=None):
        '''This is the Broadcast callback, fired when someone sends a Broadcast signal along the bus.'''
        eventwrap.post(PEvent.Event(MESSAGE_MULTI, handle=sender, content=content))

    def new_participant_cb(self, new_bus_names):
        '''This is the NewParticipants callback, fired when someone joins or leaves.'''
        log.debug("new participant. new bus names %s, old %s" % (new_bus_names, self.ordered_bus_names))
        if self.ordered_bus_names != new_bus_names:
            log.warn("ordered bus names out of sync with server, resyncing")
            self.ordered_bus_names = new_bus_names

def send_to(handle, content=""):
    '''Sends the given message to the given buddy identified by handle.'''
    log.debug( 'send_to: %s %s', handle, content )
    remote_proxy = dbus_get_object(handle, DBUS_PATH)
    remote_proxy.Tell(content, reply_handler=dbus_msg, error_handler=dbus_err)

def dbus_msg():
    log.debug("async reply to send_to")
def dbus_err(e):
    log.error("async error: %s" % e)

def broadcast(content=""):
    '''Sends the given message to all participants.'''
    log.debug( 'Broadcast: %s', content )
    instance().Broadcast(content)

def my_handle():
    '''Returns the handle of this user
    
    Note, you can get a DBusException from this if you have 
    not yet got a unique ID assigned by the bus.  You may need 
    to delay calling until you are sure you are connected.
    '''
    log.debug( 'my handle' )
    return instance().tube.get_unique_name()

def is_initiator():
    '''Returns the handle of this user.'''
    log.debug( 'is initiator' )
    return instance().is_initiator

def get_participants():
    '''Returns the list of active participants, in order of arrival.
    List is maintained by the activity creator; if that person leaves it may not stay in sync.'''
    log.debug( 'get_participants' )
    try:
        return instance().ordered_bus_names[:]
    except IndexError, err:
        return [] # no participants yet, as we don't yet have a connection

def dbus_get_object(handle, path):
    '''Get a D-bus object from another participant.

    This is how you can communicate with other participants using
    arbitrary D-bus objects without having to manage the participants
    yourself.

    Simply define a D-bus class with an interface and path that you
    choose; when you want a reference to the corresponding remote
    object on a participant, call this method.
    '''
    log.debug( 'dbus_get_object: %s %s', handle, path )
    return instance().tube.get_object(handle, path)
