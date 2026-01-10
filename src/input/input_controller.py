import asyncio
import logging
from typing import Dict, Any, Callable
from game.game_state import Game
from input.input_devices import InputDevice
from core import tiles

logger = logging.getLogger(__name__)

class GameInputController:
    """
    Handles input events and translates them into game actions.
    Extracted from BlockWordsPygame to improve testability and separation of concerns.
    """
    def __init__(self, game: Game):
        self.game = game

    def handle_left_movement(self, input_device: InputDevice):
        if not self.game.running:
            return
        rack = self.game.racks[input_device.player_number]
        if rack.cursor_position > 0:
            rack.cursor_position -= 1
            rack.draw()
            self.game.sound_manager.play_left()

    def handle_right_movement(self, input_device: InputDevice):
        if not self.game.running:
            return
        rack = self.game.racks[input_device.player_number]
        if rack.cursor_position < tiles.MAX_LETTERS - 1:
            rack.cursor_position += 1
            rack.draw()
            self.game.sound_manager.play_right()

    async def handle_insert_action(self, input_device: InputDevice, now_ms: int):
        if not self.game.running:
            return
        rack = self.game.racks[input_device.player_number]
        if input_device.reversed != (rack.cursor_position >= len(input_device.current_guess)):
            # Insert letter at cursor position into the guess
            letter_at_cursor = rack.letters()[rack.cursor_position]
            input_device.current_guess += letter_at_cursor
            self.game.sound_manager.play_add()
        await self.game._app.guess_word_keyboard(input_device.current_guess, input_device.player_number, now_ms)

    async def handle_delete_action(self, input_device: InputDevice, now_ms: int):
        if not self.game.running:
            return
        rack = self.game.racks[input_device.player_number]
        if input_device.reversed != (rack.cursor_position < len(input_device.current_guess)):
            # Remove letter at cursor position from the guess
            input_device.current_guess = input_device.current_guess[:rack.cursor_position] + input_device.current_guess[rack.cursor_position + 1:]
            if rack.select_count > 0:
                self.game.sound_manager.play_erase()
        rack.select_count = len(input_device.current_guess)
        if rack.select_count == 0:
            self.game.sound_manager.play_cleared()
        await self.game._app.guess_word_keyboard(input_device.current_guess, input_device.player_number, now_ms)

    async def handle_space_action(self, input_device: InputDevice, now_ms: int):
        if not self.game.running:
            return

        rack = self.game.racks[input_device.player_number]
        rack_position = rack.cursor_position if not input_device.reversed else 5 - rack.cursor_position
        if rack_position >= len(input_device.current_guess):
            # Insert letter at cursor position into the guess
            letter_at_cursor = rack.letters()[rack.cursor_position]
            input_device.current_guess += letter_at_cursor
            self.game.sound_manager.play_add()
        else:
            # Remove letter at cursor position from the guess
            if input_device.reversed:
                letter_to_remove = len(input_device.current_guess) - rack_position
                input_device.current_guess = input_device.current_guess[:letter_to_remove-1] + input_device.current_guess[letter_to_remove:]
            else:
                letter_to_remove = rack_position
                input_device.current_guess = input_device.current_guess[:letter_to_remove] + input_device.current_guess[letter_to_remove + 1:]
            if rack.select_count > 0:
                self.game.sound_manager.play_erase()
        rack.select_count = len(input_device.current_guess)
        if rack.select_count == 0:
            self.game.sound_manager.play_cleared()
        await self.game._app.guess_word_keyboard(input_device.current_guess, input_device.player_number, now_ms)

    async def start_game(self, input_device: InputDevice, now_ms: int):
        print(f"=========start_game {input_device} {now_ms}")
        input_device.current_guess = ""
        player_number = await self.game.start(input_device, now_ms)
        
        # If start returns -1 (max players), handle gracefully
        if player_number == -1:
             return None

        rack = self.game.racks[player_number]
        rack.cursor_position = 0
        rack.select_count = 0

        # clear out the last guess
        await self.game._app.guess_word_keyboard("", player_number, now_ms)
        return player_number

    def handle_return_action(self, input_device: InputDevice):
        if not self.game.running:
            return
        rack = self.game.racks[input_device.player_number]
        input_device.current_guess = ""
        rack.cursor_position = 0 if not input_device.reversed else 5
        rack.select_count = len(input_device.current_guess)
        self.game.sound_manager.play_cleared()
        rack.draw()

    def get_handlers(self) -> Dict[str, Callable]:
        """Return a dictionary of input handlers binding methods to names."""
        return {
            'left': self.handle_left_movement,
            'right': self.handle_right_movement,
            'insert': self.handle_insert_action,
            'delete': self.handle_delete_action,
            'action': self.handle_space_action,
            'return': self.handle_return_action,
            'start': self.start_game,
        }
