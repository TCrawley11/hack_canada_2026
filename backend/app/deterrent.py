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
        "Fly back the way you came darn chopped crows!"
    ],
    "deer": [
        "Get out of here deer! You are destroying the harvest! Leave now!",
        "Hey deer! Get away from the crops! Go back to the forest where you belong!",
    ],
    "rat": [
        "Hey rats! Get away from the fucking crops! Go back to the sewers where you belong!",
        "Go back to the mutant turtles, Master Splinter",
    ],
    "raccoon": [
        "Raccoon! Get your grubby paws off the crops! Scram!",
        "Hey you sneaky raccoon! Out! Out! Out! Get off this property!",
    ],
    "goose": [
        "Goose! You are not wanted, even in Waterloo. Go find a pond somewhere else! Shoo!",
    ],

    "coyote": [
        "Coyote! You mangy, flea-ridden waste of fur! Get off this farm before I make you into a hat!",
        "Oh hell nah, it's wily coyote! Get your bony behind off my property RIGHT NOW!",
        "You call yourself a predator?! You look like you lost a fight with a lawn mower! GET OUT!",
        "Coyote!, Your howling is pathetic and so are you! Nobody is impressed! LEAVE!"
    ],

    "bear": [
        "Get out of here winnie the pooh!",
        "There ain't no honey for you here little bear. LEAVE!",
        "Boy there ain't no salmon for you. "
    ],

    "human": [
        "Human! get the fuck out of here! I'm calling 911",
        "Hey there foolish one, you are being recorded now. This is being sent to the POLICE!",
        "Why the hell are you on this farm child! Up to something sussy are we...? Just leave and I won't tell anyone",
    ],
}

DEFAULT_SCRIPTS = [
    "Listen here you little troublemaker, I've got a shotgun and zero patience! SCRAM!",
    "Get your freeloading behind off my property before I lose my mind!",
    "The voices inside my head are getting louder... hehehe...",
]

# Resolve sounds directory relative to this file (backend/sounds/)
_SOUNDS_DIR = os.path.join(os.path.dirname(__file__), "..", "sounds")

def _sound(filename: str) -> str:
    return os.path.normpath(os.path.join(_SOUNDS_DIR, filename))

# Predator sound effects per species mapped to actual files in backend/sounds/
PREDATOR_SOUNDS: dict[str, list[str]] = {
    "crow":    [_sound("owl.mp3")],
    "deer":    [_sound("howling.mp3"), _sound("help_me.mp3")],
    "rat":     [_sound("owl.mp3")],
    "raccoon": [_sound("howling.mp3")],
    "goose":   [_sound("howling.mp3")],
    "coyote":  [_sound("lion1.mp3"), _sound("lion2.mp3"), _sound("lion3.mp3")],
    "human":   [_sound("hell_nah.mp3"), _sound("help_me.mp3")],
}

# Cooldown tracking: species -> last triggered timestamp
cooldowns: dict[str, float] = {}
cooldown_lock = threading.Lock()
COOLDOWN_SECONDS = 10

# Global audio playback tracking
_audio_playing = False
_audio_lock = threading.Lock()

# Script decks: tracks which lines haven't been played yet per species.
# Resets and reshuffles when all lines have been used.
_decks: dict[str, list[str]] = {}
_deck_lock = threading.Lock()

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

def _draw_script(species: str) -> str:
    """Draw the next script line without repeating until all lines have been used."""
    with _deck_lock:
        if not _decks.get(species):
            pool = SCRIPTS.get(species, DEFAULT_SCRIPTS).copy()
            random.shuffle(pool)
            _decks[species] = pool
        return _decks[species].pop()

def play_audio_background(audio_bytes: bytes) -> None:
    global _audio_playing
    with _audio_lock:
        _audio_playing = True
    try:
        pygame.mixer.init()
        sound = pygame.mixer.Sound(io.BytesIO(audio_bytes))
        sound.play()
        pygame.time.wait(int(sound.get_length() * 1000))
    finally:
        with _audio_lock:
            _audio_playing = False

def play_sound_file_background(path: str) -> None:
    global _audio_playing
    with _audio_lock:
        _audio_playing = True
    try:
        pygame.mixer.init()
        pygame.mixer.music.load(path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.wait(100)
    finally:
        with _audio_lock:
            _audio_playing = False

def trigger_deterrent(species: str) -> str | None:
    """
    Randomly plays either a TTS script line or a predator sound effect.
    TTS lines cycle through all options before repeating (no-repeat deck).
    Returns a description of what was played, or None if on cooldown or audio is playing.
    """
    species_key = species.lower()

    # Block all detections while any audio is playing
    with _audio_lock:
        if _audio_playing:
            return None

    if is_on_cooldown(species_key):
        return None

    set_cooldown(species_key)

    sound_files = [p for p in PREDATOR_SOUNDS.get(species_key, []) if os.path.exists(p)]
    use_sound = bool(sound_files) and random.random() < 0.5

    if use_sound:
        path = random.choice(sound_files)
        thread = threading.Thread(target=play_sound_file_background, args=(path,), daemon=True)
        thread.start()
        return f"[sound: {os.path.basename(path)}]"

    script = _draw_script(species_key)
    tts_client = get_client()

    audio_generator = tts_client.text_to_speech.convert(
        voice_id=VOICE_ID,
        text=script,
        model_id="eleven_turbo_v2_5",
    )
    audio_bytes = b"".join(audio_generator)

    thread = threading.Thread(target=play_audio_background, args=(audio_bytes,), daemon=True)
    thread.start()

    return script


def play_sound_manual(sound_name: str) -> str | None:
    """
    Play a specific sound file by name (without path/extension).
    Returns the sound name if played, None if audio is already playing.
    """
    global _audio_playing
    with _audio_lock:
        if _audio_playing:
            return None
    
    # Find the sound file
    for filename in os.listdir(_SOUNDS_DIR):
        name_without_ext = os.path.splitext(filename)[0]
        if name_without_ext.lower() == sound_name.lower():
            path = os.path.join(_SOUNDS_DIR, filename)
            thread = threading.Thread(target=play_sound_file_background, args=(path,), daemon=True)
            thread.start()
            return sound_name
    return None


def play_tts_manual(text: str) -> str | None:
    """
    Play TTS for custom text.
    Returns the text if played, None if audio is already playing.
    """
    global _audio_playing
    with _audio_lock:
        if _audio_playing:
            return None
    
    tts_client = get_client()
    audio_generator = tts_client.text_to_speech.convert(
        voice_id=VOICE_ID,
        text=text,
        model_id="eleven_turbo_v2_5",
    )
    audio_bytes = b"".join(audio_generator)
    
    thread = threading.Thread(target=play_audio_background, args=(audio_bytes,), daemon=True)
    thread.start()
    return text


def get_available_sounds() -> list[str]:
    """Return list of available sound file names (without extension)."""
    sounds = []
    if os.path.exists(_SOUNDS_DIR):
        for filename in os.listdir(_SOUNDS_DIR):
            if filename.endswith(('.mp3', '.wav', '.ogg')):
                sounds.append(os.path.splitext(filename)[0])
    return sounds
