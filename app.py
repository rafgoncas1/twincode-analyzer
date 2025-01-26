from flask import Flask, render_template, session, redirect, request, jsonify, send_from_directory, send_file
import os
from flask_socketio import SocketIO
import requests
import json
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint
import pandas as pd
import threading
from io import BytesIO
from processor import process_form1, process_form2, filter_ids, join_files, filter_gender_perception, create_cps_df, create_wide_df
from analyzer import analyzeVariableBetween, analyzeVariableWithin, analyzeCpsBetween, analyzeCpsWithin
import traceback
import math
import zipfile
import io

app = Flask(__name__)
socket = SocketIO(app)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///analysis.db'
db = SQLAlchemy(app)


class Analysis(db.Model):
    name = db.Column(db.String(80), primary_key=True)
    favourite = db.Column(db.Boolean, default=False, nullable=False)
    # Satatus: 'completed', 'running', 'pending'
    status = db.Column(db.String(80), default="pending", nullable=False)
    custom = db.Column(db.Boolean, default=False, nullable=False)
    __table_args__ = (CheckConstraint(
        "status IN ('completed', 'running', 'pending')", name='status_check'), )
    percentage = db.Column(db.Integer, default=0, nullable=False)
    __table_args__ = (CheckConstraint(
        '0<=percentage AND percentage<=100', name='percentage_check'), )
    
    def to_json(self):
        return {'name': self.name, 'favourite': self.favourite, 'status': self.status, 'percentage': self.percentage, 'custom': self.custom}


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

@app.route('/custom', methods=['GET'])
def custom():
    if is_logged():
        return render_template('custom.html')
    else:
        return redirect('/login')


@app.route('/analysis/<analysis_name>', methods=['GET'])
def analysis(analysis_name):
    if is_logged():
        # Check if analysis exists and is completed
        analysis = Analysis.query.get(analysis_name)
        if not analysis or analysis.status != 'completed':
            return page_not_found()

        #  Load json data from analysis results
        with open('analysis/' + analysis_name + '/analysis.json') as json_file:
            data = json.load(json_file)

        data['name'] = analysis_name

        return render_template('analysis.html', data=data)
    else:
        return redirect('/login')

@app.route('/analysis/<analysis_name>/download', methods=['GET'])
def download(analysis_name):
    if is_logged():
        folder_path = 'analysis/' + analysis_name
        if os.path.exists(folder_path):
            memory_file = io.BytesIO()
            with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(folder_path):
                    for filename in files:
                        file_path = os.path.join(root, filename)
                        relative_path = os.path.join(analysis_name,os.path.relpath(file_path, folder_path))
                        zipf.write(file_path, arcname=relative_path)
            memory_file.seek(0)

            return send_file(memory_file, download_name=analysis_name + '.zip', as_attachment=True)
        else:
            return page_not_found()
    else:
        return redirect('/login')


@app.route('/analysis/<analysis_name>/plots/<path:filename>')
def serve_plots(analysis_name, filename):
    return send_from_directory(f'analysis/{analysis_name}/plots', filename)


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


@app.route('/api/analyses', methods=['GET'])
def api_sessions():
    if is_logged():
        if update_sessions():
            analyses = Analysis.query.all()
            analyses_json = [analysis.to_json() for analysis in analyses]
            return jsonify(analyses_json), 200
        else:
            return jsonify({'message': 'Error getting sessions from API!'}), 500
    else:
        return jsonify({'message': 'Not logged in!'}), 403

@app.route('/api/sessions', methods=['GET'])
def api_sessions_twincode():
    if is_logged():
        if update_sessions():
            sessions = Analysis.query.filter_by(custom=False).all()
            sessions_json = [session.to_json() for session in sessions]
            return jsonify(sessions_json), 200
        else:
            return jsonify({'message': 'Error getting sessions from API!'}), 500
    else:
        return jsonify({'message': 'Not logged in!'}), 403

@app.route('/api/favourites/<analysis_name>', methods=['PUT'])
def api_favourites(analysis_name):
    if is_logged():
        print('Updating favourite for session ' + analysis_name + '...')
        analysis = Analysis.query.get(analysis_name)
        if analysis:
            analysis.favourite = request.get_json()['favourite']
            db.session.commit()
            socket.emit('favouriteUpdated', {
                        'name': analysis_name, 'favourite': analysis.favourite})
            return jsonify({'message': 'Favourite updated successfully!'}), 200
        else:
            return jsonify({'message': 'Session not found!'}), 404
    else:
        return jsonify({'message': 'Not logged in!'}), 403


