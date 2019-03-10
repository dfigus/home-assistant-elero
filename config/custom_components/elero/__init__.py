"""
Support for Elero electrical drives.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/elero/
"""
import logging

import homeassistant.helpers.config_validation as cv
import serial
import voluptuous as vol
from homeassistant.const import CONF_PORT, EVENT_HOMEASSISTANT_STOP

# Python libraries/modules that you would normally install for your component.
REQUIREMENTS = ['pyserial==3.4']

# Other HASS components that should be setup before the platform is loaded.
DEPENDENCIES = []

_LOGGER = logging.getLogger(__name__)

# The domain of your component. Equal to the filename of your component.
DOMAIN = 'elero'

# The Transmitter device.
ELERO_TRANSMITTERS = None

# Configs to the serial connection.
CONF_TRANSMITTERS = 'transmitters'
CONF_TRANSMITTER_ID = 'transmitter_id'
CONF_BAUDRATE = 'baudrate'
CONF_BYTESIZE = 'bytesize'
CONF_PARITY = 'parity'
CONF_STOPBITS = 'stopbits'

# Default serial connection details.
DEFAULT_PORT = '/dev/ttyUSB0'
DEFAULT_BAUDRATE = 38400
DEFAULT_BYTESIZE = serial.EIGHTBITS
DEFAULT_PARITY = serial.PARITY_NONE
DEFAULT_STOPBITS = serial.STOPBITS_ONE

# values to bit shift.
HEX_255 = 0xFF
BIT_8 = 8

# Header for all command.
BYTE_HEADER = 0xAA
# command lengths
BYTE_LENGTH_2 = 0x02
BYTE_LENGTH_4 = 0x04
BYTE_LENGTH_5 = 0x05

# Wich channels are learned.
COMMAND_CHECK = 0x4A
# required response lenth.
RESPONSE_LENGTH_CHECK = 6
# The Playload will be send to all channel with bit set.
COMMAND_SEND = 0x4C
# required response lenth.
RESPONSE_LENGTH_SEND = 7
# Get the status or position of the channel.
COMMAND_INFO = 0x4E
# Required response lenth.
RESPONSE_LENGTH_INFO = 7
# for Serial error handling
NO_SERIAL_RESPONSE = b''

# Playloads to send.
PAYLOAD_STOP = 0x10
PAYLOAD_STOP_TEXT = "stop"
PAYLOAD_UP = 0x20
PAYLOAD_UP_TEXT = "up"
PAYLOAD_VENTILATION_POS_TILTING = 0x24
PAYLOAD_VENTILATION_POS_TILTING_TEXT = "ventilation position/tilting"
PAYLOAD_DOWN = 0x40
PAYLOAD_DOWN_TEXT = "down"
PAYLOAD_INTERMEDIATE_POS = 0x44
PAYLOAD_INTERMEDIATE_POS_TEXT = "intermediate position/tilting"

# Info to receive response.
INFO_UNKNOWN = "unknown response"
INFO_NO_INFORMATION = "no information"
INFO_TOP_POSITION_STOP = "top position stop"
INFO_BOTTOM_POSITION_STOP = "bottom position stop"
INFO_INTERMEDIATE_POSITION_STOP = "intermediate position stop"
INFO_TILT_VENTILATION_POS_STOP = "tilt ventilation position stop"
INFO_BLOCKING = "blocking"
INFO_OVERHEATED = "overheated"
INFO_TIMEOUT = "timeout"
INFO_START_TO_MOVE_UP = "start to move up"
INFO_START_TO_MOVE_DOWN = "start to move down"
INFO_MOVING_UP = "moving up"
INFO_MOVING_DOWN = "moving down"
INFO_STOPPED_IN_UNDEFINED_POSITION = "stopped in undefined position"
INFO_TOP_POS_STOP_WICH_TILT_POS = "top position stop wich is tilt position"
INFO_BOTTOM_POS_STOP_WICH_INT_POS = \
    "bottom position stop wich is intermediate position"
INFO_SWITCHING_DEVICE_SWITCHED_OFF = "switching device switched off"
INFO_SWITCHING_DEVICE_SWITCHED_ON = "switching device switched on"

