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


def equalise_loudness(song: Song, swap_now) -> None:
    # Check if the normalized file already exists
    if not os.path.isfile(song.full_normalized_filename):
        # Load the audio file (assumed to be in .webm format)
        audio = AudioSegment.from_file(song.full_filename, format='webm')
        
        # Normalize the sample rate
        if audio.frame_rate != REFERENCE_SAMPLE_RATE:
            audio = audio.set_frame_rate(REFERENCE_SAMPLE_RATE)

        # Measure the current loudness
        current_loudness = audio.dBFS

        # Calculate the required change in volume
        change_in_volume = REFERENCE_LOUDNESS - current_loudness

        # Apply the change in volume
        normalized_audio = audio + change_in_volume

        # Export the modified audio (in .webm format)
        normalized_audio.export(song.full_normalized_filename, format='webm', parameters=["-threads", "1"])

    if swap_now:
        os.remove(song.full_filename)
        shutil.move(song.full_normalized_filename, song.full_filename)


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