@app.route('/api/analysis/<session_name>', methods=['POST'])
def api_session_analysis(session_name):
    if is_logged():
        session = Analysis.query.get(session_name)
        if not session:
            return jsonify({'message': 'Session not found!'}), 404
        form1 = request.files.get('form1')
        if not form1:
            return jsonify({'message': 'Form1 not found!'}), 400
        form2 = request.files.get('form2')
        if not form2:
            return jsonify({'message': 'Form2 not found!'}), 400
        reviewers = json.loads(request.form.get('reviewers'))
        main_reviewer = request.form.get('mainReviewer')
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

        tagachat_df = get_tagachat_data(session_name, reviewers, main_reviewer)
        if 'error' in tagachat_df:
            tagachat_df = None

        session.status = 'running'
        session.percentage = 1
        db.session.commit()

        socket.emit('analysisStarted', {'name': session_name})
        threading.Thread(target=start_analysis, args=(
            session_name, form1_df, form2_df, twincode_df, tagachat_df,)).start()
        return jsonify({'message': 'Analysis started successfully!'}), 202
    else:
        return jsonify({'message': 'Not logged in!'}), 403
    
@app.route('/api/analysis/custom', methods=['POST'])
def api_custom_analysis():
    if is_logged():
        form1 = request.files.get('form1')
        if not form1:
            return jsonify({'message': 'Form1 not found!'}), 400
        form2 = request.files.get('form2')
        if not form2:
            return jsonify({'message': 'Form2 not found!'}), 400
        reviewers = json.loads(request.form.get('reviewers'))
        analysis_name = request.form.get('name')
        if not analysis_name:
            return jsonify({'message': 'No analysis name supplied'}), 400
        main_reviewer = json.loads(request.form.get('mainReviewer'))
        
        selected_sessions = list(reviewers.keys())
        
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
        
        twincode_df = None
        tagachat_df = None

        for session_name in selected_sessions:
            twincode_data = get_tc_data(session_name)
            if 'error' in twincode_data:
                return jsonify(twincode_data['error']), 500
            if twincode_df is None:
                twincode_df = twincode_data
            else:
                twincode_df = pd.concat([twincode_df, twincode_data])
            tagachat_data = get_tagachat_data(session_name, reviewers[session_name], main_reviewer[session_name])
            if 'error' in tagachat_data:
                tagachat_data = None
            if tagachat_df is None:
                tagachat_df = tagachat_data
            else:
                tagachat_df = pd.concat([tagachat_df, tagachat_data])
        
        session = Analysis.query.get(analysis_name)
        if not session:
            session = Analysis(name=analysis_name, custom=True)
            db.session.add(session)
            db.session.commit()
        else:
            return jsonify({'message': 'Analysis name already exists!'}), 400
        
        session.status = 'running'
        session.percentage = 1
        db.session.commit()

        socket.emit('analysisStarted', {'name': analysis_name})
        threading.Thread(target=start_analysis, args=(
            analysis_name, form1_df, form2_df, twincode_df, tagachat_df,)).start()
        

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

def update_sessions():
    with app.app_context():
        try:
            res = requests.get(os.environ.get('TC_API_URL') + '/sessions',
                                headers={'Authorization': os.environ.get('TC_ADMIN_SECRET')})
            if res.status_code == 200:
                sessions = res.json()
                for session in sessions:
                    db_session = Analysis.query.get(session['name'])
                    if not db_session:
                        db.session.add(Analysis(name=session['name']))
                db.session.commit()
                return True
            else:
                return False
        except:
            return False


def get_tc_data(session_name):
    twincode_req = requests.get(os.environ.get('TC_API_URL') + '/analytics/' +
                                session_name, headers={'Authorization': os.environ.get('TC_ADMIN_SECRET')})
    if not twincode_req.ok:
        return {'error': 'Error fetching twincode data for ' + session_name}

    twincode_data = None
    try:
        twincode_data = twincode_req.json()
    except:
        return {'error': 'Error parsing twincode data for ' + session_name}

    df = pd.DataFrame(twincode_data)
    return df


