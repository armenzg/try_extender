from flask import Flask, request, jsonify
from urllib import unquote

from mozci.mozci import trigger_job
from revision_info import jobs_per_revision

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.debug = True


@app.route("/backend/process_data", methods=['POST'])
def process_data():
    buildernames = map(unquote, request.form.keys())
    buildernames.remove('commit')
    commit = request.form['commit']
    for buildername in buildernames:
        trigger_job(buildername=buildername, revision=commit, dry_run=True)
    return jsonify(request.form)

@app.route("/backend/get_json")
def get_json():
    commit = request.values['commit']
    return jsonify(jobs_per_revision(commit))

if __name__ == "__main__":
    app.run(host='0.0.0.0')
