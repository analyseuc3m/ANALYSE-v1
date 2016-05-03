from edxmako.shortcuts import render_to_response
from django.contrib.auth.decorators import login_required
#from django_future.csrf import ensure_csrf_cookie
from django.contrib.auth.models import User
from django.http import HttpResponse
import logging
import json
from django.db.models import Q
from learning_analytics.analytics import to_iterable_module_id, get_module_consumption, get_video_time_watched, get_video_events_info, get_user_video_intervals, get_daily_consumption,get_DB_infovideos
from track.backends.django import TrackingLog
#Codigo J. Antonio Gascon
from courseware.courses import get_course_by_id

from json import dumps
from xmodule.modulestore.django import modulestore
from opaque_keys.edx.locator import CourseLocator, BlockUsageLocator
from opaque_keys.edx.locations import Location, SlashSeparatedCourseKey

from analytics import (get_DB_sort_course_homework, get_DB_course_spent_time, get_DB_student_grades, get_DB_course_section_accesses,
                       get_DB_course_video_problem_progress, get_DB_time_schedule, videos_problems_in,
                       ready_for_arraytodatatable, join_video_problem_time)

from operator import truediv

from courseware.access import has_access
from courseware.masquerade import setup_masquerade
from courseware.models import StudentModule
from student.models import CourseEnrollment
from courseware.courses import get_course_with_access, get_studio_url
#from courseware.views import fetch_reverify_banner_info
from data import chapter_time_to_js, students_to_js, course_accesses_to_js, get_info_videos_descriptors,get_course_key, get_course_module, get_course_students, get_course_grade_cutoff

from models import *

VISUALIZATIONS_ID = {'LA_vid_prob_prog': 0,
                     'LA_video_progress': 1,
                     'LA_video_time':2,
                     'LA_problem_time':3,
                     'LA_repetition_video_interval':4,
                     'LA_daily_time': 5,
                     'LA_video_events': 6,
                     'LA_course_sort_students': 7,
                     'LA_student_grades': 8,
                     'LA_chapter_time': 9,
                     'LA_course_accesses': 10,
                     'LA_time_schedule': 11,
                     }

# Constants for student_id
ALL_STUDENTS = -1
PROF_GROUP = -2
PASS_GROUP = -3
FAIL_GROUP = -4



# Create your views here.

