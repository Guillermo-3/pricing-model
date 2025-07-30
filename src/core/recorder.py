import json
import time
import pathlib

class Recorder:
    def __init__(self, log_directory: str = "logs"):
        self.logdir = pathlib.Path(log_directory)
        self.logdir.mkdir(exist_ok=True)
        self.file_handles = {}
        print(f"Recorder initialized. Logging to directory: {self.logdir.resolve()}")

    def log(self, event_name: str, data: dict):
        """
        Appends a dictionary to a daily .jsonl file for a given event type.
        
        Args:
            event_name (str): The name of the event (e.g., 'market_data', 'quotes').
            data (dict): The data dictionary to log.
        """
        # Get the current date for the filename, e.g., 20250729
        today = time.strftime('%Y%m%d')
        file_key = f"{event_name}_{today}"

        if file_key not in self.file_handles:
            filepath = self.logdir / f"{file_key}.jsonl"
            self.file_handles[file_key] = filepath.open("a", buffering=1)

        # Write the data as a single, compressed JSON line
        # The 't_log_ns' is added to have a consistent timestamp of when the event was recorded
        log_entry = {"t_log_ns": time.time_ns(), **data}
        self.file_handles[file_key].write(json.dumps(log_entry, separators=(",",":")) + "\n")

    def close(self):
        """Closes all open file handles."""
        for handle in self.file_handles.values():
            handle.close()
        self.file_handles = {}