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
    logging.info("API fetching students for course: %s" % course_id)
    results = get_all_list_data(request_context, courses.list_users_in_course_users, course_id, "email", enrollment_type="student")

    # reduce the student data to the subset that we need
    students = [{
        "id":             x['id'],           # canvas ID for user 
        "sis_user_id":    x['sis_user_id'],  # huid from student information systems 
        "sortable_name":  x['sortable_name'], 
        "name":           x['name'],
    } for x in results]

    logging.debug("Students in course: %s" % students)

    return list(students)

def api_get_assignments_list(request_context, course_id):
    '''
    Returns a list of assignments for the course.

    https://canvas.instructure.com/doc/api/assignments.html#method.assignments_api.index 
    '''
    logging.info("API fetching assignments for course: %s" % course_id)
    results = get_all_list_data(request_context, assignments.list_assignments, course_id, '')
    logging.debug("Assignments List: %s" % [r['id'] for r in results]) 
    return results

def api_get_submissions(request_context, course_id, assignment_ids):
    '''
    Returns the submission data for each assignment.

    https://canvas.instructure.com/doc/api/submissions.html#method.submissions_api.index
    '''
    logging.info("API fetching submissions for course %s and %d assignments (assignment_ids: %s)" % (course_id, len(assignment_ids), ', '.join(map(str, assignment_ids))))
    include = "assignment"
    results = []
    for position, assignment_id in enumerate(assignment_ids, start=1):
        logging.info("[%d of %d] Fetching submissions for assignment_id: %d..." % (position, len(assignment_ids), assignment_id))
        list_data = get_all_list_data(request_context, submissions.list_assignment_submissions_courses, course_id, assignment_id, include)
        logging.debug("Submissions for assignment %s: %s" % (assignment_id, list_data))
        results.append({"assignment_id": assignment_id, "submissions": list_data})
    return results

def load(course_id, cache_file, use_cache=False):
    '''
    Loads data from local cache or from the Canvas API.
    '''
    data = {}
    savecache = lambda: cache_write(cache_file, data)
    if use_cache:
        data = cache_read(cache_file) or {}

    request_context = RequestContext(OAUTH_TOKEN, CANVAS_API_URL, per_page=100)
    if 'students' not in data:
        data['students'] = api_get_students_list(request_context, course_id)
        savecache()
    if 'assignments' not in data:
        data['assignments'] = api_get_assignments_list(request_context, course_id)
        savecache()
    if 'submissions' not in data:
        data['submissions'] = api_get_submissions(request_context, course_id, [a['id'] for a in data['assignments']])
        savecache()

    return data