@login_required
#@ensure_csrf_cookie
def index(request, course_id):
    # Palette
    color_not = '#CCCCCC'
    color_fail = '#e41a1c'
    color_ok = '#F2F20D'
    color_prof = '#4daf4a'
    problem_activity='#377eb8'
    video_activity='#ff7f00'
    video_repetition='#fdbf6f'
    course_activity='#984ea3'
    graded_time='#88419d'
    ungraded_time='#8c6bb1'
    chapter_time='#8c96c6'
    play_event='#1b9e77'
    pause_event='#d95f02'
    seek_from_event='#7570b3'
    seek_to_event='#e7298a'
    change_speed_event='#66a61e'
    morning_time='#C9C96C'
    afternoon_time ='#7F7160'
    night_time ='#50587C'
    # Request data
    course_key = get_course_key(course_id)
    course = get_course_module(course_key)
    #course2= get_course_by_id(SlashSeparatedCourseKey.from_deprecated_string(course_id))
    #user = request.user #Codigo Jose A. Gascon
    staff_access = has_access(request.user, 'staff', course).has_access#Codigo Jose A. Gascon
    instructor_access = has_access(request.user, 'instructor', course).has_access#Codigo Jose A. Gascon
    #Codigo Jose A. Gascon
    masq, user = setup_masquerade(request, course_key,staff_access, reset_masquerade_data=True)  # allow staff to toggle masquerade on info page
    user = request.user
    studio_url = get_studio_url(course, 'course_info')
    
    #reverifications = fetch_reverify_banner_info(request, course_key)
    
    #course = get_course_with_access(request.user, action='load', course_key=course_key, depth=None, check_if_enrolled=False)
    #user = User.objects.get(request.user.email)
    # Proficiency and pass limit
    pass_limit = get_course_grade_cutoff(course)
    proficiency_limit = (1 - pass_limit) / 2 + pass_limit
    usernames_in = []
    for student in CourseEnrollment.objects.users_enrolled_in(course_key):#Codigo Jose A. Gascon, se cambia la forma de llamar al metode users_enrolled_in
        usernames_in.append(student.username.encode('utf-8'))


    # Data for visualization in JSON
    user_for_charts = '#average' if (staff_access or instructor_access) else user
    kwargs = {
        'qualifiers': {'category': 'video', },
    }     
    # This returns video descriptors in the order they appear on the course
    video_descriptors = videos_problems_in(course)[0]
    #WARNINIG 
    #video_durations = get_info_videos_descriptors(video_descriptors)[2]
    #video_names, video_module_keys, video_durations = get_info_videos_descriptors(video_descriptors) # NO SE USAN LAS OTRAS VARIABLES
    video_names, video_module_keys, video_durations =get_DB_infovideos()
    video_names_sorted = video_names
    video_ids_sort = video_names_sorted

    #course_name = get_course_by_id(course_key, depth=None)
    names_students=[]
    only_students = []
    students_names = get_course_students(course_key)
    print students_names
    for student in students_names:
        staff_access_user = has_access(student, 'staff', course).has_access
        instructor_access_user = has_access(student, 'instructor', course).has_access
        if not (staff_access_user or instructor_access_user):
            names_students.append(student.username.encode('utf-8'))
            only_students.append(student)

    video_ids_str = []
    course_video_names = []
    problem_ids_str=[]
    for descriptor in video_descriptors:
        video_ids_str.append((course_key.make_usage_key('video', descriptor.location.name))._to_string())
        course_video_names.append(descriptor.display_name_with_default)
    if len(video_descriptors) > 0:
        first_video_id = course_key.make_usage_key('video', video_descriptors[0].location.name)
        # Video progress visualization. Video percentage seen total and non-overlapped.
        video_names, avg_video_time, video_percentages = get_video_time_watched(user_for_charts, course_key)  
        if avg_video_time != []:
            all_video_time_percent = map(truediv, avg_video_time, video_durations)
            all_video_time_percent = [int(round(x*100,0)) for x in all_video_time_percent]
        else:
            all_video_time_percent = avg_video_time


        column_headers = ['Video', 'Different video time', 'Total video time']
        # Codigo Javier Orcoyen
        video_prog_json = ready_for_arraytodatatable(column_headers, video_names, video_percentages, all_video_time_percent)
        video_names, all_video_time = get_module_consumption(user_for_charts, course_key, 'video')
        # Time spent on every video resource
        column_headers = ['Video', 'Time watched']
        video_distrib_json = ready_for_arraytodatatable(column_headers, video_names, all_video_time)
  
        # Video events dispersion within video length
        scatter_array = get_video_events_info(user_for_charts, first_video_id)    
  
        # Repetitions per video intervals
        user_for_vid_intervals = '#class_total_times' if user_for_charts == '#average' else user_for_charts
        video_intervals_array = get_user_video_intervals(user_for_vid_intervals, first_video_id)        

    # Case no videos in course
    else:
        video_names = None
        video_prog_json = json.dumps(None)
        video_distrib_json = json.dumps(None)
        scatter_array = json.dumps(None)
        video_intervals_array = json.dumps(None)
          
    # Time spent on every problem resource
    # Codigo Javier Orcoyen
    problem_names, time_x_problem = get_module_consumption(user_for_charts, course_key, 'problem')
    column_headers = ['Problem', 'Time on problem']
    problem_distrib_json = ready_for_arraytodatatable(column_headers, problem_names, time_x_problem)
    print 'USER'
    print user
    problems_in = videos_problems_in(course)[1]
    problem_names_sorted = [x.display_name_with_default.encode('utf-8') for x in problems_in]
    orden=[]
    orden.append(i for i, x in enumerate(problem_names_sorted))
    problem_ids_str=problem_names_sorted
    # Daily time spent on video and/or problem resources
    video_days, video_daily_time = get_daily_consumption(user_for_charts, course_key, 'video')
    problem_days, problem_daily_time = get_daily_consumption(user_for_charts, course_key, 'problem')    
    vid_and_prob_daily_time = join_video_problem_time(video_days, video_daily_time, problem_days, problem_daily_time) 
    #Analytics visualizations
    if staff_access or instructor_access:
        # Instructor access
        std_sort = get_DB_sort_course_homework(course_key)
        # Chapter time
        cs, st = get_DB_course_spent_time(course_key, student_id=ALL_STUDENTS)
        students_spent_time = chapter_time_to_js(cs, st)
        students_grades = get_DB_student_grades(course_key, student_id=ALL_STUDENTS) 
        cs, sa = course_accesses = get_DB_course_section_accesses(course_key, student_id=ALL_STUDENTS)
        students_course_accesses = course_accesses_to_js(cs, sa)
        #students_prob_vid_progress = get_DB_course_video_problem_progress(course_key, student_id=ALL_STUDENTS)# C. J. A. Gascon ERROR
        students_time_schedule = get_DB_time_schedule(course_key, student_id=ALL_STUDENTS)
    else:
        # Sort homework                    
        # Chapter time
        std_sort = None
        cs, st = get_DB_course_spent_time(course_key, user.id)
        students_spent_time = chapter_time_to_js(cs, st) 
        students_grades = get_DB_student_grades(course_key, user.id) 
        cs, sa = course_accesses = get_DB_course_section_accesses(course_key, user.id)
        students_course_accesses = course_accesses_to_js(cs, sa) 
        students_time_schedule = get_DB_time_schedule(course_key, user.id)  
        #students_prob_vid_progress = get_DB_course_video_problem_progress(course_key, user.id)  #C. J. A. Gascon ERROR

    context = {'course': course,
               'request': request,
               'user': user,
               'user_id': user.id,
               'staff_access': staff_access,
               'instructor_access': instructor_access,
               'masquerade': masq,
               'studio_url': studio_url,
               #'reverifications': reverifications,
               'course_id': course_id,
               'students': students_to_js(only_students),
               'visualizations_id': VISUALIZATIONS_ID,
               'std_grades_dump': dumps(students_grades),
               'sort_std_dump': dumps(std_sort),
               'time_dump': dumps(students_spent_time),
               'accesses_dump': dumps(students_course_accesses),
               'std_time_schedule_dumb': dumps(students_time_schedule), 
               #'vid_prob_prog_dump': dumps(students_prob_vid_progress), #C. J. A. Gascon ERROR
               'pass_limit': pass_limit,
               'prof_limit': proficiency_limit,
               'usernames_in' : usernames_in,
               'video_names' : course_video_names,
               'video_ids' : video_ids_str,
               'video_prog_json' : video_prog_json,
               'video_distrib_json' : video_distrib_json,
               'problem_distrib_json' : problem_distrib_json,
               'video_intervals_array' : video_intervals_array,
               'vid_and_prob_daily_time' : vid_and_prob_daily_time,
               'scatter_array' : scatter_array,
               'problem_names' : problem_names,
               'problem_ids' : problem_ids_str,
               'color_not' : color_not,
               'color_ok' : color_ok,
               'color_prof' : color_prof,
               'color_fail' : color_fail,
               'problem_activity' : problem_activity,
               'video_activity' : video_activity,
               'course_activity' : course_activity,
               'video_repetition' : video_repetition,
               'graded_time' : graded_time,
               'ungraded_time' : ungraded_time,
               'chapter_time' : chapter_time,
               'user_for_charts' : user_for_charts,
               'video_ids_sort' : video_ids_sort,
               'video_names_sorted' : video_names_sorted,
               'problem_names_sorted' : problem_names_sorted,
               'play_event' : play_event,
               'pause_event' : pause_event,
               'seek_from_event' : seek_from_event,
               'seek_to_event' : seek_to_event,
               'change_speed_event' : change_speed_event,
               'morning_time' : morning_time,
               'afternoon_time' : afternoon_time,
               'night_time' : night_time,
               'names_students' : names_students,}
        
    return render_to_response('learning_analytics/learning_analytics.html', context)    