def get_tagachat_data(session_name, reviewers=None, main_reviewer=None):

    main_reviewer = main_reviewer if main_reviewer and main_reviewer.strip() else None

    tagachat_url = os.environ.get(
        'TAGACHAT_API_URL') + '/analytics/' + session_name

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

    # Renombrar columna participant por id
    df = df.rename(columns={'participant': 'id'})

    # convertir columna percent a numero
    try:
        df['percent'] = df['percent'].astype(float)
    except:
        return {'error': 'Error converting tagachat data to numbers'}
    
    # Eliminar filas donde "percent" no sea 100
    df = df[df['percent'] == 100]

    if main_reviewer:
        # Filtrar solo las filas donde el reviewer sea el main_reviewer en cada id y time, en otro caso tomar la primera fila
        df = df.groupby(['id', 'time']).apply(lambda g: g[g['reviewer'] == main_reviewer].head(1) if (g['reviewer'] == main_reviewer).any() else g.head(1)).reset_index(drop=True)
    
    # Eliminar columna session, room, reviewer, percent y renombrar columna participant por id
    df = df.drop(columns=['session', 'room', 'reviewer', 'percent'])

    # Convertir las columnas a partir de la tercera a numeros
    try:
        df.iloc[:, 2:] = df.iloc[:, 2:].astype(float)
    except:
        return {'error': 'Error converting tagachat data to numbers'}

    if not main_reviewer:
        # Hacer la media de las columnas a partir de la segunda, agrupando por id y time
        df = df.groupby(['id', 'time']).mean().reset_index()

    return df