INFO = {0x00: INFO_NO_INFORMATION,
        0x01: INFO_TOP_POSITION_STOP,
        0x02: INFO_BOTTOM_POSITION_STOP,
        0x03: INFO_INTERMEDIATE_POSITION_STOP,
        0x04: INFO_TILT_VENTILATION_POS_STOP,
        0x05: INFO_BLOCKING,
        0x06: INFO_OVERHEATED,
        0x07: INFO_TIMEOUT,
        0x08: INFO_START_TO_MOVE_UP,
        0x09: INFO_START_TO_MOVE_DOWN,
        0x0A: INFO_MOVING_UP,
        0x0B: INFO_MOVING_DOWN,
        0x0D: INFO_STOPPED_IN_UNDEFINED_POSITION,
        0x0E: INFO_TOP_POS_STOP_WICH_TILT_POS,
        0x0F: INFO_BOTTOM_POS_STOP_WICH_INT_POS,
        0x10: INFO_SWITCHING_DEVICE_SWITCHED_OFF,
        0x11: INFO_SWITCHING_DEVICE_SWITCHED_ON,
        }

ELERO_TRANSMITTER_SCHEMA = vol.Schema({
    vol.Required(CONF_TRANSMITTER_ID): cv.positive_int,
    vol.Required(CONF_PORT, default=DEFAULT_PORT): str,
    vol.Optional(CONF_BAUDRATE, default=DEFAULT_BAUDRATE): cv.positive_int,
    vol.Optional(CONF_BYTESIZE, default=DEFAULT_BYTESIZE): cv.positive_int,
    vol.Optional(CONF_PARITY, default=DEFAULT_PARITY): str,
    vol.Optional(CONF_STOPBITS, default=DEFAULT_STOPBITS): cv.positive_int,
})

