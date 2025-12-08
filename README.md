# Chorded
**A Computer Vision-Based Virtual Instrument**

> **Mission:** To make music creation accessible to individuals without access to physical instruments or financial resources by turning simple hand gestures into rich musical compositions.

---

## About The Project
Chorded is a gesture-recognition system that detects real-time hand positions and maps finger patterns to musical chords. By leveraging computer vision, it allows users to play instruments virtually, lowering the barrier to entry for musical expression.

This project bridges the gap between **Computer Vision** and **Digital Audio Workstations (DAW)** logic, creating a seamless "air-instrument" experience.

## Tech Stack
* **Language:** Python
* **Computer Vision:** OpenCV, MediaPipe
* **Backend:** Flask
* **Audio Protocol:** MIDI (Dynamic Channel Parsing)

## Key Features
* **Real-Time Gesture Tracking:** Utilizes MediaPipe to detect hand landmarks with high precision and low latency.
* **Smart Chord Mapping:** Recognizes finger patterns to trigger complex chords and dynamic inversions automatically.
* **Multi-Instrument Backend:** A Flask-based architecture that supports dynamic MIDI channel parsing, allowing the user to switch between different instrument outputs.
* **Accessibility First:** Designed specifically for users with limited physical mobility or lack of access to hardware instruments.

## How It Works
1.  **Input:** The webcam captures video input.
2.  **Processing:** OpenCV and MediaPipe process the frame to identify hand landmarks and calculate finger states.
3.  **Logic:** The Python backend interprets these states as musical chords (e.g., "Peace sign" = C Major).
4.  **Output:** The system generates MIDI signals sent to the system's audio output or connected DAW.

## Getting Started

### Prerequisites
* Python 3.8+
* Webcam

### Installation
1. Clone the repo:
   ```sh
   git clone [https://github.com/RujulaAD/Chorded.git](https://github.com/RujulaAD/Chorded.git)
