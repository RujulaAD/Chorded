import cv2
import mediapipe as mp
import pygame.midi
import time

# Debounce setup
gesture_start_time = 0
gesture_hold_threshold = 0.2  # seconds
pending_chord = None

# Initialize MediaPipe
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(max_num_hands=2, min_detection_confidence=0.7, min_tracking_confidence=0.6)
mp_draw = mp.solutions.drawing_utils

# Initialize MIDI
pygame.midi.init()
midi_out = pygame.midi.Output(0)
midi_out.set_instrument(49, 0)  # Channel 0: strings
vari_instrument = 24 # 0=piano, 24=guitar 
midi_out.set_instrument(vari_instrument, 1)   # Channel 1: chosen instrument

# Chord mapping
root_notes = ['C', 'D', 'E', 'F', 'G', 'A', 'B']
guitar_chords = {
    ('C', 'major'):     [48, 52, 55, 60, 64],      # C3, E3, G3, C4, E4
    ('C', 'minor'):     [63, 67, 72],         # Eb G C (1st inversion)
    ('C', 'diminished'): [63, 66, 72],        # Eb Gb C (1st inversion)
    ('C', 'dominant7'): [64, 67, 70, 72],     # E G Bb C (1st inv)
    ('C', 'minor7'):    [63, 67, 70, 72],     # Eb G Bb C (1st inv)
    ('C', 'major7'):    [64, 67, 71, 72],     # E G B C (1st inv)

    ('D', 'major'):     [50, 57, 62, 66],          # D3, A3, D4, F#4
    ('D', 'minor'):     [65, 69, 74],
    ('D', 'diminished'): [65, 68, 74],
    ('D', 'dominant7'): [66, 69, 72, 74],
    ('D', 'minor7'):    [65, 69, 72, 74],
    ('D', 'major7'):    [66, 69, 73, 74],

    ('E', 'major'):     [68, 71, 76],
    ('E', 'minor'):     [40, 47, 52, 55, 59, 64],  # E2, B2, E3, G3, B3, E4
    ('E', 'diminished'): [67, 70, 76],
    ('E', 'dominant7'): [68, 71, 74, 76],
    ('E', 'minor7'):    [67, 71, 74, 76],
    ('E', 'major7'):    [68, 71, 75, 76],

    ('F', 'major'):     [41, 45, 48, 53, 57, 65],  # F2, A2, C3, F3, A3, F4
    ('F', 'minor'):     [64, 69, 72],
    ('F', 'diminished'): [64, 67, 72],
    ('F', 'dominant7'): [65, 69, 72, 74],
    ('F', 'minor7'):    [64, 69, 72, 74],
    ('F', 'major7'):    [65, 69, 72, 76],

    ('G', 'major'):     [43, 47, 50, 55, 59, 67],         # E2, B2, D3, G3, B3, G4
    ('G', 'minor'):     [67, 70, 74],
    ('G', 'diminished'): [67, 70, 73],
    ('G', 'dominant7'): [67, 71, 74, 76],
    ('G', 'minor7'):    [67, 70, 74, 76],
    ('G', 'major7'):    [67, 71, 74, 78],

    ('A', 'major'):     [69, 73, 76],
    ('A', 'minor'):     [69, 72, 76],
    ('A', 'diminished'): [69, 72, 75],
    ('A', 'dominant7'): [69, 73, 76, 78],
    ('A', 'minor7'):    [69, 72, 76, 78],
    ('A', 'major7'):    [69, 73, 76, 80],

    ('B', 'major'):     [71, 75, 78],
    ('B', 'minor'):     [71, 74, 78],
    ('B', 'diminished'): [71, 74, 77],
    ('B', 'dominant7'): [71, 75, 78, 80],
    ('B', 'minor7'):    [71, 74, 78, 80],
    ('B', 'major7'):    [71, 75, 78, 82],
}
piano_chords = {
    ('C', 'major'):     [60, 64, 67],
    ('C', 'minor'):     [60, 63, 67],
    ('C', 'diminished'): [60, 63, 66],
    ('C', 'dominant7'): [60, 64, 67, 70],
    ('C', 'minor7'):    [60, 63, 67, 70],
    ('C', 'major7'):    [60, 64, 67, 71],

    ('D', 'major'):     [62, 66, 69],
    ('D', 'minor'):     [62, 65, 69],
    ('D', 'diminished'): [62, 65, 68],
    ('D', 'dominant7'): [62, 66, 69, 72],
    ('D', 'minor7'):    [62, 65, 69, 72],
    ('D', 'major7'):    [62, 66, 69, 73],

    ('E', 'major'):     [64, 68, 71],
    ('E', 'minor'):     [64, 67, 71],
    ('E', 'diminished'): [64, 67, 70],
    ('E', 'dominant7'): [64, 68, 71, 74],
    ('E', 'minor7'):    [64, 67, 71, 74],
    ('E', 'major7'):    [64, 68, 71, 75],

    ('F', 'major'):     [65, 69, 72],
    ('F', 'minor'):     [65, 68, 72],
    ('F', 'diminished'): [65, 68, 71],
    ('F', 'dominant7'): [65, 69, 72, 75],
    ('F', 'minor7'):    [65, 68, 72, 75],
    ('F', 'major7'):    [65, 69, 72, 76],

    ('G', 'major'):     [67, 71, 74],
    ('G', 'minor'):     [67, 70, 74],
    ('G', 'diminished'): [67, 70, 73],
    ('G', 'dominant7'): [67, 71, 74, 77],
    ('G', 'minor7'):    [67, 70, 74, 77],
    ('G', 'major7'):    [67, 71, 74, 78],

    ('A', 'major'):     [69, 73, 76],
    ('A', 'minor'):     [69, 72, 76],
    ('A', 'diminished'): [69, 72, 75],
    ('A', 'dominant7'): [69, 73, 76, 79],
    ('A', 'minor7'):    [69, 72, 76, 79],
    ('A', 'major7'):    [69, 73, 76, 80],

    ('B', 'major'):     [71, 75, 78],
    ('B', 'minor'):     [71, 74, 78],
    ('B', 'diminished'): [71, 74, 77],
    ('B', 'dominant7'): [71, 75, 78, 81],
    ('B', 'minor7'):    [71, 74, 78, 81],
    ('B', 'major7'):    [71, 75, 78, 82],
}