# Validation of the user's configuration.
CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_TRANSMITTERS): [ELERO_TRANSMITTER_SCHEMA],
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up is called when Home Assistant is loading our component."""
    global ELERO_TRANSMITTERS
    ELERO_TRANSMITTERS = EleroTransmitters()
    elero_config = config.get(DOMAIN)
    for transmitter in elero_config.get(CONF_TRANSMITTERS):
        transmitter_id = transmitter.get(CONF_TRANSMITTER_ID)
        elero_transmitter = EleroTransmitter(transmitter_id,
                                             transmitter.get(CONF_PORT),
                                             transmitter.get(CONF_BAUDRATE),
                                             transmitter.get(CONF_BYTESIZE),
                                             transmitter.get(CONF_PARITY),
                                             transmitter.get(CONF_STOPBITS))
        if elero_transmitter.get_transmitter_state():
            ELERO_TRANSMITTERS.add_trasmitter(transmitter_id,
                                              elero_transmitter)

    def close_serial_ports():
        """Close the serial port."""
        ELERO_TRANSMITTERS.close_transmitters()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, close_serial_ports)

    # Return boolean to indicate that initialization was successfully.
    return True


class EleroTransmitters(object):
    """Representation of an Elero Centero USB Transmitter Stick."""

    def __init__(self):
        """Initialize the usb sticks."""
        self.transmitters = {}

    def add_trasmitter(self, transmitter_id, transmitter):
        """Store a transmitter."""
        if transmitter_id not in self.transmitters:
            self.transmitters[transmitter_id] = transmitter
        else:
            _LOGGER.error("Elero - '%s' transmitter ID is already added!",
                          transmitter_id)

    def get_transmitter(self, transmitter_id):
        """Return the given transmitter."""
        if transmitter_id in self.transmitters:
            return self.transmitters[transmitter_id]
        else:
            _LOGGER.error("Elero - the transmitter ID '%s' is not exist!",
                          transmitter_id)
            return None

    def close_transmitters(self):
        """Close the serial connection of the transmitters."""
        for id, t in self.transmitters.items():
            t.close_serial()


class EleroTransmitter(object):
    """Representation of an Elero Centero USB Transmitter Stick."""

    def __init__(self, transmitter_id, port, baudrate, bytesize, parity,
                 stopbits):
        """Initialization of a elero transmitter."""
        self._transmitter_id = transmitter_id
        self._port = port
        self._baudrate = baudrate
        self._bytesize = bytesize
        self._parity = parity
        self._stopbits = stopbits
        # setup the serial connection to the transmitter
        self._serial = None
        self._init_serial()
        # response data container
        self._reset_response()
        # get the learned channels from the transmitter
        self._learned_channels = set()
        if self._serial:
            self.check()

    def _init_serial(self):
        """Init the serial port to the transmitter."""
        try:
            self._serial = serial.Serial(self._port, self._baudrate,
                                         self._bytesize, self._parity,
                                         self._stopbits)
        except serial.serialutil.SerialException as exc:
            _LOGGER.exception("Elero - Unable to open serial port for '%s' to"
                              "Elero USB Stick: '%s'",
                              self._transmitter_id, exc)

    def close_serial(self):
        """Close the serial connection of the transmitter."""
        self._serial.close()

    def get_transmitter_state(self):
        """The transmitter is usable or not."""
        return True if self._serial else False

    def _reset_response(self):
        """Reset the response container."""
        self._response = {'bytes': None,
                          'header': None,
                          'length': None,
                          'command': None,
                          'ch_h': None,
                          'ch_l': None,
                          'chs': set(),
                          'status': None,
                          'cs': None,
                          }

    def get_transmitter_id(self):
        """Return the ID of the transmitter."""
        return self._transmitter_id

    def _get_check_command(self):
        """Create a hex list to Check command."""
        int_list = [BYTE_HEADER, BYTE_LENGTH_2,
                    COMMAND_CHECK]
        return int_list

    def check(self):
        """Wich channels are learned.

        Should be received an answer "Easy Confirm" with in 1 second.
        """
        self._send_command(self._get_check_command(), 0)
        ser_resp = self._read_response(RESPONSE_LENGTH_CHECK, 0)
        self._parse_response(ser_resp, 0)
        self._learned_channels = self._response['chs']
        self._reset_response()

    def is_learned_channel(self, channels):
        """Verify the given channel is learned or not."""
        if channels & self._learned_channels:
            return True
        else:
            return True

    def _get_info_command(self, channels):
        """Create a hex list to the Info command."""
        int_list = [BYTE_HEADER, BYTE_LENGTH_4,
                    COMMAND_INFO,
                    self._set_upper_channel_bits(channels),
                    self._set_lower_channel_bits(channels)]
        return int_list

    def info(self, channels):
        """Return the current state of the cover.

        Should be received an answer "Easy Act" with in 4 seconds.
        """
        self._send_command(self._get_info_command(channels), channels)

    def _get_up_command(self, channels):
        """Create a hex list to Open command."""
        int_list = [BYTE_HEADER, BYTE_LENGTH_5,
                    COMMAND_SEND,
                    self._set_upper_channel_bits(channels),
                    self._set_lower_channel_bits(channels),
                    PAYLOAD_UP]
        return int_list

    def up(self, channels):
        """Open the cover.

        Should be received an answer "Easy Act" with in 4 seconds.
        """
        self._send_command(self._get_up_command(channels), channels)

    def _get_down_command(self, channels):
        """Create a hex list to Close command."""
        int_list = [BYTE_HEADER, BYTE_LENGTH_5,
                    COMMAND_SEND,
                    self._set_upper_channel_bits(channels),
                    self._set_lower_channel_bits(channels),
                    PAYLOAD_DOWN]
        return int_list

    def down(self, channels):
        """Close the cover.

        Should be received an answer "Easy Act" with in 4 seconds.
        """
        self._send_command(self._get_down_command(channels), channels)

    def _get_stop_command(self, channels):
        """Create a hex list to the Stop command."""
        int_list = [BYTE_HEADER, BYTE_LENGTH_5,
                    COMMAND_SEND,
                    self._set_upper_channel_bits(channels),
                    self._set_lower_channel_bits(channels),
                    PAYLOAD_STOP]
        return int_list

    def stop(self, channels):
        """Stop the cover.

        Should be received an answer "Easy Act" with in 4 seconds.
        """
        self._send_command(self._get_stop_command(channels), channels)

    def _get_intermediate_command(self, channels):
        """Create a hex list to the intermediate command."""
        int_list = [BYTE_HEADER, BYTE_LENGTH_5,
                    COMMAND_SEND,
                    self._set_upper_channel_bits(channels),
                    self._set_lower_channel_bits(channels),
                    PAYLOAD_INTERMEDIATE_POS]
        return int_list

    def intermediate(self, channels):
        """Set the cover in intermediate position.

        Should be received an answer "Easy Act" with in 4 seconds.
        """
        self._send_command(self._get_intermediate_command(channels), channels)

    def _get_ventilation_tilting_command(self, channels):
        """Create a hex list to the ventilation command."""
        int_list = [BYTE_HEADER, BYTE_LENGTH_5,
                    COMMAND_SEND,
                    self._set_upper_channel_bits(channels),
                    self._set_lower_channel_bits(channels),
                    PAYLOAD_VENTILATION_POS_TILTING]
        return int_list

    def ventilation_tilting(self, channels):
        """Set the cover in ventilation position.

        Should be received an answer "Easy Act" with in 4 seconds.
        """
        self._send_command(self._get_ventilation_tilting_command(channels),
                           channels)

    def _read_response(self, resp_length, channels):
        """Get the serial data from the serial port."""
        if not self._serial.isOpen():
            self._serial.open()
        ser_resp = self._serial.read(resp_length)
        _LOGGER.debug("Elero - transmitter: '%s' ch: '%s' "
                      "serial response: '%s'",
                      self._transmitter_id, channels, ser_resp)
        return ser_resp

    def _parse_response(self, ser_resp, channels):
        """Parse the serial data as a response."""
        self._reset_response()
        self._response['bytes'] = ser_resp
        # No response or serial data
        if not ser_resp:
            self._response['status'] = INFO_NO_INFORMATION
            return
        resp_length = len(ser_resp)
        # Common parts
        self._response['header'] = ser_resp[0]
        self._response['length'] = ser_resp[1]
        self._response['command'] = ser_resp[2]
        self._response['ch_h'] = self._get_upper_channel_bits(ser_resp[3])
        self._response['ch_l'] = self._get_lower_channel_bits(ser_resp[4])
        self._response['chs'] = set(
            self._response['ch_h'] + self._response['ch_l'])
        # Easy Confirmed (the answer on Easy Check)
        if resp_length == RESPONSE_LENGTH_CHECK:
            self._response['cs'] = ser_resp[5]
        # Easy Ack (the answer on Easy Info)
        elif resp_length == RESPONSE_LENGTH_SEND:
            if ser_resp[5] in INFO:
                self._response['status'] = INFO[ser_resp[5]]
            else:
                self._response['status'] = INFO_UNKNOWN
                _LOGGER.warning("Elero - transmitter: '%s' ch: '%s' "
                                "status is unknown: '%s'",
                                self._transmitter_id, channels,
                                ser_resp[5])
            self._response['cs'] = ser_resp[6]
        else:
            _LOGGER.warning("Elero - transmitter: '%s' ch: '%s' "
                            "unknown response: '%s'",
                            self._transmitter_id, channels, ser_resp)
            self._response['status'] = INFO_UNKNOWN

    def get_response(self, resp_length, channels):
        """Read the response form the device."""
        ser_resp = self._read_response(resp_length, channels)
        self._parse_response(ser_resp, channels)
        return self._response

    def _send_command(self, int_list, channels):
        """Write out a command to the serial port."""
        int_list.append(self._calculate_checksum(*int_list))
        bytes_data = self._create_serial_data(int_list)
        _LOGGER.debug("Elero - transmitter: '%s' ch: '%s' "
                      "serial command: '%s'",
                      self._transmitter_id, channels, bytes_data)
        if not self._serial.isOpen():
            self._serial.open()
        self._serial.write(bytes_data)

    def _calculate_checksum(self, *args):
        """Calculate checksum.

        All the sum of all bytes (Header to CS) must be 0x00.
        """
        return (256 - sum(args)) % 256

    def _create_serial_data(self, int_list):
        """Convert integers to bytes for serial communication."""
        bytes_data = bytes(int_list)
        return bytes_data

    def _set_upper_channel_bits(self, channels):
        """Set upper channel bits, for channel 9 to 15."""
        res = 0
        for ch in channels:
            res |= (1 << (ch-1)) >> BIT_8
        return res

    def _set_lower_channel_bits(self, channels):
        """Set lower channel bits, for channel 1 to 8."""
        res = 0
        for ch in channels:
            res |= (1 << (ch-1)) & HEX_255
        return res

    def _get_upper_channel_bits(self, byt):
        """The set channel numbers from 9 to 15."""
        channels = []
        for i in range(0, 8):
            if (byt >> i) & 1 == 1:
                ch = i + 9
                channels.append(ch)

        return tuple(channels)

    def _get_lower_channel_bits(self, byt):
        """The set channel numbers from 1 to 8."""
        channels = []
        for i in range(0, 8):
            if (byt >> i) & 1 == 1:
                ch = i + 1
                channels.append(ch)

        return tuple(channels)

    def _get_learned_channels(self, byt):
        """The set channel numbers based on the bit mask."""
        channels = []
        for i in range(0, 16):
            if (byt >> i) & 1 == 1:
                ch = i + 1
                channels.append(ch)

        return tuple(channels)

    def verify_channels(self, channels):
        """Compare the response channel and the channel of the device.

        The answer is for this channel.
        """
        # TODO: check if the transmitter bug has disappeared
        if channels == self._response['chs']:
            return True
        else:
            _LOGGER.warning("Elero - the channels are not matched! "
                            "HA ch: '%s' response ch: '%s'",
                            channels, self._response['chs'])
            return False