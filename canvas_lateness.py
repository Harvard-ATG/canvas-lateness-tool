from settings import OAUTH_TOKEN, CANVAS_API_URL
from canvas_sdk.methods import courses, assignments, submissions
from canvas_sdk.utils import get_all_list_data
from canvas_sdk import RequestContext

import logging
import argparse
import json
import datetime
import dateutil.parser
import dateutil.tz
import os.path
import xlwt

UTC_TZ = dateutil.tz.gettz('UTC')
EST_TZ = dateutil.tz.gettz('America/New_York')
BASE_PATH = os.path.dirname(os.path.realpath(__file__))

def api_get_students_list(request_context, course_id):
    '''
    Returns a list of all students in the course.
    
    https://canvas.instructure.com/doc/api/courses.html#method.courses.users
    '''
    results = get_all_list_data(request_context, courses.list_users_in_course_users, course_id, "email", enrollment_type="student")
    students = sorted([{"sortable_name":x['sortable_name'], "id": x['id']} for x in results], key=lambda x: x['sortable_name'])
    logging.debug("Students in course: %s" % students)
    return list(students)

def api_get_assignments_list(request_context, course_id):
    '''
    Returns a list of assignments for the course.

    https://canvas.instructure.com/doc/api/assignments.html#method.assignments_api.index 
    '''
    results = get_all_list_data(request_context, assignments.list_assignments, course_id, '')
    logging.debug("Assignments List: %s" % [r['id'] for r in results]) 
    return results

def api_get_submissions(request_context, course_id, assignment_ids):
    '''
    Returns the submission data for each assignment.

    https://canvas.instructure.com/doc/api/submissions.html#method.submissions_api.index
    '''
    include = "assignment"
    results = []
    for assignment_id in assignment_ids:
        list_data = get_all_list_data(request_context, submissions.list_assignment_submissions_courses, course_id, assignment_id, include)
        logging.debug("Submissions for assignment %s: %s" % (assignment_id, list_data))
        results.append({"assignment_id": assignment_id, "submissions": list_data})
    return results

def fetch_data(course_id):
    '''
    Fetches students, assignments, and submissions from the canvas API.
    '''
    request_context = RequestContext(OAUTH_TOKEN, CANVAS_API_URL, per_page=100)
    students = api_get_students_list(request_context, course_id)
    assignments = api_get_assignments_list(request_context, course_id)
    submissions = api_get_submissions(request_context, course_id, [a['id'] for a in assignments])
    data = {
        'assignments': assignments,
        'submissions': submissions,
        'students': students,
    }
    return data

def load_data(course_id, cache_file, use_cache=False):
    '''
    Loads data from local cache or from the Canvas API.

    Only loads from the cache if the cache data is available
    and if use_cache=True.
    '''
    data = None
    if use_cache and os.path.exists(cache_file):
        logging.info("Loading data from %s instead of fetching from %s" % (cache_file, CANVAS_API_URL))
        with open(cache_file, 'r') as f:
            data = json.load(f)
    else:
        logging.info("Fetching data from %s" % CANVAS_API_URL)
        data = fetch_data(course_id)
        save_json(filename=cache_file, data=data)
    return data

def save_json(filename=None, data=None):
    '''
    Helper to save data to a JSON file.
    '''
    if filename is None:
        raise Exception("Filename is required")
    logging.info("Writing data to %s" % filename)
    with open(filename, 'w') as outfile:
        json.dump(data, outfile, sort_keys=True, indent=2)

def save_spreadsheet(filename=None, data=None):
    '''
    Creates a spreadsheet with the data.
    '''
    if filename is None:
        raise Exception("Filename is required")

def main():
    logging.basicConfig(filename='debug.log', level=logging.DEBUG)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    logging.getLogger('').addHandler(console) # add to root handler

    parser = argparse.ArgumentParser(description="Export lateness data for each student's assignment")
    parser.add_argument('course_id', help='Canvas Course ID')
    parser.add_argument('--use_cache',  dest='use_cache', action='store_true', help="Use cached data (if available) rather than fetching from the API")
    parser.set_defaults(use_cache=False)
    args = parser.parse_args()
    logging.debug("CLI args: %s" % args)

    cache_file = os.path.join(BASE_PATH, "%s-cache.json" % args.course_id)
    data = load_data(args.course_id, cache_file, use_cache=args.use_cache)

    spreadsheet_filename = os.path.join(BASE_PATH, "%s-export.xls" % args.course_id)
    save_spreadsheet(filename=spreadsheet_filename, data=data)
    logging.debug("Done.")

if __name__ == "__main__":
    main()
