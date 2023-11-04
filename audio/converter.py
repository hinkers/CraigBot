from __future__ import annotations

import os
import shutil
import sys
from typing import TYPE_CHECKING

from pydub import AudioSegment
from pydub.utils import make_chunks

if TYPE_CHECKING:
    from database.audio import Song

# Hardcoded reference values for loudness and sample rate
REFERENCE_LOUDNESS = -7.8  # in dBFS
REFERENCE_SAMPLE_RATE = 48000


def convert_to_webm(song: Song) -> None:
    audio = AudioSegment.from_file(song.full_filename)
    output_format = "webm"
    audio.export(song.full_filename_without_extension + '.webm', format=output_format)
    os.remove(song.full_filename)
    song.extension = 'webm'


def equalise_loudness(song: Song) -> None:
    # Load the new audio track
    audio = AudioSegment.from_file(song.full_filename, format="webm")

    # Resample the new track if necessary
    if audio.frame_rate != REFERENCE_SAMPLE_RATE:
        audio = audio.set_frame_rate(REFERENCE_SAMPLE_RATE)

    # Get the loudness of the new track
    chunks = make_chunks(audio, 1000)
    loudness = max(chunk.dBFS for chunk in chunks)

    # Normalize the loudness of the new track if necessary
    if loudness != REFERENCE_LOUDNESS:
        audio = audio.apply_gain(REFERENCE_LOUDNESS - loudness)

    # Export the normalized audio track as a new file
    temp_file = song.full_filename_without_extension + '_normalized.webm'
    audio.export(temp_file, format="webm")
    os.remove(song.full_filename)
    shutil.move(temp_file, song.full_filename)


def get_loudness(audio_file):
    # Load the audio file
    audio = AudioSegment.from_file(audio_file, format="webm")

    # Get the sample rate of the audio file
    sample_rate = audio.frame_rate

    # Calculate the loudness of the audio file
    chunks = make_chunks(audio, 1000)
    loudness = max(chunk.dBFS for chunk in chunks)

    print(f"Reference loudness: {loudness} dBFS")
    print(f"Reference sample rate: {sample_rate} Hz")


if __name__ == '__main__':
    if sys.argv[1] == 'get_loudness':
        get_loudness(sys.argv[2])
    elif sys.argv[1] == 'equalise_loudness':
        equalise_loudness(sys.argv[2])
