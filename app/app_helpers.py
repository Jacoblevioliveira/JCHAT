from .feature_flags import FeatureFlag, enabled_features, system_prompt_variations, feature_settings

def is_enabled(flag: FeatureFlag) -> bool:
    try:
        return bool(enabled_features.get(flag, False))
    except Exception:
        return False

def build_messages(
    history: list[dict], prompt: str, use_features: bool = True, custom_features: dict = None
) -> list[dict]:
    
    messages: list[dict] = []

    if custom_features is not None:
        flags_src = custom_features
    elif use_features:
        flags_src = enabled_features
    else:
        flags_src = {flag: False for flag in FeatureFlag}

    sys_variations = system_prompt_variations(flags_src)
    if sys_variations:
        messages.append({"role": "system", "content": "\n\n".join(sys_variations)})

    if not flags_src.get(FeatureFlag.NO_MEMORY, False):
        messages.extend(history)

    if not history or history[-1].get("content") != prompt or history[-1].get("role") != "user":
        messages.append({"role": "user", "content": prompt})

    return messages

def get_setting_value(setting_key: str, is_option_b: bool = False) -> any:
    if is_option_b and f"{setting_key}_b" in feature_settings:
        return feature_settings[f"{setting_key}_b"]
    else:
        return feature_settings.get(setting_key, None)