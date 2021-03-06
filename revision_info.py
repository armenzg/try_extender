"""Create a graph with information about the existing jobs for a revision."""
import collections
import json
import logging
import requests

from mozci.sources.allthethings import list_builders
from mozci.platforms import is_downstream, determine_upstream_builder, \
    filter_buildernames
from mozci.utils.authentication import get_credentials


LOG = logging.getLogger()
logging.basicConfig(level=logging.INFO)

RESULTS = ['success', 'warning', 'failure', 'skipped', 'exception', 'retry', 'cancelled',
           'pending', 'running', 'coalesced', 'unknown']

TRY_URL = 'https://hg.mozilla.org/try/json-pushes?tipsonly=1'


def generate_builders_relations_dictionary():
    """Create a dictionary that maps every upstream job to its downstream jobs."""
    builders = list_builders()
    relations = collections.defaultdict(list)
    for buildername in builders:
        if is_downstream(buildername):
            relations[determine_upstream_builder(buildername)].append(buildername)
    return relations

UPSTREAM_TO_DOWNSTREAM = None


def load_relations():
    global UPSTREAM_TO_DOWNSTREAM
    if UPSTREAM_TO_DOWNSTREAM is None:
        UPSTREAM_TO_DOWNSTREAM = generate_builders_relations_dictionary()


def get_upstream_buildernames(repo_name):
    """Return every upstream buildername in a repo."""
    buildernames = filter_buildernames([repo_name],
                                       ['hg bundle', 'pgo'],
                                       list_builders())
    upstream_jobs = []
    for buildername in buildernames:
        if not is_downstream(buildername):
            upstream_jobs.append(buildername)
    return upstream_jobs


def get_author(rev):
    """Get the author of a revision."""
    url = "%s&changeset=%s" % (TRY_URL, rev)
    data = requests.get(url).json()
    for push in data:
        return data[push]['user']


def get_list_of_commits(author):
    """Get a list of commits made by a person. If author is None return most recent commits."""
    if author is None:
        url = TRY_URL
    else:
        url = "%s&user=%s" % (TRY_URL, author)
    list_of_commits= []
    data = requests.get(url).json()

    for push in data:
        list_of_commits.append((int(push), data[push]['changesets'][0][:12]))
    list_of_commits = sorted(list_of_commits)[::-1]
    return {author: [x[1] for x in list_of_commits[:10]]}


def get_jobs(rev):
    """Get all jobs that ran in a revision."""
    url = "https://secure.pub.build.mozilla.org/buildapi/self-serve/try/rev/%s?format=json" % rev
    LOG.debug("About to fetch %s" % url)

    req = requests.get(url, auth=get_credentials())

    if req.status_code not in [200]:
        raise Exception

    data = req.json()
    jobs = []
    for build in data:
        jobs.append((build['buildername'], build.get('status')))
    return jobs


def separate_downstream(jobs):
    """Split list of jobs in downstream and upstream."""
    upstream_jobs = []
    downstream_jobs = []
    for job in jobs:
        buildername = job[0]
        # If the job is not on allthethings.json, we will find an exception
        try:
            downstream_status = is_downstream(buildername)
        except:
            continue

        if downstream_status:
            downstream_jobs.append(job)
        else:
            upstream_jobs.append(job)

    return sorted(upstream_jobs), sorted(downstream_jobs)


def jobs_per_revision(revision):
    """Generate a json graph of existing and possible jobs."""
    load_relations()
    all_jobs = get_jobs(revision)

    if all_jobs is None:
        return

    upstream_jobs, downtream_jobs = separate_downstream(all_jobs)

    processed_jobs = {}
    processed_jobs['new_builds'] = {'existing': [], 'possible': []}

    for build_job in upstream_jobs:
        buildername, status = build_job
        if status == 0:
            processed_jobs[buildername] = {'existing': [], 'possible': []}
        else:
            processed_jobs['new_builds']['existing'].append(buildername)

    for test_job in downtream_jobs:
        buildername = test_job[0]
        upstream = determine_upstream_builder(buildername)
        if upstream in processed_jobs:
            if buildername not in processed_jobs[upstream]['existing']:
                processed_jobs[upstream]['existing'].append(buildername)

    for build_job in processed_jobs.keys():
        if build_job == 'new_builds':
            continue

        existing_downstream = set(processed_jobs[build_job]['existing'])
        possible_downstream = sorted(list(
            set(UPSTREAM_TO_DOWNSTREAM[build_job]) - existing_downstream))
        processed_jobs[build_job]['possible'] = possible_downstream
        processed_jobs[build_job]['existing'].sort()

    all_build_jobs = get_upstream_buildernames(' try ') + get_upstream_buildernames('_try_')
    for build_job in all_build_jobs:
        if build_job not in processed_jobs.keys() + processed_jobs['new_builds']['existing']:
            processed_jobs["new_builds"]['possible'].append(build_job)
    processed_jobs["new_builds"]['possible'].sort()

    return processed_jobs


def write_revision_graph(revision):
    """Write the json graph to a file."""
    with open('try_graph.json', 'w') as f:
        graph = jobs_per_revision(revision)
        json.dump(graph, f, sort_keys=True, indent=4, separators=(',', ': '))
