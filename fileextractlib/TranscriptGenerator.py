import whisper
import time
import os
from os import path
import argparse
from datetime import timedelta
import numpy as np
import ffmpeg
import io

from webvtt import WebVTT, Caption

import config
import logging

_logger = logging.getLogger(__name__)

class TranscriptGenerator:
    """
     Can be used to convert lecture video/audio to text transcripts in WebVTT format.
    """

    def __init__(self, whisper_model: str = "base"):
        """
        Create a new instance of the class, which can be used to process lecture video/audio recordings into text transcripts.

        :param whisper_model: OpenAI whisper model name, defaults to "base"
        """
        self.model: whisper.Whisper = whisper.load_model(name=config.current["transcript_generation"]["whisper_model"],
                                                         device=config.current["transcript_generation"]["device"])

    def process_to_vtt(self, file_name: str) -> WebVTT:
        """
        Processes the file with the specified name to a transcript. Uses ffmpeg internally to extract the audio, so any video/audio format readable by 
        ffmpeg works by default. Additionally, networked resources supported by ffmpeg also work (e.g. specifying an HTTP URL to a video file as file_name)

        :param file_name: Name/path of the input video/audio file.
        :raises RuntimeError: Raised when the ffmpeg process encounters an error during audio extraction.
        :return: Returns a WebVTT object containing the transcript.
        """
        # load audio data from file
        try:
            sample_rate = 16000
            y, _ = (
                ffmpeg.input(file_name, threads=0)
                .output("-", format="s16le", acodec="pcm_s16le", ac=1, ar=sample_rate)
                .run(
                    cmd=["ffmpeg", "-nostdin"], capture_stdout=True, capture_stderr=True
                )
            )
        except ffmpeg.Error as e:
            raise RuntimeError(f"Failed to load audio: {e.stderr.decode()}") from e

        # audio data load into numpy array
        audio_data = np.frombuffer(y, np.int16).flatten().astype(np.float32) / 32768.0

        start_time: float = time.time()
        result = self.model.transcribe(audio=audio_data, word_timestamps=True)
        end_time: float = time.time()

        vtt = WebVTT()

        for segment in result["segments"]:
            segment_text: str = ""
            for word in segment["words"]:
                segment_text += word["word"]

            segment_start = timedelta(seconds=segment["start"])
            segment_end = timedelta(seconds=segment["end"])

            if segment_start.microseconds == 0:
                segment_start = segment_start + timedelta(microseconds=1)

            if segment_end.microseconds == 0:
                segment_end = segment_end + timedelta(microseconds=1)

            caption = Caption(
                str(segment_start),
                str(segment_end),
                "-" + segment_text
            )
            vtt.captions.append(caption)

        _logger.info("Generated transcript in " + str(end_time - start_time) + " seconds.")
        return vtt
        

    def process_to_file(self, file_name: str) -> str:
        """
        Processes the file with the specified name to a transcript. Uses ffmpeg internally to extract the audio, so any video/audio format readable by 
        ffmpeg works by default. Additionally, networked resources supported by ffmpeg also work (e.g. specifying an HTTP URL to a video file as file_name)

        :param file_name: Name/path of the input video/audio file.
        :raises RuntimeError: Raised when the ffmpeg process encounters an error during audio extraction.
        :return: Returnsa transcript as a string, in WebVTT caption format.
        """
        vtt = self.process_to_vtt(file_name)
        
        with io.StringIO() as f:
            vtt.write(f)
            f.seek(0)
            return f.read()