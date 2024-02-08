from flask import Flask, render_template, session, redirect, request, jsonify
import os
from flask_socketio import SocketIO
import requests
import json
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint
import pandas as pd
import threading

app = Flask(__name__)
socket = SocketIO(app)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sessions.db'
db = SQLAlchemy(app)

class Session(db.Model):
    name = db.Column(db.String(80), primary_key=True)
    favourite = db.Column(db.Boolean, default=False, nullable=False)
    # Satatus: 'completed', 'running', 'pending'
    status = db.Column(db.String(80), default="pending", nullable=False)
    __table_args__ = (CheckConstraint("status IN ('completed', 'running', 'pending')", name='status_check'), )
    percentage = db.Column(db.Integer, default=0, nullable=False)
    __table_args__ = (CheckConstraint('0<=percentage AND percentage<=100', name='percentage_check'), )

with app.app_context():
    db.create_all()

def is_logged():
    if session.get('logged_in'):
        return True
    else:
        return False

@app.route('/')
def index():
    if is_logged():
            return render_template('index.html')
    else:
        return redirect('/login')
    
@app.route('/login', methods=['GET'])
def login():
    if is_logged():
        return redirect('/')
    else:
        return render_template('login.html', navbar=False)

### API Routes ###

@app.route('/api/login', methods=['POST'])
def api_login():
    password = request.get_json()['password']
    if password == os.environ.get('ADMIN_PASSWORD'):
        session['logged_in'] = True
        return jsonify({'message': 'Logged in successfully!'}), 200
    else:
        return jsonify({'message': 'Incorrect password!'}), 403

@app.route('/api/logout', methods=['POST'])
def api_logout():
    session['logged_in'] = False
    return jsonify({'message': 'Logged out successfully!'}), 200

@app.route('/api/sessions', methods=['GET'])
def api_sessions():
    if is_logged():
        res = requests.get(os.environ.get('TC_API_URL') + '/sessions', headers={'Authorization': os.environ.get('TC_ADMIN_SECRET')})
        if res.status_code == 200:
            sessions = res.json()
            for session in sessions:
                db_session = Session.query.get(session['name'])
                if db_session:
                    session['favourite'] = db_session.favourite
                    session['status'] = db_session.status
                    session['percentage'] = db_session.percentage
                else:
                    session['favourite'] = False
                    session['status'] = False
                    session['percentage'] = 0
                    db.session.add(Session(name=session['name']))
            db.session.commit()
            return jsonify(sessions), 200
        else:
            return jsonify({'message': 'Error getting sessions from API!'}), 500
    else:
        return jsonify({'message': 'Not logged in!'}), 403

@app.route('/api/favourites/<session_name>', methods=['PUT'])
def api_favourites(session_name):
    if is_logged():
        print('Updating favourite for session ' + session_name + '...')
        session = Session.query.get(session_name)
        if session:
            session.favourite = request.get_json()['favourite']
            db.session.commit()
            socket.emit('favouriteUpdated', {'name': session_name, 'favourite': session.favourite})
            return jsonify({'message': 'Favourite updated successfully!'}), 200
        else:
            return jsonify({'message': 'Session not found!'}), 404
    else:
        return jsonify({'message': 'Not logged in!'}), 403
    
@app.route('/api/analysis/<session_name>', methods=['POST'])
def api_analysis(session_name):
    if is_logged():
        session = Session.query.get(session_name)
        if session:
            session.status = 'running'
            session.percentage = 1
            db.session.commit()
            socket.emit('analysisStarted', {'name': session_name})
            threading.Thread(target=start_analysis, args=(session_name,)).start()
            return jsonify({'message': 'Analysis started successfully!'}), 202
        else:
            return jsonify({'message': 'Session not found!'}), 404
    else:
        return jsonify({'message': 'Not logged in!'}), 403

### SocketIO ###

@socket.on('connect')
def connect_handler():
    if not is_logged():
        print('Connection refused!')
        return False
    else:
        print('Client connected!')

### Auxiliar Functions ###

def start_analysis(session_name):
    with app.app_context():
        twincode_req = requests.get(os.environ.get('TC_API_URL') + '/analytics/' + session_name , headers={'Authorization': os.environ.get('TC_ADMIN_SECRET')})
        print(twincode_req.ok)
        if not twincode_req.ok:
            analysis_error(session_name, 'Error fetching twincode data for ' + session_name + ' - ' + str(twincode_req.text))
            return
        
        twincode_data = None
        try:
            twincode_data = twincode_req.json()
        except:
            analysis_error(session_name, 'Error parsing twincode data for ' + session_name)
            return

        twincode_df = pd.DataFrame(twincode_data)
        print(twincode_df)
        
        tagachat_req = requests.get(os.environ.get('TAGACHAT_API_URL') + '/sessions/' + session_name + "/rooms/")
        if not tagachat_req.ok:
            analysis_error(session_name, 'Error fetching tagachat data for ' + session_name)
            return
        
        tagachat_data = tagachat_req.json()
        print(tagachat_data)

def analysis_error(session_name, message):
    with app.app_context():
        session = Session.query.get(session_name)
        session.status = 'pending'
        session.percentage = 0
        db.session.commit()
        socket.emit('analysisError', {'name': session.name, 'message': message})
    

if __name__ == '__main__':
    app.run()