@login_required
#@ensure_csrf_cookie
def chart_update(request):

    results = {'success' : False}
    chart_info_json = dumps(results)
    if request.method == u'GET':
        
        GET = request.GET
        user_id = GET[u'user_id']
        user_id = request.user if user_id == "" else user_id
        chart = int(GET[u'chart'])
        course_key = get_course_key(GET[u'course_id'])  

        if chart == VISUALIZATIONS_ID['LA_chapter_time']:
            cs, st = get_DB_course_spent_time(course_key, student_id=user_id)
            student_spent_time = chapter_time_to_js(cs, st)
            chart_info_json = dumps(student_spent_time)
        elif chart == VISUALIZATIONS_ID['LA_course_accesses']:
            cs, sa = get_DB_course_section_accesses(course_key, student_id=user_id)
            student_course_accesses = course_accesses_to_js(cs, sa)
            chart_info_json = dumps(student_course_accesses)
        elif chart == VISUALIZATIONS_ID['LA_student_grades']:            
            students_grades = get_DB_student_grades(course_key, student_id=user_id)
            chart_info_json = dumps(students_grades)
        elif chart == VISUALIZATIONS_ID['LA_time_schedule']:
            student_time_schedule = get_DB_time_schedule(course_key, student_id=user_id)
            chart_info_json = dumps(student_time_schedule)
        elif chart == VISUALIZATIONS_ID['LA_vid_prob_prog']:            
            student_prob_vid_progress = get_DB_course_video_problem_progress(course_key, student_id=user_id)# C. J. A. Gascon ERROR
            chart_info_json = dumps(student_prob_vid_progress)
        elif chart == VISUALIZATIONS_ID['LA_video_progress']:
            # Video progress visualization. Video percentage seen total and non-overlapped.
            course = get_course_with_access(user_id, action='load', course_key=course_key, depth=None, check_if_enrolled=False)         
            #video_descriptors = videos_problems_in(course)[0]
            #video_durations = get_info_videos_descriptors(video_descriptors)[2]
            video_durations = get_DB_infovideos()[2]
            # Codigo Javier Orcoyen
            video_names, avg_video_time, video_percentages = get_video_time_watched(user_id, course_key)
            if avg_video_time != []:
                all_video_time_percent = map(truediv, avg_video_time, video_durations)
                all_video_time_percent = [int(round(x*100,0)) for x in all_video_time_percent]
            else:
                all_video_time_percent = avg_video_time     
            column_headers = ['Video', 'Different video time', 'Total video time']
            chart_info_json = ready_for_arraytodatatable(column_headers, video_names, video_percentages, all_video_time_percent)

        elif chart == VISUALIZATIONS_ID['LA_video_time']:
            # Time spent on every video resource         
            # Codigo Javier Orcoyen     
            video_names, all_video_time = get_module_consumption(user_id, course_key, 'video')
            column_headers = ['Video', 'Time watched']
            chart_info_json = ready_for_arraytodatatable(column_headers, video_names, all_video_time)
        elif chart == VISUALIZATIONS_ID['LA_problem_time']:
            # Time spent on every problem resource   
            # Codigo Javier Orcoyen         
            problem_names, time_x_problem = get_module_consumption(user_id, course_key, 'problem')
            column_headers = ['Problem', 'Time on problem']
            chart_info_json = ready_for_arraytodatatable(column_headers, problem_names, time_x_problem)
        elif chart == VISUALIZATIONS_ID['LA_repetition_video_interval']:
            # Repetitions per video intervals           
            video_name = GET[u'video'] 
            video_id = BlockUsageLocator._from_string(video_name)
            #video_id = Location.from_deprecated_string(video_id._to_deprecated_string())
            chart_info_json = get_user_video_intervals(user_id, video_id)
            
        elif chart == VISUALIZATIONS_ID['LA_daily_time']:
            # Daily time spent on video and/or problem resources            
            video_days, video_daily_time = get_daily_consumption(user_id, course_key, 'video')
            problem_days, problem_daily_time = get_daily_consumption(user_id, course_key, 'problem')    
            chart_info_json = join_video_problem_time(video_days, video_daily_time, problem_days, problem_daily_time)          
        elif chart == VISUALIZATIONS_ID['LA_video_events']:
            # Video events dispersion within video length     
            video_name = GET[u'video']   
            video_id = BlockUsageLocator._from_string(video_name)
            #video_id = Location.from_deprecated_string(video_id._to_deprecated_string())        
            chart_info_json = get_video_events_info(user_id, video_id) 
    
    return HttpResponse(chart_info_json, content_type='application/json')
