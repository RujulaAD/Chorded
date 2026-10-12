import cv2
import base64
import itertools
import mediapipe as mp
import pygame.midi
import re
import tkinter as tk
import time
from tkinter import ttk

# Debounce setup

ROOT_PITCH_CLASSES = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
CHORD_QUALITIES = {
    '': ('major', ''),
    'maj': ('major', ''),
    'major': ('major', ''),
    'm': ('minor', 'm'),
    'min': ('minor', 'm'),
    'minor': ('minor', 'm'),
    'dim': ('diminished', 'dim'),
    'diminished': ('diminished', 'dim'),
    '°': ('diminished', 'dim'),
    '7': ('dominant7', '7'),
    'dom7': ('dominant7', '7'),
    'dominant7': ('dominant7', '7'),
    'm7': ('minor7', 'm7'),
    'min7': ('minor7', 'm7'),
    'minor7': ('minor7', 'm7'),
    'maj7': ('major7', 'maj7'),
    'major7': ('major7', 'maj7'),
    'aug': ('augmented', 'aug'),
    'augmented': ('augmented', 'aug'),
    '+': ('augmented', 'aug'),
    'sus2': ('suspended2', 'sus2'),
    'sus4': ('suspended4', 'sus4'),
    '6': ('sixth', '6'),
    'm6': ('minor6', 'm6'),
    'min6': ('minor6', 'm6'),
    'add9': ('add9', 'add9'),
    '9': ('dominant9', '9'),
    'm9': ('minor9', 'm9'),
    'min9': ('minor9', 'm9'),
    'maj9': ('major9', 'maj9'),
    'major9': ('major9', 'maj9'),
    'dim7': ('diminished7', 'dim7'),
    'm7b5': ('half_diminished7', 'm7b5'),
    'ø': ('half_diminished7', 'm7b5'),
    'ø7': ('half_diminished7', 'm7b5'),
}
CHORD_INTERVALS = {
    'major': [0, 4, 7],
    'minor': [0, 3, 7],
    'diminished': [0, 3, 6],
    'dominant7': [0, 4, 7, 10],
    'minor7': [0, 3, 7, 10],
    'major7': [0, 4, 7, 11],
    'augmented': [0, 4, 8],
    'suspended2': [0, 2, 7],
    'suspended4': [0, 5, 7],
    'sixth': [0, 4, 7, 9],
    'minor6': [0, 3, 7, 9],
    'add9': [0, 4, 7, 14],
    'dominant9': [0, 4, 7, 10, 14],
    'minor9': [0, 3, 7, 10, 14],
    'major9': [0, 4, 7, 11, 14],
    'diminished7': [0, 3, 6, 9],
    'half_diminished7': [0, 3, 6, 10],
}

gesture_start_time = 0
gesture_hold_threshold = 0.2  # seconds
pending_chord = None

def parse_chord_symbol(symbol):
    match = re.fullmatch(r'([A-Ga-g])([#b]?)(.*)', symbol.strip())
    if not match:
        raise ValueError(f"Invalid chord name: {symbol}")

    letter, accidental, suffix = match.groups()
    root_name = letter.upper()
    root_pitch = ROOT_PITCH_CLASSES[root_name]
    if accidental == '#':
        root_pitch += 1
    elif accidental == 'b':
        root_pitch -= 1
    root_pitch %= 12

    suffix = suffix.strip()
    if suffix in {'M7', 'M9'}:
        quality, quality_suffix = ('major7', 'maj7') if suffix == 'M7' else ('major9', 'maj9')
    else:
        quality_data = CHORD_QUALITIES.get(suffix.lower())
        if quality_data is None:
            supported = 'major/minor, 7, m7, maj7, dim/dim7, m7b5, aug, sus2/sus4, 6/m6, add9, 9, m9, or maj9'
            raise ValueError(f"Unsupported chord quality in {symbol!r}; use {supported}.")
        quality, quality_suffix = quality_data

    return (root_pitch, quality), f'{root_name}{accidental}{quality_suffix}'