def process(data, student_identifier=None):
    '''
    Transforms the raw data retrieved from the API into data about each student's "lateness"
    for each assignment. The data is returned in a format suitable for output. 
    '''

    # initialize 
    assignment_ids = [a['id'] for a in data['assignments']]
    zero_delta = datetime.timedelta(days=0, seconds=0, microseconds=0)

    # configures the student identifier that should be used
    student_identifier_choices = {
        'huid': {'field': 'sis_user_id', 'sortkey': lambda s: s['sis_user_id']},
        'name': {'field': 'sortable_name', 'sortkey': lambda s: s['sortable_name']},
    }
    student_descriptor = student_identifier_choices.get(student_identifier, student_identifier_choices['huid'])

    # group submissions by assignment and student for easy lookup
    submissions_by_assignment = {}
    submissions_by_student = {}
    for sub_item in data['submissions']:
        assignment_id = sub_item['assignment_id']
        if assignment_id not in assignment_ids:
            continue
        assignment_subs = sorted(sub_item['submissions'], key=lambda s: (s['user_id'], s['assignment_id'], s['submitted_at']))
        submissions_by_assignment[assignment_id] = assignment_subs
        for assignment_sub in assignment_subs:
            submissions_by_student.setdefault(assignment_sub['user_id'], {}).setdefault(assignment_id, []).append(assignment_sub)

    # aggregate the results
    results = []
    display_date_format = '%a, %b %d at %I:%M%p'
    for student in sorted(data['students'], key=student_descriptor['sortkey']):
        student_id = student['id']
        student_result = {
            'student_id': student_id, 
            'student_name': student.get(student_descriptor['field']), 
            'assignments': [],
        }
        total_lateness = zero_delta
        for assignment in sorted(data['assignments'], key=lambda a: (a.get('assignment_group_id', 0), a['position'])):
            assignment_id = assignment['id']
            assignment_subs = submissions_by_assignment[assignment_id]

            # skip when the assignment has no submissions or has no due date, because
            # in either case there's no time delta to compare 
            if len(assignment_subs) == 0 or not assignment['due_at']:
                continue

            student_assignment_subs = submissions_by_student.get(student_id, {}).get(assignment_id, [])

            # parse the assignment due date
            due_date_iso = assignment['due_at']
            due_date = None
            due_date_display = ''
            if due_date_iso:
                due_date = dateutil.parser.parse(due_date_iso).replace(tzinfo=UTC_TZ)
                due_date_display = due_date.astimezone(EST_TZ).strftime(display_date_format)

            # parse the date of the last submission attempt
            sub_date_iso = ''
            sub_date = None
            sub_date_display = ''
            if len(student_assignment_subs) > 0:
                sub_item = student_assignment_subs[-1]
                sub_date_iso = sub_item['submitted_at']
                if sub_date_iso:
                    sub_date = dateutil.parser.parse(sub_date_iso).replace(tzinfo=UTC_TZ)
                    sub_date_display = sub_date.astimezone(EST_TZ).strftime(display_date_format)

            # calculate the delta
            time_delta = None
            time_delta_seconds = None
            if due_date and sub_date:
                time_delta = sub_date - due_date
                time_delta_seconds = int(time_delta.total_seconds())
                
            # accumulate the total lateness
            if time_delta is not None and time_delta > zero_delta:
                total_lateness += time_delta

            # add assignment delta 
            student_result['assignments'].append({
                'assignment_id': assignment['id'],
                'assignment_name': assignment['name'],
                'due_date_iso': due_date_iso,
                'due_date_display': due_date_display,
                'submission_date_iso': sub_date_iso,
                'submission_date_display': sub_date_display,
                'time_delta_seconds': time_delta_seconds,
            })

        # update total delta
        student_result['total_lateness_seconds'] = int(total_lateness.total_seconds())
        student_result['total_lateness_hours'] = int(total_lateness.total_seconds() / 3600) # round down to be nice

        results.append(student_result)

    return results

def cache_read(filename):
    '''
    Helper to read data from a JSON file.
    '''
    data = None
    if os.path.exists(filename):
        logging.info("Reading data from: %s" % filename)
        with open(filename, 'r') as f:
            data = json.load(f)
        if isinstance(data, dict):
            logging.debug("File contains top-level keys: %s" % ", ".join(data.keys()))
    else:
        logging.info("File does not exist: %s" % filename)
    return data

def cache_write(filename, data):
    '''
    Helper to save data to a JSON file.
    '''
    logging.info("Writing data to: %s" % filename)
    with open(filename, 'w') as outfile:
        json.dump(data, outfile, sort_keys=True, indent=2)
    return data

