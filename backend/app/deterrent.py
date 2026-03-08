import os
import random
import time
import threading
import io
import pygame

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs import stream
load_dotenv()

# Audio scripts per species
SCRIPTS: dict[str, list[str]] = {
    "crow": [
        "Hey! Get out of here you filthy crow! Shoo! Away with you!",
        "CROWS! Get off this farm right now! You are not welcome here!",
        "Go away crow! This is not your land! Leave immediately!",
    ],
    "deer": [
        "Hey deer! Get out of the crops! Go back to the forest where you belong!",
        "Shoo deer! Away from the farm! Move it! Get going!",
        "Get out of here deer! You are destroying the harvest! Leave now!",
    ],
    "rat": [
        "Hey rats! Get out of the fucking crops! Go back to the sewers where you belong!",
        "Go back into the sewers you filthy rats! This is not your land! Leave immediately!",
        "Go back to the mutant turtles, Master Splinter",
    ],
    "raccoon": [
        "Raccoon! Get your grubby paws off the crops! Scram!",
        "Hey you sneaky raccoon! Out! Out! Out! Get off this property!",
        "Go away raccoon! This food is not for you! Get lost!",
    ],
    "goose": [
        "Goose! Get off the farm! Go find a pond somewhere else! Shoo!",
        "Hey goose! Nobody wants you here! Get moving! Go away!",
        "Get out of here you honking goose! Leave the farm alone! Scram!",
    ],

    "coyote": [
        "Coyote! You mangy, flea-ridden waste of fur! Get off this farm before I make you into a hat!",
        "Hey scrawny! Yeah you, the one that looks like a wet dog had a baby with a trash can! SCRAM!",
        "Get lost coyote! You couldn't catch a cold, let alone my chickens! Get out of here!",
        "Oh look, it's the ugliest thing on four legs! Get your bony behind off my property RIGHT NOW!",
        "Coyote! Your howling is pathetic and so are you! Nobody is impressed! LEAVE!",
        "You call yourself a predator?! You look like you lost a fight with a lawn mower! GET OUT!",
        "Hey mangy! The roadrunner called, he said even HE doesn't want to be caught by something as embarrassing as you! GO AWAY!",
    ],
}

DEFAULT_SCRIPTS = [
    "Get off this farm right now! You are not welcome here! Go away!",
    "Shoo! Get away! Leave this farm immediately! Get out!",
    "Hey! Get out of here! This is private property! Scram!",
]

# Cooldown tracking: species -> last triggered timestamp
cooldowns: dict[str, float] = {}
cooldown_lock = threading.Lock()
COOLDOWN_SECONDS = 10

# Replace with your ElevenLabs voice ID
VOICE_ID = "rfHVfqlu6LXw4vLf7q4i"

client: ElevenLabs | None = None


def get_client() -> ElevenLabs:
    global client
    if client is None:
        api_key = os.getenv("ELEVENLABS_API_KEY")
        client = ElevenLabs(api_key=api_key)
    return client


def is_on_cooldown(species: str) -> bool:
    with cooldown_lock:
        last = cooldowns.get(species, 0)
        return (time.time() - last) < COOLDOWN_SECONDS


def set_cooldown(species: str) -> None:
    with cooldown_lock:
        cooldowns[species] = time.time()


def play_audio_background(audio_bytes: bytes) -> None:
    pygame.mixer.init()
    sound = pygame.mixer.Sound(io.BytesIO(audio_bytes))
    sound.play()
    pygame.time.wait(int(sound.get_length() * 1000))


def trigger_deterrent(species: str) -> str | None:
    """
    Generate and play a scare audio for the given species.
    Returns the script used, or None if on cooldown.
    Plays audio in a background thread so it doesn't block detection.
    """
    species_key = species.lower()

    if is_on_cooldown(species_key):
        return None

    set_cooldown(species_key)

    scripts = SCRIPTS.get(species_key, DEFAULT_SCRIPTS)
    script = random.choice(scripts)

    client = get_client()
    audio_generator = client.text_to_speech.convert(
        voice_id=VOICE_ID,
        text=script,
        model_id="eleven_turbo_v2_5",
    )
    audio_bytes = b"".join(audio_generator)

    thread = threading.Thread(target=play_audio_background, args=(audio_bytes,), daemon=True)
    thread.start()

    return script
