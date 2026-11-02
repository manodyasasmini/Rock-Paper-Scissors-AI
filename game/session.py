"""Game state, scoring and keyboard rules. Knows nothing about cameras or drawing."""
from collections import deque

import config
from ai.engine import CHOICES, AdaptiveEngine, explain
from game import leaderboard
from game.settings import Settings
from game.summary import RoundRecord, summarize

BEATS = {"ROCK": "SCISSORS", "PAPER": "ROCK", "SCISSORS": "PAPER"}
GUEST_NAME = "Guest"  # never saved: each guest starts fresh and leaves nothing behind

STATE_START = "START"                    # Leaderboard and "press SPACE"
STATE_NAME_INPUT = "NAME_INPUT"          # Step 1: typing a name
STATE_CAMERA_CHECK = "CAMERA_CHECK"      # Step 2: hold a hand up, then the match begins
STATE_IDLE = "IDLE"                      # Between matches: waiting to start a round
STATE_COUNTDOWN = "COUNTDOWN"            # 3, 2, 1 countdown
STATE_SHOW_RESULT = "RESULT"             # Showing winner of current round
STATE_SUMMARY = "SUMMARY"                # End of a match: the report card
STATE_REPLAY = "REPLAY"                  # Every round of the match, with what the AI expected

# States where a visitor may have walked away
QUIET_STATES = (STATE_NAME_INPUT, STATE_CAMERA_CHECK, STATE_IDLE, STATE_SHOW_RESULT, STATE_SUMMARY, STATE_REPLAY)

ACTION_QUIT = "quit"
ACTION_TOGGLE_FULLSCREEN = "fullscreen"

KEY_ENTER = 13
KEY_ESC = 27
KEY_BACKSPACE = 8
KEY_SPACE = 32
KEY_CTRL_A = 1

ADMIN_ROWS = 5


def determine_winner(p_move, a_move):
    if p_move not in CHOICES:
        return "INVALID"
    if p_move == a_move:
        return "TIE"
    if BEATS[p_move] == a_move:
        return "PLAYER"
    return "AI"


