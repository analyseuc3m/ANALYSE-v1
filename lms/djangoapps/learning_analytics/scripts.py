from track.backends.django import TrackingLog

from datetime import datetime
# Para el shell de Django ./manage.py lms shell --settings=devstack_analytics

from learning_analytics.data import get_courses_list, get_course_students, get_course_module, get_course_key
from learning_analytics.data import videos_problems_in, get_info_videos
from learning_analytics.analytics import get_daily_consumption
#from learning_analytics.data_processing import videos_problems_in, get_info_videos
#from learning_analytics.data_querying import get_daily_consumption
#from learning_analytics.analytics_jose import time_schedule
#from learning_analytics.celeryHector import update_visualization_data
from learning_analytics.data import get_courses_list, get_course_students, get_course_module, get_course_key
from learning_analytics.analytics import (update_DB_course_struct, update_DB_course_spent_time, update_DB_sort_course_homework, update_DB_student_grades, update_DB_course_section_accesses, update_DB_course_problem_progress, update_DB_course_video_progress, time_schedule,update_DB_daily_time_prob_and_vids,update_DB_problem_time_distribution,update_DB_video_time_distribution,update_DB_video_events,update_DB_repetition_video_intervals,update_DB_video_time_watched)
course_id = get_course_key("course-v1:edx+CS102+2016_T3")

#course_id = get_course_key("UC3M/EVAL2014/DECEMBER")
#course_id = get_course_key("UC3M/Q103/2014")
course_id = get_course_key("course-v1:edx+CS112+2015_T3")
#course_id = get_course_key("course-v1:edx+CS102+2016_T3")


update_DB_course_struct(course_id) #OK                                                        learning_analytics_coursestruct
update_DB_student_grades(course_id) # OK                                                        learning_analytics_studentgrades
update_DB_course_spent_time(course_id) #OK                                                    learning_analytics_coursetime 
update_DB_sort_course_homework(course_id) #OK, actualiza solo                                learning_analytics_sortgrades 
update_DB_course_section_accesses(course_id) #OK                                             learning_analytics_courseaccesses
time_schedule(course_id) #OK                                                                    learning_analytics_timeschedule
#update_visualization_data(course_id) #OK NO ESTA DEFINIDO, CAMBIA NOMBRE
update_DB_course_problem_progress(course_id) #OK Se prueba sin comentar la optimizacion y no hay progreso        learning_analytics_courseprobvidprogress
update_DB_course_video_progress(course_id) #OK                                                                     learning_analytics_courseprobvidprogress
#NUEVAS
update_DB_daily_time_prob_and_vids(course_id) #OK                                            learning_analytics_dailyconsumption
update_DB_problem_time_distribution(course_id) #OK, parece que cuadran                        learning_analytics_consumptionmodule 
update_DB_video_time_distribution(course_id) #OK Valores de PORCENTAJE RAROS                    learning_analytics_consumptionmodule 
update_DB_video_events(course_id) #OK, sospecho                                                learning_analytics_videoevents
update_DB_repetition_video_intervals(course_id) #OK, sospecho                                     learning_analytics_videointervals
update_DB_video_time_watched(course_id) #OK, falla y tiene elementos vacios hay que ver find_video_intervals porque luego lleva eventos vacios a get_new_module_events_sql     learning_analytics_videotimewatched

