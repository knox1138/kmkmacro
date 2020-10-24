import busio

from kmk.extensions import Extension
from kmk.matrix import intify_coordinate


class SplitType:
    UART = 1
    I2C = 2  # unused
    ONEWIRE = 3  # unused
    BLE = 4  # unused


class Split(Extension):
    def __init__(
        self,
        extra_data_pin=None,
        split_offsets=None,
        split_flip=True,
        split_side=None,
        split_type=SplitType.UART,
        target_left=True,
        uart_flip=True,
        uart_pin=None,
        uart_timeout=20,
    ):
        self.extra_data_pin = extra_data_pin
        self.split_offsets = split_offsets
        self.split_flip = split_flip
        self.split_side = split_side
        self.split_type = split_type
        self.split_target_left = target_left
        self._uart = None
        self._uart_buffer = []
        self.uart_flip = uart_flip
        self.uart_pin = uart_pin
        self.uart_timeout = uart_timeout

    def during_bootup(self, keyboard):
        try:
            # Working around https://github.com/adafruit/circuitpython/issues/1769
            # keyboard._hid_helper_inst.create_report([]).send()
            # Line above is broken and needs fixed for aut detection
            self._is_target = True
        except OSError:
            self._is_target = False

        if self.split_flip and not self._is_target:
            keyboard.col_pins = list(reversed(keyboard.col_pins))
        if self.split_side == 'Left':
            self.split_target_left = self._is_target
        elif self.split_side == 'Right':
            self.split_target_left = not self._is_target

        if self.uart_pin is not None:
            if self._is_target:
                self._uart = busio.UART(
                    tx=None, rx=self.uart_pin, timeout=self.uart_timeout
                )
            else:
                self._uart = busio.UART(
                    tx=self.uart_pin, rx=None, timeout=self.uart_timeout
                )
        # Attempt to sanely guess a coord_mapping if one is not provided.
        if not keyboard.coord_mapping:
            keyboard.coord_mapping = []

            rows_to_calc = len(keyboard.row_pins)
            cols_to_calc = len(keyboard.col_pins)

            if self.split_offsets:
                rows_to_calc *= 2
                cols_to_calc *= 2

            for ridx in range(rows_to_calc):
                for cidx in range(cols_to_calc):
                    keyboard.coord_mapping.append(intify_coordinate(ridx, cidx))

    def before_matrix_scan(self, keyboard_state):
        if self.split_type is not None and self._is_target:
            return self._receive_from_initiator()

    def after_matrix_scan(self, keyboard_state, matrix_update):
        if matrix_update is not None and not self._is_target:
            self._send_to_target(matrix_update)

    def _send_to_target(self, update):
        if self.split_target_left:
            update[1] += self.split_offsets[update[0]]
        else:
            update[1] -= self.split_offsets[update[0]]
        if self._uart is not None:
            self._uart.write(update)

    def _receive_from_initiator(self):
        if self._uart is not None and self._uart.in_waiting > 0 or self._uart_buffer:
            if self._uart.in_waiting >= 60:
                # This is a dirty hack to prevent crashes in unrealistic cases
                import microcontroller

                microcontroller.reset()

            while self._uart.in_waiting >= 3:
                self._uart_buffer.append(self._uart.read(3))
            if self._uart_buffer:
                update = bytearray(self._uart_buffer.pop(0))

                return update

        return None
