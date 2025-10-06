import yaml
import os
import time
from threading import Lock
from typing import Any, Dict

class YAMLConfigManager:
    """
    Dynamic YAML configuration manager with auto-reload functionality.
    """
    
    def __init__(self, config_file: str = "config.yaml"):
        self.config_file = config_file
        self.config_data: Dict[str, Any] = {}
        self.last_modified = 0
        self.lock = Lock()
        self.load_config()
    
    def load_config(self) -> None:
        """Load configuration from YAML file."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config_data = yaml.safe_load(f) or {}
                self.last_modified = os.path.getmtime(self.config_file)
                print(f"YAML configuration loaded from {self.config_file}")
            else:
                print(f"Warning: Config file {self.config_file} not found. Using empty config.")
                self.config_data = {}
        except yaml.YAMLError as e:
            print(f"Error parsing YAML config: {e}")
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
                print("YAML configuration reloaded due to file change")
                return True
        return False
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """Get configuration value using dot notation."""
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

# Example usage
if __name__ == "__main__":
    yaml_config = YAMLConfigManager()
    
    print("YAML Config Demo:")
    print(f"Trading enabled: {yaml_config.get('trading.trading_enabled')}")
    print(f"Coins to trade: {yaml_config.get('trading.coins_to_trade')}")
    print(f"Dashboard theme: {yaml_config.get('dashboard.theme')}")