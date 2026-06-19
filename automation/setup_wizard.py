"""
APEX AI Trading Bot Setup Wizards.
Provides terminal-based CLISetupWizard and Tkinter-based GUISetupWizard.
"""
import os
import sys
import requests
import yaml
from pathlib import Path

def validate_alpaca_credentials(api_key: str, secret_key: str) -> bool:
    """Validate Alpaca API credentials against the live or mock server."""
    base_url = os.environ.get("ALPACA_API_BASE_URL") or "https://paper-api.alpaca.markets"
    url = f"{base_url.rstrip('/')}/v2/account"
    headers = {
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": secret_key,
        "Content-Type": "application/json"
    }
    try:
        r = requests.get(url, headers=headers, timeout=5)
        return r.status_code == 200
    except Exception:
        return False

def validate_ib_credentials(account_id: str) -> bool:
    """Validate Interactive Brokers account ID against the live or mock server."""
    if os.environ.get("OPENAI_API_BASE"):
        ib_base_url = "http://localhost:8001"
    else:
        ib_base_url = "https://localhost:5000/v1/api"
        
    url = f"{ib_base_url}/portfolio/{account_id}/meta"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {account_id}"
    }
    try:
        r = requests.get(url, headers=headers, timeout=5)
        return r.status_code == 200
    except Exception:
        return False

def save_settings(data: dict):
    """Save configuration parameters to .env, config/config.yaml, and SQLite database settings table."""
    # 1. Update .env file
    env_path = Path("config").parent / ".env"
    env_lines = []
    if env_path.exists():
        with open(env_path, "r") as f:
            env_lines = f.readlines()
    else:
        example_path = Path("config").parent / ".env.example"
        if example_path.exists():
            with open(example_path, "r") as f:
                env_lines = f.readlines()

    env_dict = {}
    for line in env_lines:
        line_str = line.strip()
        if line_str and not line_str.startswith("#") and "=" in line_str:
            parts = line_str.split("=", 1)
            env_dict[parts[0].strip()] = parts[1].strip()

    key_mapping = {
        "alpaca_key": "ALPACA_API_KEY",
        "alpaca_api_key": "ALPACA_API_KEY",
        "alpaca_secret": "ALPACA_SECRET_KEY",
        "alpaca_secret_key": "ALPACA_SECRET_KEY",
        "gemini_key": "GEMINI_API_KEY",
        "gemini_api_key": "GEMINI_API_KEY",
        "openai_key": "OPENAI_API_KEY",
        "openai_api_key": "OPENAI_API_KEY",
        "anthropic_key": "ANTHROPIC_API_KEY",
        "anthropic_api_key": "ANTHROPIC_API_KEY",
        "newsapi_key": "NEWSAPI_KEY",
        "quiver_key": "QUIVER_QUANT_API_KEY",
        "quiver_quant_api_key": "QUIVER_QUANT_API_KEY",
    }

    for k, v in data.items():
        env_key = key_mapping.get(k.lower())
        if env_key:
            env_dict[env_key] = str(v)
        elif "_" in k and ("key" in k.lower() or "token" in k.lower() or k.isupper()):
            env_dict[k] = str(v)

    with open(env_path, "w") as f:
        for k, v in env_dict.items():
            f.write(f"{k}={v}\n")

    for k, v in env_dict.items():
        os.environ[k] = v

    # 2. Update config/config.yaml
    config_path = Path("config/config.yaml")
    config = {}
    if config_path.exists():
        with open(config_path, "r") as f:
            config = yaml.safe_load(f) or {}

    if "risk_profile" in data:
        config["risk_profile"] = data["risk_profile"]
    if "stop_loss_pct" in data:
        try:
            config["stop_loss_pct"] = float(data["stop_loss_pct"])
        except ValueError:
            pass
    if "take_profit_pct" in data:
        try:
            config["take_profit_pct"] = float(data["take_profit_pct"])
        except ValueError:
            pass
    if "max_positions" in data:
        try:
            config["max_concurrent_positions"] = int(data["max_positions"])
        except ValueError:
            pass
    if "broker" in data:
        if "broker" not in config:
            config["broker"] = {}
        config["broker"]["provider"] = data["broker"]
    if "ib_account" in data:
        if "broker" not in config:
            config["broker"] = {}
        config["broker"]["account_id"] = data["ib_account"]

    # Write back to yaml
    with open(config_path, "w") as f:
        yaml.safe_dump(config, f, default_flow_style=False)

    # 3. Update SQLite database settings table
    db_path = config.get("database", {}).get("path", "trading.db")
    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        for k, v in data.items():
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, str(v)))
        conn.commit()
        conn.close()
    except Exception:
        pass