# Camera
cap = cv2.VideoCapture(0)

# Track chord state
last_chord_notes = []
last_played_chord = None

def get_fingers_up(hand_landmarks):
    finger_tips = [4, 8, 12, 16, 20]
    finger_names = ['thumb', 'index', 'middle', 'ring', 'pinky']
    fingers_up = []

    if hand_landmarks.landmark[4].x > hand_landmarks.landmark[3].x:
        fingers_up.append('thumb')
    for tip, name in zip(finger_tips[1:], finger_names[1:]):
        if hand_landmarks.landmark[tip].y < hand_landmarks.landmark[tip - 2].y:
            fingers_up.append(name)

    return fingers_up

cv2.namedWindow("Chord Guide", cv2.WINDOW_NORMAL)
guide = cv2.imread("Gesture_to_Chords.png")

while True:
    cv2.imshow("Chord Guide", guide)

    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = hands.process(rgb)

    fingers_up = []

    if result.multi_hand_landmarks:
        for hand in result.multi_hand_landmarks:
            mp_draw.draw_landmarks(frame, hand, mp_hands.HAND_CONNECTIONS)
            fingers_up.append(get_fingers_up(hand))

    if len(fingers_up) == 2:
        left_fingers = fingers_up[0]
        right_fingers = fingers_up[1]

        if set(left_fingers) == {'thumb', 'pinky'}:
            root = 'A'
        elif set(left_fingers) == {'index', 'pinky'}:
            root = 'B'
        elif 1 <= len(left_fingers) <= 5:
            root = root_notes[len(left_fingers) - 1]
        else:
            root = None

        if root:
            # Updated chord type mapping
            if len(right_fingers) == 1:
                chord_type = 'major'
            elif len(right_fingers) == 2:
                chord_type = 'minor'
            elif len(right_fingers) == 3:
                chord_type = 'dominant7'
            elif len(right_fingers) == 4:
                chord_type = 'minor7'
            elif len(right_fingers) == 5:
                chord_type = 'major7'
            else:
                chord_type = None

            if chord_type:
                chord_key = (root, chord_type)

                if chord_key != pending_chord:
                    pending_chord = chord_key
                    gesture_start_time = time.time()
                else:
                    if time.time() - gesture_start_time >= gesture_hold_threshold and chord_key != last_played_chord:
                        for note in last_chord_notes:
                            midi_out.note_off(note, 1)
                            midi_out.note_off(note, 0)

                        instrument_chords = guitar_chords if vari_instrument == 24 else piano_chords
                        chord_notes = [note - 12 for note in instrument_chords[chord_key]]


                        if chord_notes:
                            for i, note in enumerate(chord_notes):
                                midi_out.note_on(note, 100, 1)
                                midi_out.note_on(note, 50, 0)
                                time.sleep(0.05)  # 50 milliseconds between notes



                        last_chord_notes = chord_notes
                        last_played_chord = chord_key

    # Stop if no hands or closed
    if len(fingers_up) < 2 or all(len(f) == 0 for f in fingers_up):
        if last_chord_notes:
            for note in last_chord_notes:
                midi_out.note_off(note, 1)
                midi_out.note_off(note, 0)
            last_chord_notes = []
            last_played_chord = None
            pending_chord = None

    cv2.imshow("Air Chord", frame)
    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()
midi_out.close()
pygame.midi.quit()
