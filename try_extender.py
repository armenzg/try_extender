import string

from flask import Flask, request, jsonify, redirect
from urllib import unquote

from mozci.mozci import trigger_job
from mozci import query_jobs
from mozci.sources import buildjson
from mozci.sources.allthethings import list_builders
from mozci.utils.transfer import MEMORY_SAVING_MODE
from revision_info import jobs_per_revision

app = Flask(__name__, static_folder='static', static_url_path='/static')
MEMORY_SAVING_MODE = True
#app.debug = True


@app.route("/backend/process_data", methods=['POST'])
def process_data():
    buildernames = map(unquote, request.form.keys())
    buildernames.remove('commit')
    commit = request.form['commit']

    assert all(c in string.hexdigits for c in commit)
    for buildername in buildernames:
        assert buildername in list_builders()

    for buildername in buildernames:
        trigger_job(buildername=buildername, revision=commit, dry_run=True)

    buildjson.BUILDS_CACHE = {}
    query_jobs.JOBS_CACHE = {}

    return jsonify(request.form)

@app.route("/backend/get_json")
def get_json():
    commit = request.values['commit']
    assert all(c in string.hexdigits for c in commit)
    ret = jobs_per_revision(commit)

    buildjson.BUILDS_CACHE = {}
    query_jobs.JOBS_CACHE = {}

    return jsonify(ret)

@app.route("/")
def index():
    return redirect("/static/json_test.html")


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
