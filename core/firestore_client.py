import os
from google.cloud import firestore
from google.oauth2 import service_account

KEY_PATH = "serviceAccountKey.json"

if os.path.exists(KEY_PATH):
    credentials = service_account.Credentials.from_service_account_file(KEY_PATH)
    db = firestore.Client(credentials=credentials)
else:
    db = firestore.Client()