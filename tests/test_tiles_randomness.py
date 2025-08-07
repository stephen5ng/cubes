#!/usr/bin/env python3

import random
from tiles import Rack

def test_rack_randomness():
    """Test that Rack instances generate consistent letter sequences with the same seed."""
    
    print("Testing Rack randomness consistency...")
    
    # Test 1: Multiple racks with same initial letters
    print("\nTest 1: Multiple racks with same initial letters")
    initial_letters = "ABCDEF"
    
    rack1 = Rack(initial_letters)
    rack2 = Rack(initial_letters)
    rack3 = Rack(initial_letters)
    
    print(f"Initial letters: {initial_letters}")
    print(f"Rack 1 next letter: {rack1.next_letter()}")
    print(f"Rack 2 next letter: {rack2.next_letter()}")
    print(f"Rack 3 next letter: {rack3.next_letter()}")
    
    # Test 2: Generate multiple next letters from same rack
    print("\nTest 2: Generate multiple next letters from same rack")
    rack = Rack("XYZ")
    print(f"Initial letters: XYZ")
    
    for i in range(5):
        next_letter = rack.next_letter()
        print(f"Next letter {i+1}: {next_letter}")
        # Replace a letter to trigger gen_next_letter()
        rack.replace_letter(next_letter, 0)
    
    # Test 3: Check if random state is consistent between runs
    print("\nTest 3: Check random state consistency")
    print(f"Current random state: {random.getstate()}")
    
    # Reset random state and test again
    random.seed(1)
    rack4 = Rack("ABC")
    print(f"After reset, next letter: {rack4.next_letter()}")
    
    # Test 4: Manual random test
    print("\nTest 4: Manual random test")
    random.seed(1)
    bag = ['A', 'B', 'C', 'D', 'E']
    for i in range(3):
        print(f"Random choice {i+1}: {random.choice(bag)}")

if __name__ == "__main__":
    test_rack_randomness() 