def find_playable_guitar_voicing(root_pitch, quality):
    target_pitches = {(root_pitch + interval) % 12 for interval in CHORD_INTERVALS[quality]}

    for max_fret in range(13):
        string_frets = [
            [-1] + [fret for fret in range(max_fret + 1) if (open_note + fret) % 12 in target_pitches]
            for open_note in GUITAR_OPEN_STRINGS
        ]
        best_shape = None
        for frets in itertools.product(*string_frets):
            notes = [open_note + fret for open_note, fret in zip(GUITAR_OPEN_STRINGS, frets) if fret >= 0]
            if len(notes) < len(target_pitches) or len(set(notes)) != len(notes):
                continue
            pitches = {note % 12 for note in notes}
            if pitches != target_pitches or min(notes) % 12 != root_pitch or notes != sorted(notes):
                continue

            held_frets = [fret for fret in frets if fret > 0]
            if held_frets and max(held_frets) - min(held_frets) > 4:
                continue

            score = (6 - len(notes)) * 100 + sum(max(0, fret) for fret in frets)
            if best_shape is None or score < best_shape[0]:
                best_shape = (score, notes)

        if best_shape is not None:
            return best_shape[1]

    raise ValueError(f'No playable guitar voicing found for pitch class {root_pitch}, {quality}.')


def get_chord_notes(chord_identity, chord_table):
    target_pitch, quality = chord_identity
    anchor_root, anchor_pitch = min(
        ROOT_PITCH_CLASSES.items(),
        key=lambda item: abs((target_pitch - item[1] + 6) % 12 - 6),
    )
    shift = (target_pitch - anchor_pitch + 6) % 12 - 6
    if (anchor_root, quality) in chord_table:
        return [note + shift for note in chord_table[(anchor_root, quality)]]
    if chord_table is guitar_chords:
        return find_playable_guitar_voicing(target_pitch, quality)

    anchor_root_note = min(
        note for note in chord_table[(anchor_root, 'major')]
        if note % 12 == anchor_pitch
    )
    root_note = anchor_root_note + shift
    return [root_note + interval for interval in CHORD_INTERVALS[quality]]


def parse_song_chords(entered):
    gesture_slots = [
        (first_count, second_count)
        for first_count in range(1, 6)
        for second_count in range(first_count, 6)
    ]
    parsed = [parse_chord_symbol(symbol) for symbol in entered.split(',') if symbol.strip()]
    unique_chords = {}
    for chord_identity, label in parsed:
        unique_chords.setdefault(chord_identity, label)
    if not unique_chords:
        raise ValueError('Enter at least one chord.')
    if len(unique_chords) > len(gesture_slots):
        raise ValueError(f'Choose at most {len(gesture_slots)} unique chords.')
    return list(unique_chords.items())


def configure_song_chords(chord_table, chords, gestures):
    gesture_to_chord = {}
    for chord_identity, label in chords:
        gesture = gestures[chord_identity]
        if gesture in gesture_to_chord:
            raise ValueError('Each chord needs a different gesture.')
        gesture_to_chord[gesture] = (
            chord_identity,
            label,
            get_chord_notes(chord_identity, chord_table),
        )
    return gesture_to_chord


# Initialize MediaPipe
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(max_num_hands=2, min_detection_confidence=0.7, min_tracking_confidence=0.6)
mp_draw = mp.solutions.drawing_utils

# Custom hand overlay colors (BGR)
dot_color = (111, 0, 163)      # RGB 163, 0, 111
line_color = (235, 199, 252)  # RGB 252, 199, 235
hand_landmarks_style = mp.solutions.drawing_styles.get_default_hand_landmarks_style()
hand_connections_style = mp.solutions.drawing_styles.get_default_hand_connections_style()

for key in hand_landmarks_style:
    hand_landmarks_style[key].color = dot_color
    hand_landmarks_style[key].thickness = 3
    hand_landmarks_style[key].circle_radius = 2

for key in hand_connections_style:
    hand_connections_style[key].color = line_color
    hand_connections_style[key].thickness = 2

# Initialize MIDI
pygame.midi.init()
midi_out = pygame.midi.Output(0)
midi_out.set_instrument(49, 0)  # Channel 0: strings
vari_instrument = 24 # 0=piano, 24=guitar 
midi_out.set_instrument(vari_instrument, 1)   # Channel 1: chosen instrument

