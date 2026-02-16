import os
import pyupbit
from dotenv import load_dotenv

load_dotenv()

access_key = os.getenv("UPBIT_ACCESS_KEY")
secret_key = os.getenv("UPBIT_SECRET_KEY")

print(f"Access Key present: {bool(access_key)}")
print(f"Secret Key present: {bool(secret_key)}")

if access_key:
    print(f"Access Key (first 5 chars): {access_key[:5]}...")
if secret_key:
    print(f"Secret Key (first 5 chars): {secret_key[:5]}...")

if access_key and secret_key:
    upbit = pyupbit.Upbit(access_key, secret_key)
    try:
        print("Attempting to fetch KRW balance...")
        krw_balance = upbit.get_balance("KRW")
        print(f"KRW Balance result: {krw_balance}")
        
        print("Attempting to fetch all balances (raw)...")
        balances = upbit.get_balances()
        print(f"All Balances result type: {type(balances)}")
        print(f"All Balances result: {balances}")
    except Exception as e:
        print(f"Error fetching balance: {e}")
else:
    print("Keys are missing.")
