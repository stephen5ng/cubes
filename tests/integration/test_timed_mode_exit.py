
from tests.fixtures.game_factory import create_test_game, run_until_condition, async_test

@async_test
async def test_timed_mode_returns_exit_code_10_on_completion():
    # Setup - Use very short duration (1s)
    duration_s = 1
    game, fake_mqtt, queue = await create_test_game(descent_mode="timed", timed_duration_s=duration_s)
    
    # Act - Run until game stops
    # We expect it to stop after approx 1s + overhead
    stopped = await run_until_condition(
        game, 
        queue, 
        lambda: not game.running,
        max_frames=120  # 2 seconds at 60fps should be plenty
    )
    
    # Assert
    assert stopped, "Game did not stop within expected timeframe"
    assert not game.running
    assert game.exit_code == 10, f"Expected exit code 10 (Win), got {game.exit_code}"
