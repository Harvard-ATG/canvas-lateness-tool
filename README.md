# canvas-lateness-tool

This is a command-line tool written in [python](https://www.python.org/) that uses the [canvas_python_sdk](https://github.com/penzance/canvas_python_sdk) to interact with the [Canvas API](https://canvas.instructure.com/doc/api/index.html).

## Instructions

### Setup Environment

To get started, install the required python dependencies specified in the `requirements.txt` file:

```sh
$ pip install -r requirements.txt   # install required dependencies
```

Now update the `.env` file with your personal `OAUTH_TOKEN`, which is required to authenticate with the Canvas API. To obtain a token, go to [your Canvas profile](https://canvas.harvard.edu/profile) and navigate to your [profile settings](https://canvas.harvard.edu/profile/settings). At the bottom of the settings page, you should see a button to create a **New Access Token**. When you click the button, it should open a dialog containing an access token. Copy and paste this value into your `.env` file such that `OAUTH_TOKEN="your_secret_token"`.

```sh
$ cp -v .env.example .env  # copy example configuration
$ nano .env                # edit config to update your oauth token
```

At this point you should have all required python dependencies and the required environment settings.

### Usage

The script takes a canvas course ID as input and then generates a report (an Excel spreadsheet and JSON file):

```sh
$ python canvas_lateness.py --help
usage: canvas_lateness.py [-h] [--student_name {huid,name}] [--use_cache]
                          [--debug]
                          course_id

Generates a spreadsheet with student submission timestamps for each
assignment. Late submissions are called out in red, while on time submissions
are in blue.

positional arguments:
  course_id             Canvas Course ID.

optional arguments:
  -h, --help            show this help message and exit
  --student_name {huid,name}
                        Choose whether to display student name or HUID in the
                        results. (default: huid)
  --use_cache           Use cached data rather than fetching from the API, if
                        it is available. (default: False)
  --debug               Log debugging information. (default: False)
```

Example:

```sh
$ python canvas_lateness.py 39
API fetching students for course: 39
Starting new HTTPS connection (1): canvas.harvard.edu
Writing data to: 39-cache.json
API fetching assignments for course: 39
Writing data to: 39-cache.json
API fetching submissions for course 39 and 1 assignments (assignment_ids: 65141)
[1 of 1] Fetching submissions for assignment_id: 65141...
Writing data to: 39-cache.json
Writing data to: 39-results-20160909.json
Writing spreadsheet to: 39-results-20160909.xls
```

You can then open the generated spreadsheet:

```sh
$ open 39-results-20160909.xls
```

The results will display the student HUID by default, but if you would like to use the student names instead, you can use the `--student_name` option:

```sh
python canvas_lateness 39 --student_name name
```

##Excel Export

The excel spreadsheet generated by the script will have two worksheets. The first contains the _delta time_ (submitted - due) for each student's assignment. The second sheet contains the total lateness, or sum of all positive deltas, for each student. 

Note that assignments will only be included in the spreadsheet if they meet the following criteria:

1. The assignment has a due date.
2. The assignment has at least one submission.

### Sheet 1

| Assignment  | Week 1 Assignment    |                      |                 | Week 2 Assignment    |                      |                 |
|-------------|----------------------|----------------------|-----------------|----------------------|----------------------|-----------------|
| Students    | Due                  | Submitted            | Delta (seconds) | Due                  | Submitted            | Delta (seconds) |
| HUID or Name | 12-Sep-16 11:59:00 PM | 13-Sep-16 8:04:45 PM | 72,345           | 15-Sep-16 11:59:00 PM | 03-Sep-16 5:52:31 PM | -1,058,789          |
|             |                      |                      |                 |                      |                      |                 |

### Sheet 2

| Students    |Total in hours | Total in seconds |
|-------------|-----------------|---------------|-----------------|
| HUID or Name |20            | 72,345          |
|             |               |                 |
