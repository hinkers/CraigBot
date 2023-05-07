import sys

from pydub import AudioSegment
from pydub.utils import make_chunks

# Hardcoded reference values for loudness and sample rate
REFERENCE_LOUDNESS = -7.8  # in dBFS
REFERENCE_SAMPLE_RATE = 48000


def equalise_loudness(audio_file):
    # Load the new audio track
    audio = AudioSegment.from_file(audio_file, format="webm")

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
    audio.export(audio_file, format="webm")

    return audio_file


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
