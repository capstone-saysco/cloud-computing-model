from flask import Flask, request, Response
from flask_mysqldb import MySQL
import pymysql
import json

mysql =MySQL()
app = Flask(__name__)

app.config['MYSQL_DATABASE_USER'] = 'root'
app.config['MYSQL_DATABASE_DB'] = 'saysco_db'
app.config['MYSQL_DATABASE_PASSWORD'] = ''
app.config['MYSQL_DATABASE_HOST'] = 'localhost'

mysql.init_app(app)

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
    
    if request.form == None:
        status = 400
        output = {
            'message': "Invalid data",
            'data': request.form
        }

    else:
        answer_id = request.form['answer_id']
        question = request.form['question']
        key_answer = request.form['key_answer']
        answer = request.form['answer']
        
        # TODO: do the analysis here
        
        score = 00
        conn = mysql.connect()
        cur = conn.cursor(pymysql.cursors.DictCursor)
        cur.execute("UPDATE student_answer SET score = %s WHERE student_answer.id = %s", (score, answer_id))
        conn.commit()
        
        status = 200
        data = {
            'id': answer_id,
            'question': question,
            'key_answer': key_answer,
            'answer': answer,
            'score_result': score
            }
        output = {
            'message': "Data processed, get the detailed essay via show API.",
            'data': data
            }
        
    return Response(json.dumps(output), status=status, mimetype='application/json')