# Chord mapping
root_notes = ['C', 'D', 'E', 'F', 'G', 'A', 'B']
# Each shape lists frets from low E to high E; -1 means mute the string.
GUITAR_OPEN_STRINGS = [40, 45, 50, 55, 59, 64]
GUITAR_FRET_SHAPES = {
    ('C', 'major'): (-1, 3, 2, 0, 1, 0),
    ('C', 'minor'): (-1, 3, 5, 5, 4, 3),
    ('C', 'diminished'): (-1, 3, 4, 5, 4, -1),
    ('C', 'dominant7'): (-1, 3, 2, 3, 1, 3),
    ('C', 'minor7'): (-1, 3, 1, 3, 1, 3),
    ('C', 'major7'): (-1, 3, 2, 0, 0, 0),
    ('D', 'major'): (-1, -1, 0, 2, 3, 2),
    ('D', 'minor'): (-1, -1, 0, 2, 3, 1),
    ('D', 'diminished'): (-1, -1, 0, 1, 3, 1),
    ('D', 'dominant7'): (-1, -1, 0, 2, 1, 2),
    ('D', 'minor7'): (-1, -1, 0, 2, 1, 1),
    ('D', 'major7'): (-1, -1, 0, 2, 2, 2),
    ('E', 'major'): (0, 2, 2, 1, 0, 0),
    ('E', 'minor'): (0, 2, 2, 0, 0, 0),
    ('E', 'diminished'): (0, 1, 2, 0, -1, -1),
    ('E', 'dominant7'): (0, 2, 0, 1, 0, 0),
    ('E', 'minor7'): (0, 2, 0, 0, 0, 0),
    ('E', 'major7'): (0, 2, 1, 1, 0, 0),
    ('F', 'major'): (1, 3, 3, 2, 1, 1),
    ('F', 'minor'): (1, 3, 3, 1, 1, 1),
    ('F', 'diminished'): (1, 2, 3, 1, -1, -1),
    ('F', 'dominant7'): (1, 3, 1, 2, 1, 1),
    ('F', 'minor7'): (1, 3, 1, 1, 1, 1),
    ('F', 'major7'): (1, 3, 2, 2, 1, 1),
    ('G', 'major'): (3, 2, 0, 0, 0, 3),
    ('G', 'minor'): (3, 5, 5, 3, 3, 3),
    ('G', 'diminished'): (3, 4, 5, 3, -1, -1),
    ('G', 'dominant7'): (3, 2, 0, 0, 0, 1),
    ('G', 'minor7'): (3, 5, 3, 3, 3, 3),
    ('G', 'major7'): (3, 2, 0, 0, 0, 2),
    ('A', 'major'): (-1, 0, 2, 2, 2, 0),
    ('A', 'minor'): (-1, 0, 2, 2, 1, 0),
    ('A', 'diminished'): (-1, 0, 1, 2, 1, -1),
    ('A', 'dominant7'): (-1, 0, 2, 0, 2, 0),
    ('A', 'minor7'): (-1, 0, 2, 0, 1, 0),
    ('A', 'major7'): (-1, 0, 2, 1, 2, 0),
    ('B', 'major'): (-1, 2, 4, 4, 4, 2),
    ('B', 'minor'): (-1, 2, 4, 4, 3, 2),
    ('B', 'diminished'): (-1, 2, 3, 4, 3, -1),
    ('B', 'dominant7'): (-1, 2, 1, 2, 0, 2),
    ('B', 'minor7'): (-1, 2, 0, 2, 0, 2),
    ('B', 'major7'): (-1, 2, 4, 3, 4, 2),
}
guitar_chords = {
    key: [open_note + fret for open_note, fret in zip(GUITAR_OPEN_STRINGS, shape) if fret >= 0]
    for key, shape in GUITAR_FRET_SHAPES.items()
}


def validate_chord_dictionary(chords):
    expected = {
        'major': {0, 4, 7},
        'minor': {0, 3, 7},
        'diminished': {0, 3, 6},
        'dominant7': {0, 4, 7, 10},
        'minor7': {0, 3, 7, 10},
        'major7': {0, 4, 7, 11},
    }
    root_pc = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}

    for (root, quality), notes in chords.items():
        got = {n % 12 for n in notes}
        target = {(root_pc[root] + p) % 12 for p in expected[quality]}
        if got != target:
            raise ValueError(f"Chord mismatch: {root} {quality} -> notes={sorted(notes)} got={sorted(got)} expected={sorted(target)}")


validate_chord_dictionary(guitar_chords)
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



# Camera and combined chord-mapping interface
instrument_chords = guitar_chords if vari_instrument == 24 else piano_chords
cap = cv2.VideoCapture(0)
last_chord_notes = []
last_played_chord = None
song_gestures = {}
current_chords = []
gesture_boxes = {}
gesture_slots = [
    (first_count, second_count)
    for first_count in range(1, 6)
    for second_count in range(first_count, 6)
]
background_color = '#FCC7EB'
text_color = '#A3006F'


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


