import logging
from typing import Optional, Callable, Awaitable
from core.app import App
from game.game_state import Game
from input.input_controller import GameInputController
from input.input_devices import KeyboardInput
from config import game_config

logger = logging.getLogger(__name__)

class KeyboardHandler:
    """Processes keyboard events with game state awareness."""

    def __init__(self, game: Game, app: App, input_controller: GameInputController):
        self.game = game
        self.app = app
        self.input_controller = input_controller

    async def handle_event(self, key: str, keyboard_input: KeyboardInput, now_ms: int) -> None:
        """Handle keyboard events for the game."""
        if key == "ESCAPE":
            print("starting due to ESC")
            keyboard_input.player_number = await self.input_controller.start_game(keyboard_input, now_ms)
            return

        if keyboard_input.player_number is None:
            return

        elif key == "LEFT":
            self.input_controller.handle_left_movement(keyboard_input)
        elif key == "RIGHT":
            self.input_controller.handle_right_movement(keyboard_input)
        elif key == "SPACE":
            await self.input_controller.handle_space_action(keyboard_input, now_ms)
        elif key == "BACKSPACE":
            if keyboard_input.current_guess:
                keyboard_input.current_guess = keyboard_input.current_guess[:-1]
                self.game.racks[keyboard_input.player_number].select_count = len(keyboard_input.current_guess)
                self.game.racks[keyboard_input.player_number].draw()
        elif key == "RETURN":
            self.input_controller.handle_return_action(keyboard_input)
        elif key == "TAB":
            self.game.toggle_player_count()
                     
        elif len(key) == 1:
            remaining_letters = list(self.game.racks[keyboard_input.player_number].letters())
            # Remove letters already used in current guess
            for l in keyboard_input.current_guess:
                if l in remaining_letters:
                    remaining_letters.remove(l)
            
            # If key not available, clear guess (strict typing)
            if key not in remaining_letters:
                keyboard_input.current_guess = ""
                self.game.racks[keyboard_input.player_number].select_count = len(keyboard_input.current_guess)
                # Re-fetch remaining letters as we just cleared used ones
                remaining_letters = list(self.game.racks[keyboard_input.player_number].letters())
            
            if key in remaining_letters:
                keyboard_input.current_guess += key
                await self.app.guess_word_keyboard(keyboard_input.current_guess, keyboard_input.player_number, now_ms)
                self.game.racks[keyboard_input.player_number].select_count = len(keyboard_input.current_guess)
                logger.debug(f"key: {str(key)} {keyboard_input.current_guess}")
