from flask import Flask, request, Response
from predict import make_prediction
import json
app = Flask(__name__)

@app.route("/", methods=["GET"])
def welcome():
    output = {
        'message': "Response success!"
    }
    return Response(json.dumps(output), status=200, mimetype='application/json')

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