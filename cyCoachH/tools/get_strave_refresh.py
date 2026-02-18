import requests
import sys

# -------------------------------------------------------
# INSTRUCTIONS:
# 1. Run this script.
# 2. It will ask for your Client ID and Secret.
# 3. It will generate a URL. Open that URL in your browser.
# 4. Click "Authorize".
# 5. The browser will redirect to a broken page (localhost). 
#    LOOK AT THE URL BAR. Copy the code=... part.
# 6. Paste the code back here.
# -------------------------------------------------------

def get_credentials():
    print("--- Strava OAuth Setup ---")
    client_id = input("Enter your Client ID: ").strip()
    client_secret = input("Enter your Client Secret: ").strip()
    return client_id, client_secret

def main():
    client_id, client_secret = get_credentials()

    # 1. Generate Auth URL
    auth_url = (
        f"https://www.strava.com/oauth/authorize"
        f"?client_id={client_id}"
        f"&response_type=code"
        f"&redirect_uri=http://localhost/exchange_token"
        f"&approval_prompt=force"
        f"&scope=activity:read_all"
    )

    print(f"\n[ACTION REQUIRED] Open this URL in your browser:\n{auth_url}\n")
    print("After authorizing, you will be redirected to 'http://localhost/exchange_token?code=...'.")
    print("Copy the text AFTER 'code=' and paste it below.")
    
    auth_code = input("\nPaste the 'code' here: ").strip()

    # 2. Exchange Code for Refresh Token
    print("\nExchanging code for permanent token...")
    token_url = "https://www.strava.com/oauth/token"
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": auth_code,
        "grant_type": "authorization_code"
    }

    try:
        response = requests.post(token_url, data=payload)
        data = response.json()

        if response.status_code == 200:
            refresh_token = data.get("refresh_token")
            print("\nSUCCESS! Add these lines to your ~/cyCoach/.env file:\n")
            print(f"STRAVA_CLIENT_ID={client_id}")
            print(f"STRAVA_CLIENT_SECRET={client_secret}")
            print(f"STRAVA_REFRESH_TOKEN={refresh_token}")
        else:
            print(f"\nERROR: {data}")

    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    main()