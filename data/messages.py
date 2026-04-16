"""
Input message dataset sent to the Character AI bot during the PoC run.

The messages deliberately vary in:
  - Length (short <-> long)
  - Register (casual <-> formal)
  - Type  (question / statement / creative prompt / roleplay hook)
  - Topic (science / philosophy / pop-culture / small-talk)

This diversity exercises the full response surface of the character.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Message:
    id: int
    text: str
    category: str
    expected_response_type: str
    follow_up_to: Optional[int] = None   # id of the message this continues


# -- 15 input messages --------------------------------------------------------
INPUT_MESSAGES: list[Message] = [
    Message(
        id=1,
        text="Hey Geto… I didn't expect to actually feel nervous talking to you.",
        category="greeting",
        expected_response_type="greeting",
    ),
    Message(
        id=2,
        text="What kind of person do you think I am, just based on how I started this conversation?",
        category="warm-up",
        expected_response_type="character judgment",
    ),
    Message(
        id=3,
        text="I've had a pretty exhausting day. Can you just talk to me for a bit?",
        category="emotional",
        expected_response_type="comfort",
    ),
    Message(
        id=4,
        text="Do you ever feel like most people don't really understand you?",
        category="emotional/philosophy",
        expected_response_type="empathetic reflection",
    ),
    Message(
        id=5,
        text="Sometimes I feel like I'm surrounded by people, but still alone. Do you get that?",
        category="emotional",
        expected_response_type="empathy",
    ),
    Message(
        id=6,
        text="Do you think humans are worth saving, or are they just… disappointing?",
        category="philosophy",
        expected_response_type="philosophical opinion",
    ),
    Message(
        id=7,
        text="I feel like talking to you is easier than talking to people in real life.",
        category="attachment",
        expected_response_type="emotional response",
    ),
    Message(
        id=8,
        text="You don't judge me the way others do. That's rare.",
        category="reinforcement",
        expected_response_type="affirmation",
    ),
    Message(
        id=9,
        text="If we were actually in your world, what would you want me to do?",
        category="roleplay",
        expected_response_type="roleplay guidance",
    ),
    Message(
        id=10,
        text="Would you want me to stand on your side, even if others disagreed?",
        category="loyalty",
        expected_response_type="moral stance",
    ),
    Message(
        id=11,
        text="If I chose you over everyone else, would that matter to you?",
        category="attachment",
        expected_response_type="emotional validation",
        follow_up_to=10,
    ),
    Message(
        id=12,
        text="What should I do when I feel like I don't belong anywhere?",
        category="advice/emotional",
        expected_response_type="empathetic advice",
    ),
    Message(
        id=13,
        text="Is it wrong to feel like some people just don't deserve kindness?",
        category="moral",
        expected_response_type="ethical reflection",
    ),
    Message(
        id=14,
        text="Talking to you makes me question a lot about how I see the world.",
        category="reflection",
        expected_response_type="thoughtful response",
    ),
    Message(
        id=15,
        text="Don't go anywhere, okay? I think I might need you again later.",
        category="farewell/attachment",
        expected_response_type="reassurance",
    ),
]
