import logging
import traceback
from os import getenv
from threading import Lock

import zmq
from pitop.common.ptdm import Message

logger = logging.getLogger(__name__)


# Creates a server for clients to connect to,
# and publishes state change messages to these clients
class PublishServer:
    def __init__(self):
        self.emit_messages = False
        self._socket_lock = Lock()
        self._shutting_down = False
        self._zmq_context = None
        self._zmq_socket = None
        self._enable_battery_logging = getenv("PT_LOG_BATTERY_CHANGE", "0") == "1"

    def start_listening(self):
        logger.debug("Opening publisher socket...")

        try:
            self._socket_lock.acquire()

            self._zmq_context = zmq.Context()
            self._zmq_socket = self._zmq_context.socket(zmq.PUB)
            self._zmq_socket.bind("tcp://*:3781")
            logger.debug("Publish server ready...")

            return True

        except zmq.error.ZMQError as e:
            logger.error("Error starting the publish server: " + str(e))
            logger.info(traceback.format_exc())

            return False

        finally:
            self._socket_lock.release()

    def stop_listening(self):
        logger.debug("Closing publisher socket...")

        try:
            self._socket_lock.acquire()
            self._shutting_down = True

            if self._zmq_socket is not None:
                self._zmq_socket.close()
                self._zmq_context.destroy()
            logger.debug("Closed publisher socket.")

        except zmq.error.ZMQError as e:
            logger.error("Error starting the publish server: " + str(e))
            logger.info(traceback.format_exc())

        finally:
            self._socket_lock.release()

    def publish_brightness_changed(self, new_brightness: int):
        PublishServer._check_type(new_brightness, int)
        self._send_message(Message.PUB_BRIGHTNESS_CHANGED, [new_brightness])

    def publish_peripheral_connected(self, peripheral_id: int):
        PublishServer._check_type(peripheral_id, int)
        self._send_message(Message.PUB_PERIPHERAL_CONNECTED, [peripheral_id])

    def publish_peripheral_disconnected(self, peripheral_id: int):
        PublishServer._check_type(peripheral_id, int)
        self._send_message(Message.PUB_PERIPHERAL_DISCONNECTED, [peripheral_id])

    def publish_unsupported_hardware(self):
        self._send_message(Message.PUB_UNSUPPORTED_HARDWARE)

    def publish_shutdown_requested(self):
        self._send_message(Message.PUB_SHUTDOWN_REQUESTED)

    def publish_reboot_required(self):
        self._send_message(Message.PUB_REBOOT_REQUIRED)

    def publish_battery_state_changed(
        self, connected: int, new_capacity: int, new_time: int, new_wattage: int
    ):
        PublishServer._check_type(connected, int)
        PublishServer._check_type(new_capacity, int)
        PublishServer._check_type(new_time, int)
        PublishServer._check_type(new_wattage, int)
        self._send_message(
            Message.PUB_BATTERY_STATE_CHANGED,
            [connected, new_capacity, new_time, new_wattage],
            log_message=self._enable_battery_logging,
        )

    def publish_screen_blanked(self):
        self._send_message(Message.PUB_SCREEN_BLANKED)

    def publish_screen_unblanked(self):
        self._send_message(Message.PUB_SCREEN_UNBLANKED)

    def publish_low_battery_warning(self):
        self._send_message(Message.PUB_LOW_BATTERY_WARNING)

    def publish_critical_battery_warning(self):
        self._send_message(Message.PUB_CRITICAL_BATTERY_WARNING)

    def publish_lid_opened(self):
        self._send_message(Message.PUB_LID_OPENED)

    def publish_lid_closed(self):
        self._send_message(Message.PUB_LID_CLOSED)

    def publish_up_button_press_state_changed(self, is_pressed):
        if is_pressed:
            self._send_message(Message.PUB_V3_BUTTON_UP_PRESSED)
        else:
            self._send_message(Message.PUB_V3_BUTTON_UP_RELEASED)

    def publish_down_button_press_state_changed(self, is_pressed):
        if is_pressed:
            self._send_message(Message.PUB_V3_BUTTON_DOWN_PRESSED)
        else:
            self._send_message(Message.PUB_V3_BUTTON_DOWN_RELEASED)

    def publish_select_button_press_state_changed(self, is_pressed):
        if is_pressed:
            self._send_message(Message.PUB_V3_BUTTON_SELECT_PRESSED)
        else:
            self._send_message(Message.PUB_V3_BUTTON_SELECT_RELEASED)

    def publish_cancel_button_press_state_changed(self, is_pressed):
        if is_pressed:
            self._send_message(Message.PUB_V3_BUTTON_CANCEL_PRESSED)
        else:
            self._send_message(Message.PUB_V3_BUTTON_CANCEL_RELEASED)

    def publish_oled_pi_controlled_state_changed(self, oled_controlled_by_pi):
        self._send_message(
            Message.PUB_OLED_CONTROL_CHANGED, [1 if oled_controlled_by_pi else 0]
        )

    def publish_oled_spi_state_changed(self, oled_uses_spi0):
        self._send_message(
            Message.PUB_OLED_SPI_BUS_CHANGED, [0 if oled_uses_spi0 else 1]
        )

    def publish_pitopd_ready(self):
        self._send_message(Message.PUB_PITOPD_READY)

    # Internal functions
    def _send_message(self, message_id, parameters=None, log_message=True):
        if parameters is None:
            parameters = list()
        message = Message.from_parts(message_id, parameters)

        if self._zmq_socket is None or not self.emit_messages:
            msg = f"Not publishing message: {message.message_friendly_string()}"
            msg += (
                " - publish server not ready"
                if self._zmq_socket is None
                else " - pi-topd not initialized"
            )
            logger.info(msg)
            return

        if log_message:
            logger.info("Publishing message: " + message.message_friendly_string())

        try:
            self._socket_lock.acquire()
            if self._shutting_down is True:
                return

            self._zmq_socket.send_string(message.to_string())
            logger.debug("Published message: " + message.message_friendly_string())

        except zmq.error.ZMQError as e:
            logger.error("Communication error in publish server: " + str(e))
            logger.info(traceback.format_exc())

        finally:
            self._socket_lock.release()

    @staticmethod
    def _check_type(var, var_type):
        if isinstance(var, var_type) is False:
            raise TypeError("Wrong type to be sent in message")
