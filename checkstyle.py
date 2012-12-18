"""
Copyright (c) 2012, Daniel Skinner <daniel@dasa.cc>
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""
import logging
import subprocess
import threading

import sublime
import sublime_plugin


def logger(level):
    sh = logging.StreamHandler()
    sh.setLevel(logging.DEBUG)
    sh.setFormatter(logging.Formatter('%(levelname)s:%(name)s:%(message)s'))
    log = logging.getLogger(__name__)
    log.setLevel(level)
    log.addHandler(sh)
    return log


log = logger(logging.DEBUG)


_settings = None
_regions = []
_msgs = []


def get_setting(key, default=None):
    global _settings
    try:
        s = sublime.active_window().active_view().settings()
        if s.has(key):
            return s.get(key)
    except:
        pass
    if _settings is None:
        _settings = sublime.load_settings("Checkstyle.sublime-settings")
    return _settings.get(key, default)


def checkstyle(view, callback=None):
    scope = view.scope_name(view.sel()[0].begin())
    if not get_setting("checkstyle", True) or "source.java" not in scope:
        log.debug("disabled")
        return

    checkstyle_cmd = get_setting("checkstyle_cmd")
    config_xml = get_setting("checkstyle_config_xml")
    args = get_setting("checkstyle_args", [])

    cmd = [checkstyle_cmd, "-c", config_xml] + args + [view.file_name()]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def wait(p, view, callback):
        p.wait()
        stdout = p.stdout.read()
        stderr = p.stderr.read()
        if callback is not None:
            callback(view, stdout, stderr)

    threading.Thread(target=wait, args=(p, view, callback)).start()


def show_results(view, stdout, stderr):
    global _regions, _msgs
    log.debug("Showing results.")
    _regions = []
    _msgs = []

    for line in stdout.split("\n"):
        try:
            parts = [s.strip() for s in line.split(":")][1:]
            if not parts or len(parts) < 2:
                continue
            msg = parts.pop(-1)
            row = int(parts.pop(0)) - 1
            col = 0
            # TODO make use of `col` correctly so it doesn't cause region
            # to market the line after.
            #if parts:
            #    col = int(parts.pop(0)) - 1
            point = view.text_point(row, col)
            region = view.line(point)

            _regions.append(region)
            _msgs.append(msg)
        except Exception as e:
            log.error(e)
    view.add_regions("checkstyle", _regions, "comment", sublime.DRAW_OUTLINED)


def update_status(view):
    global _regions, _msgs
    pos = view.sel()[0].begin()
    for i, region in enumerate(_regions):
        if region.contains(pos):
            view.set_status("checkstyle", _msgs[i])
            return
    view.erase_status("checkstyle")


class CheckstyleListener(sublime_plugin.EventListener):
    def on_post_save(self, view):
        checkstyle(view, show_results)

    def on_modified(self, view):
        global _regions, _msgs
        _regions = []
        _msgs = []
        view.erase_status("checkstyle")
        view.erase_regions("checkstyle")

    def on_selection_modified(self, view):
        if view.is_scratch():
            return

        update_status(view)
