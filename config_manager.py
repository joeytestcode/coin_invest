import json
import os
import time
from threading import Lock
from typing import Any, Dict, Optional

class ConfigManager:
    """
    Dynamic configuration manager that automatically reloads config when file changes.
    """
    
    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self.config_data: Dict[str, Any] = {}
        self.last_modified = 0
        self.lock = Lock()
        self.load_config()
    
    def load_config(self) -> None:
        """Load configuration from file."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config_data = json.load(f)
                self.last_modified = os.path.getmtime(self.config_file)
                print(f"Configuration loaded from {self.config_file}")
            else:
                print(f"Warning: Config file {self.config_file} not found. Using empty config.")
                self.config_data = {}
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON config: {e}")
            self.config_data = {}
        except Exception as e:
            print(f"Error loading config: {e}")
            self.config_data = {}
    
    def check_and_reload(self) -> bool:
        """Check if config file has been modified and reload if necessary."""
        if not os.path.exists(self.config_file):
            return False
        
        current_modified = os.path.getmtime(self.config_file)
        if current_modified > self.last_modified:
            with self.lock:
                self.load_config()
                print("Configuration reloaded due to file change")
                return True
        return False
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation (e.g., 'trading.max_investment_amount').
        Automatically checks for file changes before returning value.
        """
        self.check_and_reload()
        
        keys = key_path.split('.')
        value = self.config_data
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """Get entire configuration section."""
        self.check_and_reload()
        return self.config_data.get(section, {})
    
    def set(self, key_path: str, value: Any, save: bool = True) -> None:
        """
        Set configuration value using dot notation.
        If save=True, writes changes back to file.
        """
        with self.lock:
            keys = key_path.split('.')
            config_ref = self.config_data
            
            # Navigate to the parent of the target key
            for key in keys[:-1]:
                if key not in config_ref:
                    config_ref[key] = {}
                config_ref = config_ref[key]
            
            # Set the value
            config_ref[keys[-1]] = value
            
            if save:
                self.save_config()
    
    def save_config(self) -> None:
        """Save current configuration to file."""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config_data, f, indent=2, ensure_ascii=False)
            self.last_modified = os.path.getmtime(self.config_file)
            print(f"Configuration saved to {self.config_file}")
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def refresh(self) -> None:
        """Force reload configuration from file."""
        with self.lock:
            self.load_config()

# Global config manager instance
if __name__ == "__main__":
    config = ConfigManager()