from flask import Flask, render_template, session, redirect, request, jsonify, send_from_directory
import os
from flask_socketio import SocketIO
import requests
import json
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint
import pandas as pd
import threading
from io import BytesIO

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

@app.route('/analysis/<session_name>', methods=['GET'])
def analysis(session_name):
    if is_logged():
        # Check if session exists and is completed
        session = Session.query.get(session_name)
        if not session or session.status != 'completed':
            return page_not_found()

        #  Load json data from analysis results
        with open('analysis/' + session_name + '/analysis.json') as json_file:
            data = json.load(json_file)

        data['session'] = session_name

        return render_template('analysis.html', data=data)
    else:
        return redirect('/login')

@app.route('/analysis/<session_name>/plots/<path:filename>')
def serve_plots(session_name, filename):
    return send_from_directory(f'analysis/{session_name}/plots', filename)
    
@app.errorhandler(404)
def page_not_found(e=None):
    return render_template('404.html', navbar=False), 404

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
                    session['status'] = 'completed' if session['name'] == 'ucb1' else 'pending'
                    session['percentage'] = 100 if session['name'] == 'ucb1' else 0
                    db.session.add(Session(name=session['name'], favourite=session['favourite'], status=session['status'], percentage=session['percentage']))
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
        if not session:
            return jsonify({'message': 'Session not found!'}), 404
        form1 = request.files.get('form1')
        if not form1:
            return jsonify({'message': 'Form1 not found!'}), 400
        form2 = request.files.get('form2')
        if not form2:
            return jsonify({'message': 'Form2 not found!'}), 400
        reviewers = json.loads(request.form.get('reviewers'))
        if not reviewers:
            return jsonify({'message': 'No reviewers supplied'}), 400
        
        form1_df = None
        try:
            form1_data = BytesIO(form1.read())
            form1_df = pd.read_csv(form1_data)
        except:
            return jsonify({'message': 'Error parsing form1 data!'}), 400

        form2_df = None
        try:
            form2_data = BytesIO(form2.read())
            form2_df = pd.read_csv(form2_data)
        except:
            return jsonify({'message': 'Error parsing form2 data!'}), 400

        twincode_df = get_tc_data(session_name)
        if 'error' in twincode_df:
            return jsonify(twincode_df['error']), 500

        tagachat_df = get_tagachat_data(session_name, reviewers)
        if 'error' in tagachat_df:
            return jsonify(tagachat_df['error']), 500

        session.status = 'running'
        session.percentage = 1
        db.session.commit()
        
        socket.emit('analysisStarted', {'name': session_name})
        threading.Thread(target=start_analysis, args=(session_name,form1_df,form2_df,twincode_df,tagachat_df,)).start()
        return jsonify({'message': 'Analysis started successfully!'}), 202
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
         
def get_tc_data(session_name):
    twincode_req = requests.get(os.environ.get('TC_API_URL') + '/analytics/' + session_name , headers={'Authorization': os.environ.get('TC_ADMIN_SECRET')})
    if not twincode_req.ok:
        return {'error': 'Error fetching twincode data for ' + session_name + ' - ' + str(twincode_req.text)}
    
    twincode_data = None
    try:
        twincode_data = twincode_req.json()
    except:
        return {'error': 'Error parsing twincode data for ' + session_name}
    
    df = pd.DataFrame(twincode_data)
    return df

def get_tagachat_data(session_name, reviewers=None):
    tagachat_url = os.environ.get('TAGACHAT_API_URL') + '/analytics/' + session_name

    if reviewers:
        string_reviewers = ','.join(reviewers)
        reviewers_query = '?reviewers=' + string_reviewers
        tagachat_url += reviewers_query
    
    tagachat_req = requests.get(tagachat_url)
    if not tagachat_req.ok:
        return {'error': 'Error fetching tagachat data for ' + session_name}
    
    tagachat_data = None
    try:
        tagachat_data = tagachat_req.json()
    except:
        return {'error': 'Error parsing tagachat data for ' + session_name}
    
    df = pd.DataFrame(tagachat_data)
    # Eliminar columna session, room, reviewer y renombrar columna participant por id
    df = df.drop(columns=['session', 'room', 'reviewer'])
    df = df.rename(columns={'participant': 'id'})
    # Convertir las columnas a partir de la tercera a numeros
    try:
        df.iloc[:, 2:] = df.iloc[:, 2:].astype(float)
    except:
        return {'error': 'Error converting tagachat data to numbers'}
    # Hacer la media de las columnas a partir de la segunda, agrupando por id y time
    df = df.groupby(['id', 'time']).mean().reset_index()
    
    return df
    
def start_analysis(session_name, form1_df, form2_df, tagachat_df, twincode_df):
    with app.app_context():
        socket.emit('analysisStarted', {'name': session_name})
        print(twincode_df)
        print(tagachat_df)
        print(form1_df)
        print(form2_df)

def analysis_error(session_name, message):
    with app.app_context():
        session = Session.query.get(session_name)
        session.status = 'pending'
        session.percentage = 0
        db.session.commit()
        socket.emit('analysisError', {'name': session.name, 'message': message})

def update_percentage(session_name, percentage):
    with app.app_context():
        session = Session.query.get(session_name)
        session.percentage = percentage
        db.session.commit()
        socket.emit('percentageUpdate', {'name': session.name, 'percentage': session.percentage})
    

if __name__ == '__main__':
    app.run()