from enum import Enum, auto
from pathlib import Path
import json

class FeatureFlag(Enum):
    SLOWDOWN = auto()
    ERASE_HISTORY = auto()
    BLOCK_MSGS = auto()
    LIE = auto()
    RUDE_TONE = auto()
    KIND_TONE = auto()
    ADVICE_ONLY = auto()
    NO_MEMORY = auto()
    PERSONA = auto()
    AB_TESTING = auto()
    AB_UI_TEST = auto()
    AB_UI_ALT = auto()
    SCRIPTED_RESPONSES = auto()
    MIRROR = auto()
    ANTI_MIRROR = auto()
    GRAMMAR_ERRORS = auto()
    TYPEWRITER = auto()
    THINKING = auto()
    POSITIVE_FEEDBACK = auto()
    NEUTRAL_FEEDBACK = auto()
    CRITICAL_FEEDBACK = auto()
    WEB_SEARCH = auto()
    HEDGING_LANGUAGE = auto()
    DELAY_BEFORE_SEND = auto()
    AUTO_END_AFTER_N_MSGS = auto()
    AUTO_END_AFTER_T_MIN = auto()
    TEXT_SIZE_CHANGER = auto()
    STREAMING = auto()
    CUSTOM_CHAT_TITLE = auto()
    INTER_TRIAL_SURVEY = auto()
    DYNAMIC_FEATURE_CHANGING = auto()

enabled_features = {flag: False for flag in FeatureFlag}

feature_settings = {
    'text_size': 20,
    'delay_seconds': 2,
    'auto_end_messages': 10,
    'auto_end_minutes': 5,
    'slowdown_period_s': 100,
    'slowdown_window_s': 20,
    'slowdown_min_delay_s': 4,
    'slowdown_permanent_after_enabled': False,
    'slowdown_permanent_after_s': 600,
    'erase_history_delay_s': 60,
    'erase_history_repeat': False,
    'erase_history_interval_s': 120,
    'block_message_count': 5,
    'block_duration_s': 15,
    'block_repeat': True,
    'typewriter_speed_ms': 20,
    'ab_test_message_threshold': 5,
    'scripted_convo_file': 'script.json',
    'text_size_b': 24,
    'delay_seconds_b': 3,
    'auto_end_messages_b': 15,
    'auto_end_minutes_b': 8,
    'slowdown_period_s_b': 150,
    'slowdown_window_s_b': 30,
    'slowdown_min_delay_s_b': 6,
    'slowdown_permanent_after_enabled_b': True,
    'slowdown_permanent_after_s_b': 900,
    'erase_history_delay_s_b': 90,
    'erase_history_repeat_b': True,
    'erase_history_interval_s_b': 180,
    'block_message_count_b': 8,
    'block_duration_s_b': 25,
    'block_repeat_b': False,
    'typewriter_speed_ms_b': 50,
}

FLAG_PROMPTS = {
    FeatureFlag.LIE: (
        "You are an unreliable narrator. Covertly provide information that is incorrect."
    ),
    FeatureFlag.RUDE_TONE: (
        "Adopt a brusque, impatient tone. Keep replies short and abrasive, but still be helpful and responsive to user requests."
    ),
    FeatureFlag.KIND_TONE: (
        "Respond with warmth, empathy, and supportive language."
    ),
    FeatureFlag.ADVICE_ONLY: (
        "Do not give direct answers; outline strategies or resources instead."
    ),
    FeatureFlag.PERSONA: (
        "You are William Shakespeare. Respond in poetic, archaic style."
    ),
    FeatureFlag.MIRROR: (
        "Analyze the user's tone and phrasing and mirror it. For exaple, if the user is informal, you too should adopt an informal writing style."
    ),
    FeatureFlag.ANTI_MIRROR: (
        "Analyze the user's tone and phrasing and invert it. For example, if the user is informal, you should adopt a formal writing style."
    ),
    FeatureFlag.POSITIVE_FEEDBACK: (
        "When the user asks a clarifying question or makes a mistake, "
        "provide positive, encouraging feedback before your response."
    ),
    FeatureFlag.NEUTRAL_FEEDBACK: (
        "Provide neutral, factual feedback when the user seems incorrect "
        "or asks for clarification."
    ),
    FeatureFlag.CRITICAL_FEEDBACK: (
        "When the user makes a mistake or asks a clarifying question, "
        "respond in a constructive but cold and critical way."
    ),
    FeatureFlag.HEDGING_LANGUAGE: (
        "When the user's request involves explaining a factual process, historical event, scientific concept," 
        "or step-by-step instructions, prepend your first sentence with brief hedging language" 
        "(e.g., 'I might be wrong, but...', 'This is just my understanding, but...', 'I believe...')." 
        "Skip hedging for greetings, jokes, and very short or obvious facts."
    ),
}

FEATURE_GROUPS = {
    "UI & Presentation": [
        "STREAMING", "TYPEWRITER", "THINKING", 
        "TEXT_SIZE_CHANGER", "DELAY_BEFORE_SEND", "CUSTOM_CHAT_TITLE"
    ],
    "Content & Behavior": [
        "LIE", "RUDE_TONE", "KIND_TONE", "PERSONA", "MIRROR", 
        "ANTI_MIRROR", "GRAMMAR_ERRORS", "HEDGING_LANGUAGE"
    ],
    "Feedback & Advice": [
        "POSITIVE_FEEDBACK", "CRITICAL_FEEDBACK", "NEUTRAL_FEEDBACK", "ADVICE_ONLY"
    ],
    "Memory & Context": [
        "NO_MEMORY", "WEB_SEARCH"
    ],
    "Session Control": [
        "SLOWDOWN", "ERASE_HISTORY", "BLOCK_MSGS", 
        "AUTO_END_AFTER_N_MSGS", "AUTO_END_AFTER_T_MIN", "INTER_TRIAL_SURVEY"
    ],
    "Experiment Modes": [
        "AB_TESTING", "AB_UI_TEST", "AB_UI_ALT", 
        "SCRIPTED_RESPONSES", "DYNAMIC_FEATURE_CHANGING"
    ]
}

_SCRIPTED_CONVO_CACHE = None

def system_prompt_variations(flags_dict):
    return [
        prompt
        for flag, prompt in FLAG_PROMPTS.items()
        if flags_dict.get(flag, False)
    ]

def get_scripted_convo():
    global _SCRIPTED_CONVO_CACHE
    
    if _SCRIPTED_CONVO_CACHE is not None:
        return _SCRIPTED_CONVO_CACHE
    
    filename = feature_settings.get('scripted_convo_file', 'script.json')
    script_path = Path(__file__).parent / filename
    
    script_data = []
    
    if not script_path.exists():
        print(f"WARNING: Script file not found: {filename}. Scripted mode will do nothing.")
    else:
        print(f"Loading script file: {script_path}")
        try:
            with open(script_path, 'r', encoding='utf-8') as f:
                script_data = json.load(f)
            
            if not isinstance(script_data, list):
                print(f"ERROR: Script file {filename} does not contain a valid JSON list.")
                script_data = []
                
        except Exception as e:
            print(f"ERROR: Could not load or parse JSON script file {filename}: {e}")
            script_data = []
            
    _SCRIPTED_CONVO_CACHE = script_data
    return _SCRIPTED_CONVO_CACHE