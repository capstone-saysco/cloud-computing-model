from flask import Flask, request, Response
from flask_mysqldb import MySQL
from predict import make_prediction
from dotenv import load_dotenv
import json
import os

load_dotenv()
app = Flask(__name__)

app.config['MYSQL_USER'] = os.getenv('DB_USER')
app.config['MYSQL_DB'] = os.getenv('DB_NAME')
app.config['MYSQL_PASSWORD'] = os.getenv('DB_PASSWORDR')
app.config['MYSQL_HOST'] = os.getenv('DB_HOST')

mysql = MySQL(app)

@app.route("/saysco-api/predict-score", methods=["GET"])
def wrong_method():
    output = {
        'message': "Unavailable method, please use POST"
    }
    return Response(json.dumps(output), status=400, mimetype='application/json')

@app.route("/saysco-api/predict-score", methods=["POST"])
def predict():
    output = ''
    status = ''
    try:
        answer_id = request.form['answer_id']
        answer = request.form['answer']
        
        raw_score = make_prediction([answer])
        score = int(round(raw_score[0][0]*100))

        cursor = mysql.connection.cursor()
        cursor.execute("UPDATE student_answer SET score = %s WHERE student_answer.id = %s", (score, answer_id))
        mysql.connection.commit()
        cursor.close()
        
        status = 200
        data = {
            'id': answer_id,
            'score_result': score
            }
        output = {
            'message': "Data processed, get the detailed data via show API.",
            'data': data
            }

    except Exception as error:
        status = 500
        output = {
            'message': str(error)
        }
        
    return Response(json.dumps(output), status=status, mimetype='application/json')