def create_spreadsheet(filename, data, results):
    '''
    Creates a spreadsheet with the data.
    '''
    # Styles
    bold_style = xlwt.easyxf('font: bold 1')
    right_align = xlwt.easyxf("align: horiz right")
    delta_style = xlwt.easyxf(num_format_str='[Red]###,###,##0;[Blue]-###,###,##0;[Black]0')
    date_style = xlwt.easyxf(num_format_str='dd-mmm-yy h:mm:ss AM/PM')

    # Formats
    student_fmt = u'{student_name}'
    student_width = 256 * max([len(student_fmt.format(**r)) for r in results] + [12]) # magic num to ensure min width

    # Helper functions
    parse_iso_date = lambda d: dateutil.parser.parse(d).replace(tzinfo=UTC_TZ).astimezone(EST_TZ).replace(tzinfo=None)

    # Create workbook
    wb = xlwt.Workbook(encoding="utf-8")

    # Worksheet #1 w/ Submission Time Deltas
    ws = wb.add_sheet('Delta Sheet', cell_overwrite_ok=True)
    ws.write(0,0, u'Assignment \u2192'.encode('utf-8'), right_align)
    ws.write(1,0, u'Students \u2193'.encode('utf-8'), right_align)
    ws.col(0).width = student_width

    row = 2
    for result in results:
        student_name_str = student_fmt.format(student_name=result['student_name']) 
        ws.write(row, 0, student_name_str)

        for asstpos, asst in enumerate(result['assignments']):
            assignment_name_str = u'{name} ({id})'.format(name=asst['assignment_name'], id=asst['assignment_id'])
            due_date = parse_iso_date(asst['due_date_iso'])
            sub_date = '' if not asst['submission_date_iso'] else parse_iso_date(asst['submission_date_iso'])
            columns = (
                ('Due', due_date, date_style),
                ('Submitted', sub_date, date_style),
                ('Delta (seconds)', asst['time_delta_seconds'], delta_style),
            )
            column_widths = (
                (256 * len(asst['due_date_iso'])),
                (256 * len(asst['due_date_iso'])),
                (256 * len(columns[-1][0])),
            )
            colstart = asstpos * len(columns) + 1

            ws.write(0, colstart, assignment_name_str, bold_style)
            for colpos, column in enumerate(columns):
                ws.write(1, colstart+colpos, column[0], bold_style) # column header
                ws.write(row, colstart+colpos, *column[1:]) # column value for student
                ws.col(colstart+colpos).width = column_widths[colpos]
        row += 1

    # Worksheet #2 w/ Cumulative Lateness
    ws = wb.add_sheet('Lateness Sheet', cell_overwrite_ok=True)
    ws.col(0).width = student_width
    ws.write(0,0, u'Students'.encode('utf-8'), bold_style)

    row = 1
    for result in results:
        student_name_str = student_fmt.format(student_name=result['student_name']) 
        ws.write(row, 0, student_name_str)
        columns = (
            ('Total in hours', result['total_lateness_hours'], delta_style),
            ('Total in seconds', result['total_lateness_seconds'], delta_style),
        )
        colstart = 1
        for colpos, column in enumerate(columns):
            ws.write(0, colstart+colpos, column[0], bold_style) # column header
            ws.write(row, colstart+colpos, *column[1:]) # column value for student
        row += 1

    logging.info("Writing spreadsheet to: %s" % filename)
    wb.save(filename)

def main():
    # get CLI args
    parser = argparse.ArgumentParser(description="Generates a spreadsheet with student submission timestamps for each assignment. Late submissions are called out in red, while on time submissions are in blue.", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('course_id', help='Canvas Course ID.')
    parser.add_argument('--student_identifier', choices=['huid', 'name'], default='huid', help="Choose to identify students by name or HUID in the results.")
    parser.add_argument('--use_cache',  dest='use_cache', action='store_true', help="Use cached data rather than fetching from the API, if it is available.")
    parser.add_argument('--debug',  dest='debug', action='store_true', help="Log debugging information. ")
    parser.set_defaults(use_cache=False)
    parser.set_defaults(debug=False)
    args = parser.parse_args()

    # configure logging
    loggingConfig = {'filename': 'output.log', 'level': logging.INFO}
    if args.debug:
        loggingConfig['level'] = logging.DEBUG
    logging.basicConfig(**loggingConfig)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(loggingConfig['level'])
    requests_log.propagate = True
    console = logging.StreamHandler()
    console.setLevel(logging.INFO) # only ever output info to the console
    logging.getLogger('').addHandler(console) # add to root handler

    # configure output filenames
    today = datetime.date.today().isoformat().replace('-','')
    cache_file = os.path.join(BASE_PATH, "%s-cache.json" % args.course_id)
    results_json_file = os.path.join(BASE_PATH, "%s-results-%s.json" % (args.course_id, today))
    results_xls_file = os.path.join(BASE_PATH, "%s-results-%s.xls" % (args.course_id, today))

    # fetch and process the data
    logging.debug("Begin.")
    data = load(args.course_id, cache_file, use_cache=args.use_cache)
    if len(data['students']) == 0:
        logging.info("No students found in the course, so can't generate a report.")
    else:
        results = process(data, student_identifier=args.student_identifier)
        cache_write(results_json_file, results)
        create_spreadsheet(results_xls_file, data, results)
    logging.debug("Done.")

if __name__ == "__main__":
    main()
