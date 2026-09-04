import cv2
import mediapipe as mp

mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils

# Initialize MediaPipe Hands
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.6
)

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

WINDOW_NAME = "MediaPipe Rock Paper Scissors"
cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
cv2.setWindowProperty(WINDOW_NAME, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

# Landmark IDs for fingertips and intermediate joints
# [Index, Middle, Ring, Pinky]
FINGER_TIPS = [8, 12, 16, 20]
FINGER_PIPS = [6, 10, 14, 18]

print("Point your hand at the camera! Press 'f' for fullscreen toggle, 'q' to exit.")

while cap.isOpened():
    success, frame = cap.read()
    if not success:
        break

    # Flip horizontally for a natural mirror view
    frame = cv2.flip(frame, 1)
    h, w, _ = frame.shape

    # MediaPipe expects RGB format
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb_frame)

    gesture = "Waiting..."

    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            # Draw the skeletal joints on the screen
            mp_draw.draw_landmarks(
                frame, hand_landmarks, mp_hands.HAND_CONNECTIONS
            )

            landmarks = hand_landmarks.landmark

            # Check which fingers are extended (fingertip is above intermediate knuckle)
            # In image coordinates, smaller Y means higher on screen
            fingers_extended = []
            for tip, pip in zip(FINGER_TIPS, FINGER_PIPS):
                is_extended = landmarks[tip].y < landmarks[pip].y
                fingers_extended.append(is_extended)

            # Check thumb extension (distance relative to pinky knuckle base)
            thumb_extended = landmarks[4].x < landmarks[3].x if landmarks[17].x > landmarks[5].x else landmarks[4].x > landmarks[3].x

            # Count open fingers
            open_count = sum(fingers_extended)

            # Classify gesture based on extended fingers
            if open_count == 0:
                gesture = "ROCK"
            elif open_count >= 4:
                gesture = "PAPER"
            elif fingers_extended[0] and fingers_extended[1] and not fingers_extended[2] and not fingers_extended[3]:
                gesture = "SCISSORS"
            else:
                gesture = "Unknown"

    # Display gesture label
    color = (0, 255, 0) if gesture in ["ROCK", "PAPER", "SCISSORS"] else (0, 165, 255)
    cv2.putText(frame, f"Gesture: {gesture}", (30, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 3)

    cv2.imshow(WINDOW_NAME, frame)

    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    elif key == ord('f') or key == ord('F'):
        current_prop = cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_FULLSCREEN)
        new_prop = cv2.WINDOW_NORMAL if current_prop == cv2.WINDOW_FULLSCREEN else cv2.WINDOW_FULLSCREEN
        cv2.setWindowProperty(WINDOW_NAME, cv2.WND_PROP_FULLSCREEN, new_prop)

cap.release()
cv2.destroyAllWindows()