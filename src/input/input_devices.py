"""Input device classes for handling different types of user input."""

import pygame


class InputDevice:
    """Base class for all input devices."""
    
    def __init__(self, handlers):
        self.handlers = handlers
        self._player_number = None
        self.current_guess = ""
        self.reversed = False
        self.id = None

    @property
    def player_number(self):
        return self._player_number

    @player_number.setter
    def player_number(self, value):
        self._player_number = value
        self.reversed = (value == 1)

    async def process_event(self, event):
        """Base method to be overridden by subclasses"""
        pass


class CubesInput(InputDevice):
    """Input device for physical cube hardware."""
    
    def __str__(self):
        return "CubesInput"
    
    async def process_event(self, event):
        pass


class KeyboardInput(InputDevice):
    """Input device for keyboard input."""
    
    def __str__(self):
        return "KeyboardInput"
    
    async def process_event(self, event):
        # Keyboard input is handled separately in the main loop
        pass


class GamepadInput(InputDevice):
    """Input device for standard USB gamepad."""
    
    def __str__(self):
        return "GamepadInput"

    async def process_event(self, event, now_ms: int):
        if event["type"] == "JOYBUTTONDOWN" and event["button"] == 9:
            self.player_number = await self.handlers['start'](self, now_ms)
            print(f"JOYSTICK player_number: {self.player_number}")
            return

        if self.player_number is None:
            return

        if event["type"] == "JOYAXISMOTION":
            if event["axis"] == 0:
                if event["value"] < -0.5:
                    self.handlers['left'](self)
                elif event["value"] > 0.5:
                    self.handlers['right'](self)
            elif event["axis"] == 1:
                if event["value"] < -0.5:
                    await self.handlers['insert'](self, now_ms)
                elif event["value"] > 0.5:
                    await self.handlers['delete'](self, now_ms)
        elif event["type"] == "JOYBUTTONDOWN":
            if event["button"] == 1:
                await self.handlers['action'](self, now_ms)
            elif event["button"] == 2:
                self.handlers['return'](self)


class DDRInput(InputDevice):
    """Input device for DDR-style dance pad."""
    
    def __str__(self):
        return "DDRInput"
    
    async def process_event(self, event):
        if event.type == pygame.JOYBUTTONDOWN:
            if event.button == 9:
                self.player_number = await self.handlers['start'](self)

            if self.player_number is None:
                return
            if event.button == 1:
                await self.handlers['action'](self)
            elif event.button == 0:
                self.handlers['left'](self)
            elif event.button == 2:
                await self.handlers['action'](self)
            elif event.button == 3:
                self.handlers['right'](self)
            elif event.button == 5:
                self.handlers['return'](self)


# Mapping of joystick names to input device classes
JOYSTICK_NAMES_TO_INPUTS = {
    "USB gamepad": GamepadInput,
    "USB Gamepad": DDRInput,
}