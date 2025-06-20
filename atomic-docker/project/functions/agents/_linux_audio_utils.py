import subprocess
import re
import logging
from typing import List, Optional, Dict, Any

def _parse_pactl_output(output: str) -> List[Dict[str, Any]]:
    """
    Parses pactl list output (e.g., sink-inputs or sinks) into a list of property dictionaries.
    Each item in the list represents a block (e.g., a "Sink Input" or "Sink").
    """
    items = []
    current_item = None
    # Regex to capture the start of a new block (e.g., "Sink Input #0" or "Sink #0")
    # and also to capture key-value pairs within a block.
    # Handles cases where property values span multiple lines (though simple for now)
    block_start_pattern = re.compile(r"^(Sink Input #|Sink #)(\d+)", re.IGNORECASE)
    # Property pattern: Catches indented lines, assumes property key until '=', value after.
    # Value can contain spaces and various characters. Strips leading/trailing quotes from value.
    property_pattern = re.compile(r"^\s+([\w\.\-]+)\s*=\s*\"?(.*?)\"?$", re.IGNORECASE)
    # More specific property pattern for keys that are known and simple
    simple_property_pattern = re.compile(r"^\s+([\w\.\s-]+):\s*(.*)", re.IGNORECASE)


    for line in output.splitlines():
        block_match = block_start_pattern.match(line)
        if block_match:
            if current_item is not None:
                items.append(current_item)
            item_type = "sink_input" if block_match.group(1).lower() == "sink input #" else "sink"
            current_item = {"_type": item_type, "_index": int(block_match.group(2))}
            continue

        if current_item is None:
            continue # Skip lines until a block starts

        prop_match = property_pattern.match(line)
        if prop_match:
            key = prop_match.group(1).strip().replace(" ", "_").lower() # Normalize key
            value = prop_match.group(2).strip()
            current_item[key] = value
        else:
            simple_prop_match = simple_property_pattern.match(line)
            if simple_prop_match:
                key = simple_prop_match.group(1).strip().replace(" ", "_").lower().replace(":", "")
                value = simple_prop_match.group(2).strip()
                current_item[key] = value

    if current_item is not None:
        items.append(current_item)
    return items


