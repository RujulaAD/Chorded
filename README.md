# Chorded

Chorded is a Python webcam instrument. MediaPipe detects hand gestures, and the app plays MIDI chords through a Tkinter interface with the camera preview and song chord map in one window.

## Requirements

- Python 3.11 is recommended; it is the version used to run this project.
- A webcam.
- A MIDI output device available to Pygame. The app currently opens MIDI output device `0`.

## Install and Run

In Windows PowerShell, create the virtual environment outside the OneDrive project folder to avoid syncing generated dependency and bytecode files:

```powershell
py -3.11 -m venv "$env:USERPROFILE\venvs\chorded"
& "$env:USERPROFILE\venvs\chorded\Scripts\python.exe" -m pip install -r requirements.txt
& "$env:USERPROFILE\venvs\chorded\Scripts\python.exe" hand_to_chord.py
```

## Choose Chords and Gestures

1. Enter the song's chord names separated by commas, for example: `C, Am, F#sus4, Bb7`.
2. Select **Load chords**. The app creates and activates a default gesture for each chord.
3. To customize the gestures, choose a different finger-count pair for each chord and select **Apply gesture map**.

Each pair is the number of extended fingers on the two hands; either hand can show either count. Hold a mapped pair briefly to play its chord. Unmapped pairs do nothing. Releasing the hands or showing two closed fists stops playback. The map supports up to 15 unique chords per session.

Common chord suffixes include `m`, `dim`, `7`, `m7`, `maj7`, `aug`, `sus2`, `sus4`, `6`, `m6`, `add9`, `9`, `m9`, `maj9`, `dim7`, and `m7b5`. Sharp and flat roots are supported, such as `F#` and `Bb`.

The chord map scrolls with the mouse wheel when it is longer than the panel. Press `Esc` or close the window to exit.