class GameSession:
    def __init__(self, store, engine=None, settings=None):
        self.store = store
        self.engine = engine or AdaptiveEngine()
        self.settings = settings or Settings()

        self.state = STATE_START
        self.state_start_time = 0.0
        self.countdown_duration = config.COUNTDOWN_SECONDS

        self.player_name = None  # None until a profile is chosen, so nothing is saved before then
        self.input_text = ""
        self.last_activity = 0.0
        self.hold_since = None
        self.check_passed = False   # the camera check is done; the player starts the match with SPACE
        self.admin_open = False
        self.admin_clear_armed = False
        self.leaderboard_rows = []
        self.rank = None

        self.learn_mode = self.settings.learn_mode
        self._reset_match()
        self.refresh_leaderboard()

    # ---- derived values ----
    @property
    def match_rounds(self):
        return self.settings.match_rounds

    @property
    def tracking_active(self):
        return self.state in (STATE_CAMERA_CHECK, STATE_IDLE, STATE_COUNTDOWN, STATE_SHOW_RESULT)

    @property
    def match_complete(self):
        return self.match_rounds > 0 and len(self.match_log) >= self.match_rounds

    @property
    def is_guest(self):
        return self.player_name in (None, GUEST_NAME)

    @property
    def round_number(self):
        """The round being played, or just played while its result is on screen."""
        played = len(self.match_log)
        shown = played if self.state == STATE_SHOW_RESULT and played else played + 1
        return min(shown, self.match_rounds) if self.match_rounds else shown

    def hold_progress(self, now):
        """0 to 1: how long the player's hand has been held still on the camera check."""
        if self.check_passed:
            return 1.0
        if self.hold_since is None:
            return 0.0
        return max(0.0, min(1.0, (now - self.hold_since) / config.HOLD_TO_START_SECONDS))

    def idle_remaining(self, now):
        """Seconds left before the game returns to the start screen, or None while the visitor is active."""
        if self.state not in QUIET_STATES:
            return None
        quiet = now - self.last_activity
        if quiet < self.settings.idle_seconds:
            return None
        return max(0.0, self.settings.idle_seconds + config.IDLE_WARNING_SECONDS - quiet)

    # ---- state changes ----
    def _reset_match(self):
        self.score_player = self.score_ai = self.score_ties = 0
        self.streak = 0
        self.best_streak = 0
        self.match_history = deque(maxlen=config.MATCH_HISTORY_LENGTH)
        self.match_log = []      # one RoundRecord per round with a detected move
        self.summary = None
        self.player_move = self.ai_move = self.round_result = None
        self.prediction = None
        self.explanation = ""

    def refresh_leaderboard(self):
        self.leaderboard_rows = leaderboard.top(self.store.load_all())

    def go_to_start(self):
        self.save()
        self.player_name = None
        self.input_text = ""
        self.hold_since = None
        self._reset_match()
        self.refresh_leaderboard()
        self.state = STATE_START

    def start_new_match(self, now=0.0):
        self._reset_match()
        self.hold_since = None
        self.last_activity = now
        self.state = STATE_IDLE

    def save(self):
        if self.is_guest:
            return
        self.store.save_player(self.player_name, {
            "score_player": self.score_player,
            "score_ai": self.score_ai,
            "score_ties": self.score_ties,
            "best_streak": self.best_streak,
            "engine": self.engine.to_dict(),
            # The first version's format, so rps_game.py can still read this profile
            "transitions": self.engine.legacy_transitions(),
        })

    def _canonical_name(self, typed):
        """An empty name or "guest" plays as a guest; a name that differs only in case is the same player."""
        name = typed.strip()
        if not name or name.lower() == GUEST_NAME.lower():
            return GUEST_NAME
        for existing in self.store.load_all():
            if existing.lower() == name.lower():
                return existing
        return name

    def switch_to_player(self, name):
        self.player_name = self._canonical_name(name)
        self._reset_match()
        saved = None if self.is_guest else self.store.load_all().get(self.player_name)
        self.engine.load_record(saved)
        if not saved:
            self.save()

    def start_round(self, now):
        self.prediction = self.engine.lock_move()
        self.hold_since = None
        self.state = STATE_COUNTDOWN
        self.state_start_time = now
        self.last_activity = now

    def update(self, now, live_gesture):
        if self.state == STATE_COUNTDOWN and now - self.state_start_time >= self.countdown_duration:
            self._finish_round(now, live_gesture)
            return

        if live_gesture and self.state in QUIET_STATES:
            self.last_activity = now
        if self.state == STATE_CAMERA_CHECK and not self.check_passed and not self.admin_open:
            if live_gesture is None:
                self.hold_since = None
            elif self.hold_since is None:
                self.hold_since = now
            elif now - self.hold_since >= config.HOLD_TO_START_SECONDS:
                self.check_passed = True
        if self.state in QUIET_STATES and self.idle_remaining(now) == 0.0:
            self.admin_open = False
            self.go_to_start()

    def _finish_round(self, now, live_gesture):
        self.player_move = live_gesture
        self.ai_move = self.prediction.ai_move
        self.round_result = determine_winner(self.player_move, self.ai_move)

        if self.round_result == "PLAYER":
            self.score_player += 1
            self.streak += 1
            self.best_streak = max(self.best_streak, self.streak)
            self.match_history.append("W")
        elif self.round_result == "AI":
            self.score_ai += 1
            self.streak = 0
            self.match_history.append("L")
        elif self.round_result == "TIE":
            self.score_ties += 1
            self.match_history.append("D")

        self.explanation = explain(self.prediction, self.player_move)
        if self.round_result != "INVALID":
            expected = self.prediction.expected
            self.match_log.append(RoundRecord(
                self.player_move, self.ai_move, self.round_result, expected,
                self.prediction.probs[expected] if expected else 0.0))
        self.engine.observe(self.player_move, self.ai_move)
        self.save()
        self.state = STATE_SHOW_RESULT
        self.state_start_time = now
        self.last_activity = now

    def _finish_match(self):
        self.summary = summarize(self.match_log)
        self.rank = None
        if not self.is_guest:
            result = leaderboard.result_of(self.match_log)
            best = self.store.load_all().get(self.player_name, {}).get("best_match")
            if best is None or leaderboard.match_score_key(result) > leaderboard.match_score_key(best):
                self.store.save_player(self.player_name, {"best_match": result})
            self.rank = leaderboard.rank_of(self.store.load_all(), self.player_name)
        self.state = STATE_SUMMARY

    # ---- keyboard ----
    def handle_key(self, key, now):
        """Apply a key press. Returns an ACTION_ the window has to act on, or None."""
        was_warned = self.idle_remaining(now) is not None
        self.last_activity = now
        if was_warned and key not in (ord("q"), ord("Q")):
            return None  # the first key just answers "Still there?"

        if key == KEY_CTRL_A and self.state != STATE_NAME_INPUT:
            self.admin_open = not self.admin_open
            self.admin_clear_armed = False
            return None
        if self.admin_open:
            return self._handle_admin_key(key)

        if self.state == STATE_NAME_INPUT:
            self._handle_name_key(key)
            return None

        if key in (ord("q"), ord("Q")):
            self.save()
            return ACTION_QUIT
        if key in (ord("f"), ord("F")):
            return ACTION_TOGGLE_FULLSCREEN

        if self.state == STATE_START:
            if key in (KEY_SPACE, KEY_ENTER):
                self.input_text = ""
                self.state = STATE_NAME_INPUT
        elif self.state == STATE_CAMERA_CHECK:
            if key == KEY_SPACE:
                self.start_round(now)
            elif key == KEY_ESC:
                self.state = STATE_NAME_INPUT
                self.hold_since = None
                self.check_passed = False
        elif self.state == STATE_SUMMARY:
            if key == KEY_SPACE:
                self.start_new_match(now)
            elif key in (ord("r"), ord("R")):
                self.state = STATE_REPLAY
            elif key in (ord("n"), ord("N"), ord("p"), ord("P")):
                self.go_to_start()
        elif self.state == STATE_REPLAY:
            if key in (KEY_SPACE, KEY_ESC, ord("r"), ord("R")):
                self.state = STATE_SUMMARY
        else:  # IDLE, COUNTDOWN, RESULT
            if key in (ord("p"), ord("P")):
                self.go_to_start()
            elif key in (ord("h"), ord("H")):
                self.learn_mode = not self.learn_mode
            elif key == KEY_SPACE:
                if self.state == STATE_SHOW_RESULT and self.match_complete:
                    self._finish_match()
                elif self.state in (STATE_IDLE, STATE_SHOW_RESULT):
                    self.start_round(now)
        return None

    def _handle_name_key(self, key):
        if key == KEY_ENTER:
            self.switch_to_player(self.input_text)
            self.hold_since = None
            self.check_passed = False
            self.state = STATE_CAMERA_CHECK
        elif key == KEY_ESC:
            self.state = STATE_START
        elif key == KEY_BACKSPACE:
            self.input_text = self.input_text[:-1]
        elif 32 <= key <= 126 and len(self.input_text) < config.NAME_MAX_LENGTH:
            self.input_text += chr(key)

    def _handle_admin_key(self, key):
        row = key - ord("0")
        if key == KEY_ESC:
            self.admin_open = False
            self.admin_clear_armed = False
            return None
        if not 1 <= row <= ADMIN_ROWS:
            return None
        if row == 5:
            if self.admin_clear_armed:
                self.store.clear_best_matches()
                self.refresh_leaderboard()
            self.admin_clear_armed = not self.admin_clear_armed
            return None
        self.admin_clear_armed = False
        if row == 1:
            self.settings.cycle_match_rounds()
        elif row == 2:
            self.settings.learn_mode = not self.settings.learn_mode
            self.learn_mode = self.settings.learn_mode
        elif row == 3:
            self.settings.skeleton_only = not self.settings.skeleton_only
        elif row == 4:
            self.settings.cycle_idle_seconds()
        self.settings.save()
        return None