class CLISetupWizard:
    """Terminal-based setup wizard."""
    def run(self, data: dict = None) -> dict:
        if data is not None:
            # Validate credentials if provided
            alpaca_key = data.get("alpaca_key") or data.get("alpaca_api_key")
            alpaca_secret = data.get("alpaca_secret") or data.get("alpaca_secret_key") or os.environ.get("ALPACA_SECRET_KEY", "mock_secret")
            if alpaca_key:
                if not validate_alpaca_credentials(alpaca_key, alpaca_secret):
                    return {"status": "error", "message": "Alpaca credential validation failed"}
            
            ib_account = data.get("ib_account")
            if ib_account:
                if not validate_ib_credentials(ib_account):
                    return {"status": "error", "message": "Interactive Brokers credential validation failed"}

            save_settings(data)
            return {"status": "success"}

        # Interactive CLI menu
        print("\n" + "=" * 50)
        print("🤖 APEX AI Trading Bot — CLI Setup Wizard")
        print("=" * 50)
        
        user_data = {}
        try:
            print("\nSelect Broker Provider:")
            print("1. Alpaca Markets")
            print("2. Interactive Brokers")
            choice = input("Enter choice (1/2): ").strip()
            
            if choice == "1":
                user_data["broker"] = "alpaca"
                key = input("Enter Alpaca API Key: ").strip()
                secret = input("Enter Alpaca Secret Key: ").strip()
                user_data["alpaca_key"] = key
                user_data["alpaca_secret"] = secret
                
                print("Validating credentials...")
                if validate_alpaca_credentials(key, secret):
                    print("✅ Credentials verified successfully!")
                else:
                    print("❌ Credential validation failed! Check keys or base URL.")
                    confirm = input("Save anyway? (y/n): ").strip().lower()
                    if confirm != 'y':
                        return {"status": "error", "message": "Validation failed"}
            elif choice == "2":
                user_data["broker"] = "ib"
                account = input("Enter IB Account ID (e.g. U12345): ").strip()
                user_data["ib_account"] = account
                
                print("Validating credentials...")
                if validate_ib_credentials(account):
                    print("✅ Credentials verified successfully!")
                else:
                    print("❌ Credential validation failed! Check account ID or base URL.")
                    confirm = input("Save anyway? (y/n): ").strip().lower()
                    if confirm != 'y':
                        return {"status": "error", "message": "Validation failed"}
            else:
                print("Invalid choice. Exiting setup.")
                return {"status": "error", "message": "Invalid choice"}

            print("\nSelect Risk Profile:")
            print("1. Conservative")
            print("2. Moderate")
            print("3. Aggressive")
            risk_choice = input("Enter choice (1/2/3): ").strip()
            risk_map = {"1": "conservative", "2": "moderate", "3": "aggressive"}
            user_data["risk_profile"] = risk_map.get(risk_choice, "moderate")
            
        except (KeyboardInterrupt, EOFError):
            print("\nSetup cancelled.")
            return {"status": "error", "message": "Cancelled by user"}

        save_settings(user_data)
        print("\n🎉 Settings saved successfully!")
        return {"status": "success"}


