import subprocess

import whisper
import editor

import srt
from datetime import timedelta

from moviepy.editor import *
from moviepy.video.tools.subtitles import SubtitlesClip
from moviepy.video.fx.all import crop


def cut_silence(video):
    fast = "fast.mp4"
    #subprocess.run(["auto-editor", video, "--no-open", "-o", fast],
    #        stdout=subprocess.DEVNULL,
    #        stderr=subprocess.STDOUT)
    return fast

def v_to_a(video):
    clip = VideoFileClip(video)
    audio = "audio.wav"
    #clip.audio.write_audiofile(audio, logger=None)
    return audio

def get_segment_end(segment, original):
    return segment['end'] if segment['end'] < original.end else original.end # NOTE: whisper can return longer timestamps than original duration...
def get_segment_relative_end(segment, original, last_end):
    return last_end + (get_segment_end(segment, original) - segment["start"])

def segment_to_clip(segment, original):
    return original.subclip(segment['start'], get_segment_end(segment, original))
def segment_to_sub(segment, original, last_end, i):
    return srt.Subtitle(i, timedelta(seconds=last_end), timedelta(seconds=get_segment_relative_end(segment, original, last_end)), segment["text"])

def enumerate_on_segments(segments, original, f):
    last_end = 0
    for i, segment in enumerate(segments):
        f(i, segment, original, last_end)
        last_end = get_segment_relative_end(segment, original, last_end)

def segments_to_clip_and_subs(segments, original_file):
        clips = []
        subs = []
        original = VideoFileClip(original_file)
        enumerate_on_segments(segments, 
                original, 
                lambda i, segment, original, last_end: 
                    [
                        clips.append(segment_to_clip(segment, original)), 
                        subs.append(segment_to_sub(segment, original, last_end, i))
                    ]
        )
        return concatenate_videoclips(clips), subs

def subs_to_file(subs):
    sub_file = "subs.srt"
    with open(sub_file, "w") as file:
        file.write(srt.compose(subs))
    return sub_file

def clip_to_file(clip):
    clip_file = "end.mp4"
    clip.write_videofile(clip_file, logger=None) 
    return clip_file

def crop_clip(clip):
    (w, h) = clip.size
    return crop(clip, x_center = w/2, y_center = h/2, width = 607, height = 1080)

def overlay_end_text_on_clip(clip, end_time = 5):
    return concatenate_videoclips([clip.subclip(0, clip.end - end_time), CompositeVideoClip([clip.subclip(clip.end - end_time, clip.end), TextClip("A teljes videó megtalálható fő csatornáimon!", fontsize = 48, method = "caption", font = "Arial", color="white").set_duration(end_time).set_pos("center", "center")])])

def burn_in_subs_to_file(file, sub_file):
    subprocess.run(["ffmpeg", "-i", file, "-vf", f"subtitles={sub_file}:force_style='Alignment=2,MarginV=50,Fontsize=12'", "-c:a", "copy", f"short.mp4"])#,
        #stdout=subprocess.DEVNULL,
        #stderr=subprocess.STDOUT)
    return f"short.mp4"


def preprocess_video(original_file):
    print(f"Cutting silence out of video ({original_file})...")
    fast = cut_silence(original_file)
    print(f"Converting video ({fast}) to audio...")
    audio = v_to_a(fast)
    return fast, audio

def audio_to_segments(audio, model = "base", device = "cpu"):
    print(f"Loading Whisper model {model} on {device}...")
    model = whisper.load_model(model, device = device)
    print(f"Transcribing audio ({audio}) to text segments...")
    return model.transcribe(audio)["segments"]

def print_segments(segments):
    for segment in segments:
        print(f"{segment['id']}: {segment['start']} -> {segment['end']}")
        print(segment['text'])
        print("---" * 25)

def edit_segments(segments):
    for segment in segments:
        segment['text'] = editor.edit(contents=segment['text'].encode("UTF-8")).decode("UTF-8")
    return segments

def generate_file(segments, original_file):
    print("Generating concatenated clip and syncing subtitles...")
    concat, subs = segments_to_clip_and_subs(selected_segments, original_file)
    
    print("Cropping to size...")
    cropped = crop_clip(concat)
    
    print("Putting on end text...")
    end_file = clip_to_file(overlay_end_text_on_clip(cropped))

    print("Burning-in subtitles...")
    return burn_in_subs_to_file(end_file, subs_to_file(subs))

original_file = "project.mp4"
video, audio = preprocess_video(original_file)

segments = audio_to_segments(audio)
print_segments(segments)

run = True
count = 0
while run:
    inp = input("Command: ")
    if inp == "exit":
        run = False
    elif inp[0] == "p":
        print_segments(segments)
    elif inp[0] == "e":
        selected_segments = [segments[int(i)] for i in inp[1:].split()]
        print_segments(edit_segments(selected_segments))
    else:
        selected_segments = [segments[int(i)] for i in inp.split()]
        file = generate_file(selected_segments, video)
        print_segments(selected_segments)
        print(f"Done, wrote to {file}!")
        count += 1