root = tk.Tk()
root.title('Air Chord')
root.geometry('1240x760')
root.minsize(1160, 640)
root.configure(bg=background_color)

style = ttk.Style(root)
style.theme_use('clam')
style.configure(
    'Chord.TCombobox',
    fieldbackground='white',
    background='white',
    foreground=text_color,
    arrowcolor=text_color,
)

header = tk.Label(
    root,
    text='AIR CHORD',
    bg=background_color,
    fg=text_color,
    font=('Segoe UI', 18, 'bold'),
    anchor='w',
    padx=20,
    pady=12,
)
header.pack(fill='x')

content = tk.Frame(root, bg=background_color, padx=16, pady=4)
content.pack(fill='both', expand=True)
content.grid_columnconfigure(0, weight=1, minsize=700)
content.grid_columnconfigure(1, weight=0, minsize=380)
content.grid_rowconfigure(0, weight=1)

camera_panel = tk.Frame(content, bg=background_color)
camera_panel.grid(row=0, column=0, sticky='nsew', padx=(0, 16))
camera_panel.grid_columnconfigure(0, weight=1)
camera_panel.grid_rowconfigure(1, weight=1)
tk.Label(
    camera_panel,
    text='CAMERA',
    bg=background_color,
    fg=text_color,
    font=('Segoe UI', 11, 'bold'),
    anchor='w',
).grid(row=0, column=0, sticky='ew', pady=(0, 8))
camera_label = tk.Label(
    camera_panel,
    text='Starting camera...',
    bg='#261322',
    fg='white',
    font=('Segoe UI', 14),
)
camera_label.grid(row=1, column=0, sticky='nsew')

sidebar = tk.Frame(content, bg=background_color, width=380)
sidebar.grid(row=0, column=1, sticky='nsew')
sidebar.grid_propagate(False)
tk.Label(
    sidebar,
    text='SONG CHORDS',
    bg=background_color,
    fg=text_color,
    font=('Segoe UI', 11, 'bold'),
    anchor='w',
).pack(fill='x', pady=(0, 6))
tk.Label(
    sidebar,
    text='Type chord names separated by commas',
    bg=background_color,
    fg=text_color,
    font=('Segoe UI', 9),
    anchor='w',
).pack(fill='x', pady=(0, 6))
chord_entry = tk.Entry(
    sidebar,
    bg='white',
    fg=text_color,
    insertbackground=text_color,
    relief='flat',
    font=('Segoe UI', 11),
)
chord_entry.pack(fill='x', ipady=8, pady=(0, 8))


def make_button(parent, text, command):
    return tk.Button(
        parent,
        text=text,
        command=command,
        bg=text_color,
        fg='white',
        activebackground='#7D0055',
        activeforeground='white',
        relief='flat',
        font=('Segoe UI', 10, 'bold'),
        padx=10,
        pady=7,
        cursor='hand2',
    )