class GUISetupWizard:
    """Tkinter-based GUI setup wizard."""
    def __init__(self):
        self.root = None
        self.can_show = False
        # Headless safety check
        if os.environ.get("DISPLAY") or os.name == "nt":
            try:
                import tkinter as tk
                from tkinter import messagebox
                self.tk = tk
                self.messagebox = messagebox
                self.can_show = True
            except Exception:
                pass

    def run(self, data: dict = None) -> dict:
        if data is not None:
            # Validate credentials if provided
            alpaca_key = data.get("alpaca_key") or data.get("alpaca_api_key")
            alpaca_secret = data.get("alpaca_secret") or data.get("alpaca_secret_key") or os.environ.get("ALPACA_SECRET_KEY", "mock_secret")
            if alpaca_key:
                if not validate_alpaca_credentials(alpaca_key, alpaca_secret):
                    return {"status": "error", "message": "Alpaca credential validation failed"}
            
            ib_account = data.get("ib_account")
            if ib_account:
                if not validate_ib_credentials(ib_account):
                    return {"status": "error", "message": "Interactive Brokers credential validation failed"}

            save_settings(data)
            return {"status": "success"}

        if not self.can_show:
            return {"status": "error", "message": "Headless environment / Tkinter not available"}

        try:
            self._run_gui()
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _run_gui(self):
        tk = self.tk
        messagebox = self.messagebox
        
        self.root = tk.Tk()
        root = self.root
        root.title("APEX Bot Setup Wizard")
        root.geometry("450x380")
        
        tk.Label(root, text="APEX AI Trading Bot Setup Wizard", font=("Helvetica", 14, "bold")).pack(pady=10)
        
        # Broker selection frame
        broker_frame = tk.LabelFrame(root, text="Broker Configuration")
        broker_frame.pack(pady=10, padx=20, fill="x")
        
        broker_var = tk.StringVar(value="alpaca")
        
        def on_broker_change():
            if broker_var.get() == "alpaca":
                alpaca_key_entry.config(state="normal")
                alpaca_secret_entry.config(state="normal")
                ib_account_entry.config(state="disabled")
            else:
                alpaca_key_entry.config(state="disabled")
                alpaca_secret_entry.config(state="disabled")
                ib_account_entry.config(state="normal")
                
        tk.Radiobutton(broker_frame, text="Alpaca Markets", variable=broker_var, value="alpaca", command=on_broker_change).grid(row=0, column=0, padx=5, pady=5)
        tk.Radiobutton(broker_frame, text="Interactive Brokers", variable=broker_var, value="ib", command=on_broker_change).grid(row=0, column=1, padx=5, pady=5)
        
        tk.Label(broker_frame, text="Alpaca API Key:").grid(row=1, column=0, sticky="w", padx=5)
        alpaca_key_entry = tk.Entry(broker_frame, width=30)
        alpaca_key_entry.grid(row=1, column=1, padx=5, pady=5)
        
        tk.Label(broker_frame, text="Alpaca Secret Key:").grid(row=2, column=0, sticky="w", padx=5)
        alpaca_secret_entry = tk.Entry(broker_frame, show="*", width=30)
        alpaca_secret_entry.grid(row=2, column=1, padx=5, pady=5)
        
        tk.Label(broker_frame, text="IB Account ID:").grid(row=3, column=0, sticky="w", padx=5)
        ib_account_entry = tk.Entry(broker_frame, width=30, state="disabled")
        ib_account_entry.grid(row=3, column=1, padx=5, pady=5)
        
        # Risk Profile
        risk_frame = tk.LabelFrame(root, text="Risk Settings")
        risk_frame.pack(pady=10, padx=20, fill="x")
        
        tk.Label(risk_frame, text="Risk Profile:").grid(row=0, column=0, padx=5, pady=5)
        risk_var = tk.StringVar(value="moderate")
        risk_combo = tk.OptionMenu(risk_frame, risk_var, "conservative", "moderate", "aggressive")
        risk_combo.grid(row=0, column=1, padx=5, pady=5)
        
        def save():
            data = {
                "broker": broker_var.get(),
                "risk_profile": risk_var.get()
            }
            if broker_var.get() == "alpaca":
                key = alpaca_key_entry.get().strip()
                secret = alpaca_secret_entry.get().strip()
                if not key:
                    messagebox.showerror("Error", "Alpaca API Key is required")
                    return
                data["alpaca_key"] = key
                data["alpaca_secret"] = secret
                
                if not validate_alpaca_credentials(key, secret):
                    confirm = messagebox.askyesno("Validation Failed", "Alpaca validation failed. Save anyway?")
                    if not confirm:
                        return
            else:
                account = ib_account_entry.get().strip()
                if not account:
                    messagebox.showerror("Error", "IB Account ID is required")
                    return
                data["ib_account"] = account
                
                if not validate_ib_credentials(account):
                    confirm = messagebox.askyesno("Validation Failed", "IB validation failed. Save anyway?")
                    if not confirm:
                        return
            
            save_settings(data)
            messagebox.showinfo("Success", "Configuration saved successfully!")
            root.destroy()
            
        tk.Button(root, text="Save Configuration", command=save, bg="green", fg="white", font=("Helvetica", 10, "bold")).pack(pady=15)
        root.mainloop()