def _get_linux_app_monitor_source(target_app_names: List[str], logger: logging.Logger) -> Optional[str]:
    """
    Attempts to find a PulseAudio monitor source associated with a running application.

    This function is specific to Linux systems using PulseAudio (`pactl`).
    It tries to find a sink input linked to one of the `target_app_names`
    (by checking application.name, application.process.binary, or media.name)
    and then finds the monitor source associated with that sink input's sink.

    Args:
        target_app_names: A list of application names or binary names to search for
                          (e.g., ['zoom', 'chrome', 'firefox']). Case-insensitive substring match.
        logger: A logger instance for logging messages.

    Returns:
        The name of the monitor source device if found, otherwise None.
    """
    if not sys.platform.startswith('linux'):
        logger.debug("Not a Linux system, skipping pactl audio detection.")
        return None

    try:
        # 1. List sink inputs to find the one associated with the target application
        pactl_sink_inputs_cmd = ["pactl", "list", "short", "sink-inputs"] # Use short form for easier parsing
        # Example short output: 0	116	122	protocol-native.c	float32le 2ch 48000Hz	RUNNING
        # The full 'pactl list sink-inputs' is more reliable for properties.
        pactl_sink_inputs_cmd_full = ["pactl", "list", "sink-inputs"]

        process = subprocess.run(pactl_sink_inputs_cmd_full, capture_output=True, text=True, check=True)
        sink_inputs_output = process.stdout
        # logger.debug(f"pactl list sink-inputs output:\n{sink_inputs_output}")

        parsed_sink_inputs = _parse_pactl_output(sink_inputs_output)
        # logger.debug(f"Parsed sink inputs: {parsed_sink_inputs}")

        target_sink_index_str: Optional[str] = None
        for si in parsed_sink_inputs:
            if si.get("_type") != "sink_input": continue

            app_name = si.get("properties", {}).get("application.name", "").lower()
            app_binary = si.get("properties", {}).get("application.process.binary", "").lower()
            media_name = si.get("properties", {}).get("media.name", "").lower() # Often useful, e.g., "Playback Stream"

            # Check against each target name
            for target_name_part in target_app_names:
                target_lower = target_name_part.lower()
                if (target_lower in app_name or
                    target_lower in app_binary or
                    (media_name and target_lower in media_name)): # Media name can be None

                    # Simpler parsing for properties block from full output
                    # Look for "Sink: <digits>"
                    sink_prop = si.get("sink") # From simple_property_pattern if it worked
                    if isinstance(sink_prop, str) and sink_prop.isdigit():
                         target_sink_index_str = sink_prop
                         logger.info(f"Found matching application sink input #{si.get('_index')} for '{target_name_part}' on sink index {target_sink_index_str} (App: {app_name}, Binary: {app_binary}, Media: {media_name})")
                         break # Found a match
            if target_sink_index_str:
                break

        if not target_sink_index_str:
            logger.info(f"No running sink input found matching target applications: {target_app_names}")
            return None

        # 2. List sinks to find the monitor source for the identified sink
        pactl_sinks_cmd = ["pactl", "list", "sinks"]
        process = subprocess.run(pactl_sinks_cmd, capture_output=True, text=True, check=True)
        sinks_output = process.stdout
        # logger.debug(f"pactl list sinks output:\n{sinks_output}")

        parsed_sinks = _parse_pactl_output(sinks_output)
        # logger.debug(f"Parsed sinks: {parsed_sinks}")

        for sink_info in parsed_sinks:
            if sink_info.get("_type") == "sink" and str(sink_info.get("_index")) == target_sink_index_str:
                monitor_source_name = sink_info.get("monitor_source")
                if monitor_source_name:
                    logger.info(f"Found monitor source for sink index {target_sink_index_str}: '{monitor_source_name}'")
                    return monitor_source_name
                else:
                    logger.warning(f"Sink index {target_sink_index_str} found, but it has no 'Monitor Source' property. Properties: {sink_info}")
                    return None

        logger.warning(f"Could not find sink details for index {target_sink_index_str} from application.")
        return None

    except FileNotFoundError:
        logger.warning("`pactl` command not found. Cannot auto-detect Linux application audio source. Please ensure PulseAudio utilities are installed.")
        return None
    except subprocess.CalledProcessError as e:
        logger.error(f"Error executing `pactl` command: {e}. Output: {e.stderr}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during Linux audio source detection: {e}", exc_info=True)
        return None

if __name__ == '__main__':
    # Basic test (requires a running audio application, e.g., Chrome playing YouTube)
    logging.basicConfig(level=logging.DEBUG)
    test_logger = logging.getLogger("LinuxAudioTest")

    # Test with common browser names
    browser_apps = ['chrome', 'firefox', 'msedge', 'chromium', 'opera']
    monitor = _get_linux_app_monitor_source(browser_apps, test_logger)
    if monitor:
        test_logger.info(f"Test successful: Found monitor source for browsers: {monitor}")
    else:
        test_logger.warning("Test: No monitor source found for browsers. Ensure a browser is playing audio.")

    # Test with a specific application name (if you have one running, e.g., 'Spotify')
    # spotify_monitor = _get_linux_app_monitor_source(['spotify'], test_logger)
    # if spotify_monitor:
    #     test_logger.info(f"Test successful: Found monitor source for Spotify: {spotify_monitor}")
    # else:
    #     test_logger.warning("Test: No monitor source found for Spotify. Ensure Spotify is playing audio.")

    # Test with a non-existent app
    non_existent_monitor = _get_linux_app_monitor_source(['nonexistentapp123'], test_logger)
    if not non_existent_monitor:
        test_logger.info("Test successful: Correctly found no monitor for non-existent app.")
    else:
        test_logger.error(f"Test failed: Found monitor for non-existent app: {non_existent_monitor}")

[end of atomic-docker/project/functions/agents/_linux_audio_utils.py]