load_button = make_button(sidebar, 'Load chords', None)
load_button.pack(fill='x', pady=(0, 8))
mapping_canvas = tk.Canvas(sidebar, bg=background_color, highlightthickness=0, height=380)
mapping_canvas.pack(fill='both', expand=True)
mapping_rows = tk.Frame(mapping_canvas, bg=background_color)
mapping_canvas_window = mapping_canvas.create_window((0, 0), window=mapping_rows, anchor='nw')
mapping_rows.bind(
    '<Configure>',
    lambda event: mapping_canvas.configure(scrollregion=mapping_canvas.bbox('all')),
)
mapping_canvas.bind(
    '<Configure>',
    lambda event: mapping_canvas.itemconfigure(mapping_canvas_window, width=event.width),
)
mapping_canvas.bind_all('<MouseWheel>', lambda event: mapping_canvas.yview_scroll(-1 * (event.delta // 120), 'units'))
status_label = tk.Label(
    sidebar,
    text='Load a song chord list to begin.',
    bg=background_color,
    fg=text_color,
    font=('Segoe UI', 9),
    wraplength=350,
    justify='left',
    anchor='w',
)
status_label.pack(side='bottom', fill='x', pady=(8, 4))
apply_button = make_button(sidebar, 'Apply gesture map', None)
apply_button.pack(side='bottom', fill='x', pady=(8, 0))


def load_chords():
    global current_chords
    try:
        parsed_chords = parse_song_chords(chord_entry.get())
    except ValueError as error:
        status_label.configure(text=str(error))
        return

    current_chords = parsed_chords
    gesture_boxes.clear()
    for widget in mapping_rows.winfo_children():
        widget.destroy()

    for index, (chord_identity, label) in enumerate(current_chords):
        row = tk.Frame(mapping_rows, bg=background_color)
        row.pack(fill='x', pady=3)
        tk.Label(
            row,
            text=label,
            bg=background_color,
            fg=text_color,
            font=('Segoe UI', 10, 'bold'),
            anchor='w',
            width=8,
        ).pack(side='left')
        choices = [f'{first} + {second}' for first, second in gesture_slots]
        gesture_box = ttk.Combobox(
            row,
            values=choices,
            state='readonly',
            style='Chord.TCombobox',
            width=14,
        )
        gesture_box.current(index)
        gesture_box.pack(side='right', fill='x', expand=True)
        gesture_boxes[chord_identity] = gesture_box

    status_label.configure(text=f'{len(current_chords)} chords loaded with default gestures.')
    apply_gesture_map()


def stop_current_chord():
    global last_chord_notes, last_played_chord, pending_chord
    for note in last_chord_notes:
        midi_out.note_off(note, 1)
        midi_out.note_off(note, 0)
    last_chord_notes = []
    last_played_chord = None
    pending_chord = None


def apply_gesture_map():
    global song_gestures
    if not current_chords:
        status_label.configure(text='Load a chord list first.')
        return

    gestures = {}
    for chord_identity, gesture_box in gesture_boxes.items():
        first, second = (int(part.strip()) for part in gesture_box.get().split('+'))
        gestures[chord_identity] = tuple(sorted((first, second)))

    try:
        updated_map = configure_song_chords(instrument_chords, current_chords, gestures)
    except ValueError as error:
        status_label.configure(text=str(error))
        return

    stop_current_chord()
    song_gestures = updated_map
    mapping_text = ', '.join(
        f'{gesture[0]}+{gesture[1]}: {label}'
        for gesture, (_, label, _) in song_gestures.items()
    )
    status_label.configure(text=f'Mapping active: {mapping_text}')


load_button.configure(command=load_chords)
apply_button.configure(command=apply_gesture_map)


def update_camera():
    global gesture_start_time, pending_chord, last_chord_notes, last_played_chord
    ret, frame = cap.read()
    if not ret:
        camera_label.configure(text='Camera unavailable. Check that it is connected.', image='')
        root.after(250, update_camera)
        return

    frame = cv2.flip(frame, 1)
    result = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    fingers_up = []

    if result.multi_hand_landmarks:
        for hand in result.multi_hand_landmarks:
            mp_draw.draw_landmarks(
                frame,
                hand,
                mp_hands.HAND_CONNECTIONS,
                hand_landmarks_style,
                hand_connections_style,
            )
            fingers_up.append(get_fingers_up(hand))

    if len(fingers_up) == 2 and all(not fingers for fingers in fingers_up):
        stop_current_chord()
    elif len(fingers_up) == 2:
        gesture = tuple(sorted((len(fingers_up[0]), len(fingers_up[1]))))
        chord_data = song_gestures.get(gesture)
        if chord_data:
            chord_identity, label, chord_notes = chord_data
            if chord_identity != pending_chord:
                pending_chord = chord_identity
                gesture_start_time = time.time()
            elif time.time() - gesture_start_time >= gesture_hold_threshold and chord_identity != last_played_chord:
                for note in last_chord_notes:
                    midi_out.note_off(note, 1)
                    midi_out.note_off(note, 0)
                for note in chord_notes:
                    midi_out.note_on(note, 100, 1)
                    midi_out.note_on(note, 50, 0)
                last_chord_notes = chord_notes
                last_played_chord = chord_identity
                status_label.configure(text=f'Playing {label}')
        else:
            pending_chord = None
    else:
        stop_current_chord()

    success, encoded_frame = cv2.imencode('.png', frame)
    if success:
        image_data = base64.b64encode(encoded_frame).decode('ascii')
        camera_image = tk.PhotoImage(data=image_data)
        camera_label.configure(image=camera_image, text='')
        camera_label.image = camera_image

    root.after(15, update_camera)


def close_app():
    stop_current_chord()
    cap.release()
    hands.close()
    cv2.destroyAllWindows()
    midi_out.close()
    pygame.midi.quit()
    root.destroy()


root.protocol('WM_DELETE_WINDOW', close_app)
root.bind('<Escape>', lambda event: close_app())
root.after(0, update_camera)
root.mainloop()
