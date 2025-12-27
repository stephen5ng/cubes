#!/usr/bin/env python3

import re
import os

test_files = [
    "test_abc_restart_after_game.py",
    "test_countdown_join.py",
    "test_per_player_abc.py",
    "test_simplified_abc_clearing.py",
    "test_simplified_late_join.py"
]

for file_path in test_files:
    if os.path.exists(file_path):
        print(f"Processing {file_path}")

        with open(file_path, 'r') as f:
            content = f.read()

        # Add MockSoundManager import if not present
        if "from src.testing.mock_sound_manager import MockSoundManager" not in content:
            # Find the imports section and add the import
            imports_pattern = r"(import cubes_to_game\nimport tiles)"
            if re.search(imports_pattern, content):
                content = re.sub(
                    imports_pattern,
                    r"\1\nfrom src.testing.mock_sound_manager import MockSoundManager",
                    content
                )
            else:
                # Add after other imports
                imports_pattern = r"(import cubes_to_game)"
                content = re.sub(
                    imports_pattern,
                    r"\1\nfrom src.testing.mock_sound_manager import MockSoundManager",
                    content
                )

        # Add mock_sound_manager = MockSoundManager() in test functions
        # Look for function definitions and add the mock right after publish_queue creation
        def add_mock_sound_manager(match):
            function_content = match.group(0)
            if "mock_sound_manager = MockSoundManager()" not in function_content:
                # Add after publish_queue = TestPublishQueue()
                function_content = re.sub(
                    r"(publish_queue = TestPublishQueue\(\))",
                    r"\1\n    mock_sound_manager = MockSoundManager()",
                    function_content
                )
            return function_content

        # Find async test functions and add mock sound manager
        content = re.sub(
            r"async def test_.*?(?=^async def|^def|$)",
            add_mock_sound_manager,
            content,
            flags=re.MULTILINE | re.DOTALL
        )

        # Update handle_mqtt_message calls to include mock_sound_manager
        content = re.sub(
            r"await cubes_to_game\.handle_mqtt_message\(publish_queue,([^)]+)\)",
            r"await cubes_to_game.handle_mqtt_message(publish_queue,\1, mock_sound_manager)",
            content
        )

        with open(file_path, 'w') as f:
            f.write(content)

        print(f"  - Updated {file_path}")

print("Done!")