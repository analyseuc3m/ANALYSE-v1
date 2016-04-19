from celery import task
import logging

from learning_analytics.analytics import (update_DB_course_struct, update_DB_course_spent_time, update_DB_sort_course_homework, update_DB_student_grades, update_DB_course_section_accesses, update_DB_course_problem_progress, update_DB_course_video_progress, time_schedule,update_DB_daily_time_prob_and_vids,update_DB_problem_time_distribution,update_DB_video_time_distribution,update_DB_video_events,update_DB_repetition_video_intervals,update_DB_video_time_watched)
from data import get_courses_list, get_course_key
from opaque_keys.edx.locations import SlashSeparatedCourseKey


@task()
def update_DB_analytics():
	"""
	Update learning analytics DB data
	courses = get_courses_list()
		for course in courses:
	"""
	logging.info("Starting update_DB_analytics()")
	#course_id = get_course_key("CEPA_Sierra_Norte/C1/2015")
	course_id = get_course_key("course-v1:edx+CS112+2015_T3")
		
	update_DB_course_struct(course_id) #OK
	update_DB_student_grades(course_id) # OK
	update_DB_course_spent_time(course_id) #OK
	update_DB_sort_course_homework(course_id) #OK
	update_DB_course_section_accesses(course_id) #OK
	time_schedule(course_id) #OK
	#update_visualization_data(course_id) #OK
	#update_DB_course_problem_progress(course_id) #OK
	#update_DB_course_video_progress(course_id) #OK
	update_DB_daily_time_prob_and_vids(course_id) #OK 
	update_DB_problem_time_distribution(course_id) #OK
	update_DB_video_time_distribution(course_id)
	update_DB_video_events(course_id)
	update_DB_repetition_video_intervals(course_id)
	update_DB_video_time_watched(course_id)
	logging.info("update_DB_analytics() is finished")
	"""
	courses = get_courses_list()
		for course in courses:
	"""