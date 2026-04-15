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
        text="Hello! I'm excited to chat with you today.",
        category="greeting",
        expected_response_type="greeting",
    ),
    Message(
        id=2,
        text="Can you tell me a little about yourself and what you're passionate about?",
        category="introduction",
        expected_response_type="self-description",
    ),
    Message(
        id=3,
        text="What do you think is the most important scientific discovery of the last century?",
        category="science",
        expected_response_type="opinion",
    ),
    Message(
        id=4,
        text=(
            "I've been struggling to understand quantum entanglement. "
            "Could you explain it in simple terms, maybe with an analogy?"
        ),
        category="science/education",
        expected_response_type="explanation",
    ),
    Message(
        id=5,
        text="If you could travel anywhere in the universe, where would you go and why?",
        category="hypothetical",
        expected_response_type="creative/opinion",
    ),
    Message(
        id=6,
        text="Do you believe artificial intelligence will ever truly understand human emotions?",
        category="philosophy/AI",
        expected_response_type="philosophical debate",
    ),
    Message(
        id=7,
        text="Tell me a short, original story about a robot who discovers music for the first time.",
        category="creative writing",
        expected_response_type="story",
    ),
    Message(
        id=8,
        text="What advice would you give to someone who feels lost in life?",
        category="advice/emotional",
        expected_response_type="empathetic advice",
    ),
    Message(
        id=9,
        text=(
            "Let's roleplay: you are a wise sage living in an ancient library. "
            "I enter through the heavy oak doors. What do you say to me?"
        ),
        category="roleplay",
        expected_response_type="roleplay response",
    ),
    Message(
        id=10,
        text="What's your favourite joke? Make it nerdy.",
        category="humour",
        expected_response_type="joke",
    ),
    Message(
        id=11,
        text=(
            "Following up on the quantum entanglement explanation — "
            "how does that relate to quantum computing?"
        ),
        category="science/education",
        expected_response_type="explanation",
        follow_up_to=4,
    ),
    Message(
        id=12,
        text=(
            "I'm writing a Python script that needs to parse nested JSON. "
            "Can you show me a clean way to do that with error handling?"
        ),
        category="technical/coding",
        expected_response_type="code example",
    ),
    Message(
        id=13,
        text="Describe the feeling of watching a sunset using only metaphors.",
        category="creative/poetry",
        expected_response_type="poetic description",
    ),
    Message(
        id=14,
        text="What do you think separates a good conversation from a great one?",
        category="meta/conversation",
        expected_response_type="reflection",
    ),
    Message(
        id=15,
        text="It was wonderful talking with you. Any parting thoughts?",
        category="farewell",
        expected_response_type="farewell",
    ),
]