def start_analysis(analysis_name, form1_df, form2_df, twincode_df, tagachat_df):
    with app.app_context():
        socket.emit('analysisStarted', {'name': analysis_name})
        
        # Process form1    
        try:
            form1_df = process_form1(form1_df)
            update_percentage(analysis_name, 2)
        except:
            analysis_error(analysis_name, 'Error processing form1 data!')
            traceback.print_exc()
            return
        
        # Process form2
        try:
            form2_df = process_form2(form2_df)
        except:
            analysis_error(analysis_name, 'Error processing form2 data!')
            traceback.print_exc()
            return
        
        print('Form1 and Form2 processed successfully!')
        
        # Filter ids
        try:
            form1_df, form2_df, twincode_df, tagachat_df = filter_ids(form1_df, form2_df, twincode_df, tagachat_df)
        except:
            analysis_error(analysis_name, 'Error filtering data!')
            traceback.print_exc()
            return
                
        print('Filtering completed!')
        
        # Join files
        try:
            long_df = join_files(form1_df, form2_df, twincode_df, tagachat_df)
        except:
            analysis_error(analysis_name, 'Error joining files!')
            traceback.print_exc()
            return
        
        print('Files joined successfully!')
        
        # Filter by gender correct perception
        try:
            long_df = filter_gender_perception(long_df)
        except:
            analysis_error(analysis_name, 'Error filtering long_df by gender perception!')
            traceback.print_exc()
            return
        
        print('Long df filtered by gender perception!')
        
        # Create CPS dataframe
        try:
            cps_df = create_cps_df(long_df, form2_df)
        except:
            analysis_error(analysis_name, 'Error creating CPS dataframe!')
            traceback.print_exc()
            return
        
        print('CPS df created successfully!')
        
        # Create wide dataframe
        try:
            wide_df = create_wide_df(long_df)
        except:
            analysis_error(analysis_name, 'Error creating wide dataframe!')
            traceback.print_exc()
            return
        
        print('Wide df created successfully!')
        
        update_percentage(analysis_name, 10)
        
        # Create analysis folder for session
        if not os.path.exists("analysis"):
            os.makedirs("analysis")
        if not os.path.exists("analysis/" + analysis_name):
            os.makedirs("analysis/" + analysis_name)
        if not os.path.exists("analysis/" + analysis_name + "/plots"):
            os.makedirs("analysis/" + analysis_name + "/plots")
        if not os.path.exists("analysis/" + analysis_name + "/plots/between"):
            os.makedirs("analysis/" + analysis_name + "/plots/between")
        if not os.path.exists("analysis/" + analysis_name + "/plots/within"):
            os.makedirs("analysis/" + analysis_name + "/plots/within")
        if not os.path.exists("analysis/" + analysis_name + "/plots/within/ppgender"):
            os.makedirs("analysis/" + analysis_name + "/plots/within/ppgender")
        if not os.path.exists("analysis/" + analysis_name + "/plots/within/ipgender"):
            os.makedirs("analysis/" + analysis_name + "/plots/within/ipgender")
        if not os.path.exists("analysis/" + analysis_name + "/plots/cps_between"):
            os.makedirs("analysis/" + analysis_name + "/plots/cps_between")
        if not os.path.exists("analysis/" + analysis_name + "/plots/cps_within"):
            os.makedirs("analysis/" + analysis_name + "/plots/cps_within")
        
        print('Analysis folders created successfully!')

        long_df.to_csv("analysis/" + analysis_name + "/long_df.csv", index=False)
        wide_df.to_csv("analysis/" + analysis_name + "/wide_df.csv", index=False)
        cps_df.to_csv("analysis/" + analysis_name + "/cps_df.csv", index=False)
        
        # List of names of the columns which are numeric
        excluded = ["okv","okv_rf","kov","kov_rf"] # Exclude some irrelevant variables
        variables = set(long_df.select_dtypes(include=['int64', 'float64']).columns)
        variables = variables.difference(excluded)

        cps_variables = set(cps_df.select_dtypes(include=['int64', 'float64']).columns)
        
        results = {"between": {}, "within": {"ppgender": {}, "ipgender": {}}, "cps_between": {}, "cps_within": {}}
        
        iterations = len(variables) + len(cps_variables)
        percentage_accum = 10
        percentage_update = math.floor(90/iterations)
        
        for variable in variables:
            print("\n##### Analyzing " + variable + " for "+analysis_name+" #####")
            try:
                results["between"][variable] = analyzeVariableBetween(variable, wide_df, analysis_name)
                results["within"]["ppgender"][variable] = analyzeVariableWithin(variable, "ppgender", long_df, analysis_name)
                results["within"]["ipgender"][variable] = analyzeVariableWithin(variable, "ipgender", long_df, analysis_name)
            except:
                analysis_error(analysis_name, 'Error analyzing variable ' + variable)
                traceback.print_exc()
                return
            
            percentage_accum += percentage_update
            update_percentage(analysis_name, percentage_accum)
    
        for variable in cps_variables:
            print("\n##### Analyzing " + variable + " for "+analysis_name+" #####")
            try:
                results["cps_between"][variable] = analyzeCpsBetween(variable, cps_df, analysis_name)
                results["cps_within"][variable] = analyzeCpsWithin(variable, cps_df, analysis_name)
            except:
                analysis_error(analysis_name, 'Error analyzing CPS variable ' + variable)
                traceback.print_exc()
                return
            
            percentage_accum += percentage_update
            update_percentage(analysis_name, percentage_accum)
        
        try:
            # Save analysis as json
            with open("analysis/" + analysis_name + "/analysis.json", "w") as outfile:
                json.dump(results, outfile, indent=4, sort_keys=True)
        except:
            analysis_error(analysis_name, 'Error saving analysis results!')
            traceback.print_exc()
            return
    
        
        analysis_completed(analysis_name)


def analysis_error(analysis_name, message):
    with app.app_context():
        analysis = Analysis.query.get(analysis_name)
        analysis.status = 'pending'
        analysis.percentage = 0
        db.session.commit()
        socket.emit('analysisError', {
                    'name': analysis.name, 'message': message})


def update_percentage(analysis_name, percentage):
    with app.app_context():
        analysis = Analysis.query.get(analysis_name)
        analysis.percentage = percentage
        db.session.commit()
        socket.emit('percentageUpdate', {
                    'name': analysis.name, 'percentage': analysis.percentage})

def analysis_completed(analysis_name):
    with app.app_context():
        analysis = Analysis.query.get(analysis_name)
        analysis.status = 'completed'
        analysis.percentage = 100
        db.session.commit()
        socket.emit('analysisCompleted', {'name': analysis.name})

@app.template_filter('safe_format')
def safe_format(value):
    try:
        return f"{float(value):.4f}"
    except (ValueError, TypeError):
        return value

if __name__ == '__main__':
    app.run()
