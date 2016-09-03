# canvas-lateness-tool
Exports and aggregates late student submission data


## Quickstart

Setup python virtual environment:

```sh
$ virtualenv pyenv
$ source pyenv/bin/activate
$ pip install -r requirements.txt
```

Setup environment settings and update the `OAUTH_TOKEN` value, which is required to interact with the Canvas API:

```sh
$ cp -v .env.example .env
$ nano .env
```

Run the script on a given canvas course ID:

```sh
$ python canvas_lateness.py
usage: canvas_lateness.py [-h] [--use_cache] [--debug] course_id
```

