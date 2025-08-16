# backend/main.py

from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from azure.storage.blob import BlobServiceClient
import pandas as pd
import os

app = Flask(__name__)
app.secret_key = 'YOUR_SECRET_KEY'  # change this!

# Azure configuration
AZURE_CONNECTION_STRING = 'YOUR_AZURE_CONNECTION_STRING'
BLOB_CONTAINER_NAME = 'registration-data'
CSV_BLOB_NAME = 'registered.csv'

def get_registered_csv():
    blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
    blob_client = blob_service_client.get_container_client(BLOB_CONTAINER_NAME).get_blob_client(CSV_BLOB_NAME)
    csv_bytes = blob_client.download_blob().readall()
    # Use pandas to read the in-memory csv bytes
    from io import BytesIO
    df = pd.read_csv(BytesIO(csv_bytes))
    return df

# -- ROUTES --

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == 'fs2025' and password == 'icbfs1095':
            session['logged_in'] = True
            return redirect(url_for('registered'))
        else:
            error = 'Invalid Credentials'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/registered')
def registered():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    # The main page only renders the HTML
    return render_template('registered.html')

@app.route('/api/registered')
def api_registered():
    if not session.get('logged_in'):
        return jsonify({"error": "unauthorized"}), 403
    df = get_registered_csv()
    # Optionally, filter data with query params
    filters = {}
    for key in ['customer_code', 'customer_name', 'attendee_name', 'registered_id']:
        val = request.args.get(key)
        if val:
            filters[key] = val.lower().strip()
    if filters:
        for col, val in filters.items():
            df = df[df[col].astype(str).str.lower().str.contains(val)]
    return df.to_json(orient='records')

if __name__ == '__main__':
    app.run(debug=True)
