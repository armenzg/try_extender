import logging
import os
import string
import requests
import urllib

from flask import Flask, request, jsonify, redirect, abort, session, render_template

from mozci.mozci import trigger_job
from mozci import query_jobs
from mozci.sources import buildjson
from mozci.sources.allthethings import list_builders
from mozci.utils import transfer
from revision_info import jobs_per_revision, get_author


LOG = logging.getLogger()
logging.basicConfig(level=logging.DEBUG)

# Configuring app
app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = os.environ.get('TE_KEY')
app.config['SESSION_TYPE'] = 'filesystem'

transfer.MEMORY_SAVING_MODE = True
USERS = ['alicescarpa@gmail.com']
PORT = int(os.environ.get('PORT', 8080))
DOMAIN = os.environ.get('HEROKU_URL', 'localhost:%d' % PORT)


# Helper functions
def verify_email(email, commit):
    """Verify that an email address is allowed to extend a commit."""
    if email in USERS:
        return True
    elif email.endswith('@mozilla.com'):
        return True
    elif email == get_author(commit):
        return True
    return False


@app.route("/backend/process_data", methods=['POST'])
def process_data():
    email = session.get('email')
    commit = request.form['commit']
    if email is None:
        abort(403, 'Access denied! Please log in first.')

    if not verify_email(email, commit):
        abort(403,
              'You are not allowed to add jobs to this commit.')

    buildernames = map(urllib.unquote, request.form.keys())
    buildernames.remove('commit')

    assert all(c in string.hexdigits for c in commit)
    for buildername in buildernames:
        assert buildername in list_builders()

    for buildername in buildernames:
        print buildername
        trigger_job(buildername=buildername, revision=commit, dry_run=False)

    buildjson.BUILDS_CACHE = {}
    query_jobs.JOBS_CACHE = {}

    TH_URL = "https://treeherder.mozilla.org/#/jobs?repo=try&revision=%s" % commit
    return redirect(TH_URL)


@app.route("/backend/get_json")
def get_json():
    commit = request.args.get('commit')
    if commit is None:
        return redirect('/')

    assert all(c in string.hexdigits for c in commit)

    try:
        ret = jobs_per_revision(commit)
        # Cleaning mozci caches
        buildjson.BUILDS_CACHE = {}
        query_jobs.JOBS_CACHE = {}
        return jsonify(ret)
    except:
        print 'sending bad commit message'
        return jsonify({'Message': 'commit not found'})


@app.route("/")
def index():
    return render_template('index.html')


# Code from https://github.com/mozilla/browserid-cookbook/
@app.route('/auth/login', methods=["POST"])
def login():
    if 'assertion' not in request.form:
        abort(400)

    assertion_info = {'assertion': request.form['assertion'],
                      'audience': request.url_root}  # window.location.host
    resp = requests.post('https://verifier.login.persona.org/verify',
                         data=assertion_info, verify=True)

    if not resp.ok:
        abort(500)

    data = resp.json()

    if data['status'] == 'okay':
        session.update({'email': data['email']})
        return resp.content


@app.route('/auth/logout', methods=["POST"])
def logout():
    session.pop('email', None)
    return redirect('/')


# For running locally without gunicorn
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=PORT)
