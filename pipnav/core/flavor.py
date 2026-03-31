"""Vault-Tec loading messages and flavor text."""

import random

LOADING_MESSAGES = (
    "SCANNING WASTELAND FOR SETTLEMENTS...",
    "CALIBRATING GEIGER COUNTER...",
    "CONSULTING MR. HANDY...",
    "PLEASE STAND BY...",
    "INITIALIZING V.A.T.S. TARGETING...",
    "LOADING HOLOTAPE DATA...",
    "SYNCING WITH VAULT-TEC MAINFRAME...",
    "RETICULATING SPLINES...",
    "DEFRAGMENTING HOLODISK...",
    "TUNING DIAMOND CITY RADIO...",
    "CHECKING RADIATION LEVELS...",
    "BOOTING ROBCO INDUSTRIES OS...",
    "DECRYPTING INSTITUTE SIGNALS...",
    "POLLING SETTLEMENT RESOURCES...",
    "QUERYING BROTHERHOOD ARCHIVES...",
)


def random_loading_message() -> str:
    """Return a random Vault-Tec loading message."""
    return random.choice(LOADING_MESSAGES)
