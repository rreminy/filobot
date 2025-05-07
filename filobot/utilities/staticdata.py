import json
import os
import sys

marks_info = {}
fates_info = {}

with open(os.path.dirname(os.path.realpath(sys.argv[0])) + os.sep + os.path.join('data', 'marks_info.json'), 'r', encoding='utf-8') as json_file:
    marks_info = json.load(json_file)
with open(os.path.dirname(os.path.realpath(sys.argv[0])) + os.sep + os.path.join('data', 'fates_info.json'), 'r', encoding='utf-8') as json_file:
    fates_info = json.load(json_file)
with open(os.path.dirname(os.path.realpath(sys.argv[0])) + os.sep + os.path.join('data', 'achievementfates_info.json'), 'r', encoding='utf-8') as json_file:
    fates_info.update(json.load(json_file))