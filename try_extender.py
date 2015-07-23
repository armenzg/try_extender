from flask import Flask, request
import json

app = Flask(__name__)
app.debug = True


@app.route("/backend/process_data", methods=['POST'])
def process_data():
    return json.dumps(request.form)

if __name__ == "__main__":
    app.run(host='0.0.0.0')
