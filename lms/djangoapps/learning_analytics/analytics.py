
from courseware.grades import iterate_grades_for
from courseware.models import StudentModule
from courseware.courses import get_course_by_id
from student.models import CourseEnrollment
from data import *
from datetime import timedelta
from django.contrib.auth.models import User
from django.utils import timezone
from models import *
from classes import *

from django.db.models import Q

import copy, datetime, ast, math, re

import json
from courseware.access import has_access #Codigo Jose A. Gascon
from operator import truediv
import logging

from track.backends.django import TrackingLog

INACTIVITY_TIME = 600  # Time considered inactivity


##########################################################################
######################## COURSE STRUCT ###################################
##########################################################################


def update_DB_course_struct(course_key):
    """
    Saves course structure to database
    """
    # Get course
    #print course_key
    course = get_course_module(course_key)
    
    # Create return structure
    course_struct = get_course_struct(course)
    
    chapters_sql = CourseStruct.objects.filter(course_id=course_key, section_type='chapter')
    sequentials_sql = CourseStruct.objects.filter(course_id=course_key, section_type='sequential')
    verticals_sql = CourseStruct.objects.filter(course_id=course_key, section_type='vertical')
    
    chapter_index = 1
    for chapter in course_struct['chapters']:
        chapters_sql_filtered = chapters_sql.filter(module_state_key=chapter['id'])
        if (chapters_sql_filtered.count() == 0):
            # Create entry
            CourseStruct.objects.create(course_id=course_key,
                                      module_state_key=chapter['id'],
                                      name=chapter['name'],
                                      section_type='chapter',
                                      graded=chapter['graded'],
                                      released=chapter['released'],
                                      index=chapter_index)
        else:
            # Update entry
            chapters_sql_filtered.update(name=chapter['name'],
                                         section_type='chapter',
                                         graded=chapter['graded'],
                                         released=chapter['released'],
                                         index=chapter_index)
        # Sequentials
        seq_index = 1
        chapt_seq_sql = sequentials_sql.filter(father=chapters_sql.get(module_state_key=chapter['id']))
        for sequential in chapter['sequentials']:
            chapt_seq_sql_filtered = chapt_seq_sql.filter(module_state_key=sequential['id'])
            if(chapt_seq_sql_filtered.count() == 0):
                # Create entry
                CourseStruct.objects.create(course_id=course_key,
                                            module_state_key=sequential['id'],
                                            name=sequential['name'],
                                            section_type='sequential',
                                            father=chapters_sql.get(module_state_key=chapter['id']),
                                            graded=sequential['graded'],
                                            released=sequential['released'],
                                            index=seq_index)
            else:
                # Update entry
                chapt_seq_sql_filtered.update(name=sequential['name'],
                                              section_type='sequential',
                                              graded=sequential['graded'],
                                              released=sequential['released'],
                                              index=seq_index)
            seq_index += 1
            
            # Verticals
            vert_index = 1
            seq_vert_sql = verticals_sql.filter(father=sequentials_sql.get(module_state_key=sequential['id']))
            for vertical in sequential['verticals']:
                seq_ver_sql_filtered = seq_vert_sql.filter(module_state_key=vertical['id'])
                if(seq_ver_sql_filtered.count() == 0):
                    # Create entry
                    CourseStruct.objects.create(course_id=course_key,
                                                module_state_key=vertical['id'],
                                                name=vertical['name'],
                                                section_type='vertical',
                                                father=sequentials_sql.get(module_state_key=sequential['id']),
                                                graded=vertical['graded'],
                                                released=vertical['released'],
                                                index=vert_index)
                else:
                    # Update entry
                    seq_ver_sql_filtered.update(name=vertical['name'],
                                                section_type='vertical',
                                                graded=vertical['graded'],
                                                released=vertical['released'],
                                                index=vert_index)
                vert_index += 1
        chapter_index += 1
    
    
def get_DB_course_struct(course_key, include_verticals=False, include_unreleased=True):
    """
    Gets course structure from database
    
    course_key: course locator
    include_verticals: if true, the result will include verticals
    incluse_unreleased: if true, the result will include unreleased sections
    """
    # Course struct
    course_struct = []
    if include_unreleased:
        sql_struct = CourseStruct.objects.filter(course_id=course_key)
    else:
        sql_struct = CourseStruct.objects.filter(course_id=course_key, released=True)
    
    num_ch = sql_struct.filter(section_type='chapter').count()
    for i in range(1, num_ch + 1):
        chapt = sql_struct.filter(section_type='chapter', index=i)
        if chapt.count() != 0:
            chapt = chapt[0]
        else:
            return None
        
        ch_cont = {'id': chapt.id,
                   'module_id': chapt.module_state_key,
                   'name': chapt.name,
                   'graded': chapt.graded,
                   'type': 'chapter',
                   'sequentials': []}
        
        num_seqs = sql_struct.filter(section_type='sequential', father_id=chapt.id).count()
        for j in range(1, num_seqs + 1):
            seq = sql_struct.filter(section_type='sequential', father_id=chapt.id, index=j)
            if seq.count() != 0:
                seq = seq[0]
            else:
                return None
            
            if include_verticals:
                seq_cont = {'id': seq.id,
                            'module_id': seq.module_state_key,
                            'name': seq.name,
                            'graded': seq.graded,
                            'type': 'sequential',
                            'verticals': []}
                num_verts = sql_struct.filter(section_type='vertical', father_id=seq.id).count()
                for k in range(1, num_verts + 1):
                    vert = sql_struct.filter(section_type='vertical', father_id=seq.id, index=k)
                    if vert.count() != 0:
                        vert = vert[0]
                    else:
                        return None
                    seq_cont['verticals'].append({'id': vert.id,
                                                  'module_id': vert.module_state_key,
                                                  'name': vert.name,
                                                  'graded': vert.graded,
                                                  'type': 'vertical'})
                ch_cont['sequentials'].append(seq_cont)
            else:
                ch_cont['sequentials'].append({'id': seq.id,
                                               'module_id': seq.module_state_key,
                                               'name': seq.name,
                                               'graded': seq.graded,
                                               'type': 'sequential'})
        course_struct.append(ch_cont)
    return course_struct


#################################################################################
######################## SORT COURSE STUDENTS VISUALIZATION #####################
#################################################################################


def sort_course_homework(course_key):
    """
    Sort number of students that haven't done, have fail, have done ok, or
    have done very good each homework of a given course
    """
    
    course = get_course_module(course_key)
    
    pass_limit = get_course_grade_cutoff(course)
    proficiency_limit = (1 - pass_limit) / 2 + pass_limit

    # Obtain all sections with their released problems from grading_context
    full_gc = dump_full_grading_context(course)
    
    # Fill sort_homework
    sort_homework = {'graded_sections':[],
                     'weight_subsections':[]}
    
    for section in full_gc['graded_sections']:
        if section['released']:
            sort_homework['graded_sections'].append({'category': section['category'], 'label': section['label'],
                                                     'name': section['name'], 'NOT': 0, 'FAIL': 0,
                                                     'OK': 0, 'PROFICIENCY': 0})
    
    for subsection in full_gc['weight_subsections']:
        for grad_section in sort_homework['graded_sections']:
            if grad_section['category'] == subsection['category']:
                sort_homework['weight_subsections'].append({'category': subsection['category'], 'NOT': 0,
                                                            'FAIL': 0, 'OK': 0, 'PROFICIENCY': 0})
                break
            
    sort_homework['weight_subsections'].append({'category': 'Total', 'NOT': 0,
                                                'FAIL': 0, 'OK': 0, 'PROFICIENCY': 0})
    

    student_grades = (StudentGrades.objects.filter(course_id=course_key)
                      .filter(~Q(student_id=StudentGrades.ALL_STUDENTS))
                      .filter(~Q(student_id=StudentGrades.PROF_GROUP))
                      .filter(~Q(student_id=StudentGrades.PASS_GROUP))
                      .filter(~Q(student_id=StudentGrades.FAIL_GROUP)))    
                           
    for student_grade in student_grades:
        grades = ast.literal_eval(student_grade.grades)
        
        for i in range(len(grades['graded_sections'])):
            if grades['graded_sections'][i]['done'] and grades['graded_sections'][i]['total'] > 0:
                percent = grades['graded_sections'][i]['score'] / grades['graded_sections'][i]['total']
                if percent >= proficiency_limit:
                    sort_homework['graded_sections'][i]['PROFICIENCY'] += 1
                elif percent >= pass_limit:
                    sort_homework['graded_sections'][i]['OK'] += 1
                else:
                    sort_homework['graded_sections'][i]['FAIL'] += 1
            else:
                sort_homework['graded_sections'][i]['NOT'] += 1
        
        for j in range(len(grades['weight_subsections'])):
            if grades['weight_subsections'][j]['done'] and grades['weight_subsections'][j]['total'] > 0:
                percent = grades['weight_subsections'][j]['score'] / grades['weight_subsections'][j]['total']
                if percent >= proficiency_limit:
                    sort_homework['weight_subsections'][j]['PROFICIENCY'] += 1
                elif percent >= pass_limit:
                    sort_homework['weight_subsections'][j]['OK'] += 1
                else:
                    sort_homework['weight_subsections'][j]['FAIL'] += 1
            else:
                sort_homework['weight_subsections'][j]['NOT'] += 1
        
    return sort_homework


def update_DB_sort_course_homework(course_key):
    """
    Recalculate sort course homework data and update SQL table
    """
            
    sort_homework = sort_course_homework(course_key)
    
    #### Weight sections ####
    ws_sql = SortGrades.objects.filter(course_id=course_key, sort_type='WS')
    # Delete old data
    if ws_sql.count() > 0:
        for entry in ws_sql:
            exists = False
            for subsection in sort_homework['weight_subsections']:
                if subsection['category'] == entry.label:
                    exists = True
                    break 
            if not exists:
                # Delete old entry
                entry.delete()
                
    # Add data
    for subsection in sort_homework['weight_subsections']:
        ws_sql_filtered = ws_sql.filter(label=subsection['category'])
        if (ws_sql.count() == 0 or 
            ws_sql_filtered.count() == 0):
            # Create entry
            SortGrades.objects.create(course_id=course_key,
                                      sort_type='WS',
                                      label=subsection['category'],
                                      category=subsection['category'],
                                      name=subsection['category'],
                                      num_not=subsection['NOT'],
                                      num_fail=subsection['FAIL'],
                                      num_pass=subsection['OK'],
                                      num_prof=subsection['PROFICIENCY']
                                      )
        else:
            # Update entry
            ws_sql_filtered.update(sort_type='WS',
                                   label=subsection['category'],
                                   category=subsection['category'],
                                   name=subsection['category'],
                                   num_not=subsection['NOT'],
                                   num_fail=subsection['FAIL'],
                                   num_pass=subsection['OK'],
                                   num_prof=subsection['PROFICIENCY'])

    
    #### Graded sections ####
    gs_sql = SortGrades.objects.filter(course_id=course_key, sort_type='GS')
    # Delete old data
    if gs_sql.count() > 0:
        for entry in gs_sql:
            exists = False
            for section in sort_homework['graded_sections']:
                if section['label'] == entry.label:
                    exists = True
                    break 
            if not exists:
                # Delete old entry
                entry.delete()
                
    # Add data
    for section in sort_homework['graded_sections']:
        gs_sql_filtered = gs_sql.filter(label=section['label'])
        if (gs_sql.count() == 0 or 
            gs_sql_filtered.count() == 0):
            # Create entry
            SortGrades.objects.create(course_id=course_key,
                                      sort_type='GS',
                                      label=section['label'],
                                      category=section['category'],
                                      name=section['name'],
                                      num_not=section['NOT'],
                                      num_fail=section['FAIL'],
                                      num_pass=section['OK'],
                                      num_prof=section['PROFICIENCY'])
        else:
            # Update entry
            gs_sql_filtered.update(sort_type='GS',
                                   label=section['label'],
                                   category=section['category'],
                                   name=section['name'],
                                   num_not=section['NOT'],
                                   num_fail=section['FAIL'],
                                   num_pass=section['OK'],
                                   num_prof=section['PROFICIENCY'])
    

def get_DB_sort_course_homework(course_key):
    """
    Returns sort_course_homework from database
    """
    
    ws_sql = SortGrades.objects.filter(course_id=course_key, sort_type='WS')
    gs_sql = SortGrades.objects.filter(course_id=course_key, sort_type='GS')
    
    sort_homework = {'graded_sections':[],
                     'weight_subsections':[]}
    # Weighted subsections
    for entry in ws_sql:
        sort_homework['weight_subsections'].append({'category': entry.category, 'NOT': entry.num_not,
                                                    'FAIL': entry.num_fail,
                                                    'OK': entry.num_pass,
                                                    'PROFICIENCY': entry.num_prof})
    
    # Graded sections
    for entry in gs_sql:
        print 'GS_SQL'
        print entry.category
        print entry.num_fail,entry.num_pass,entry.num_prof
        sort_homework['graded_sections'].append({'category': entry.category, 'label': entry.label,
                                                 'name': entry.name, 'NOT': entry.num_not,
                                                 'FAIL': entry.num_fail,
                                                 'OK': entry.num_pass,
                                                 'PROFICIENCY': entry.num_prof})
        
    return sort_homework
        
        
###################################################################
############### STUDENTS GRADES VISUALIZATION #####################
###################################################################


def get_student_grades(course_key, student, full_gc=None, sort_homework=None, weight_data=None):
    """
    Get student grades for given student and course
    """
    
    if full_gc is None:
        full_gc = dump_full_grading_context(get_course_module(course_key))
        
    if (sort_homework is None or weight_data is None):
        sort_homework, weight_data = get_student_grades_course_struct(full_gc)

    # Sort each homework into its category
    i = 0
    for section in full_gc['graded_sections']:
        if section['released']:
            total_grade = 0
            done = False
            for problem in section['problems']:
                grade = get_problem_score(course_key, student, problem)[0]  # Get only grade
                if grade is not None:
                    total_grade += grade
                    done = True
                 
            if done:
                # Add grade to weight subsection
                if weight_data[section['category']]['score'] is None:
                    weight_data[section['category']]['score'] = total_grade
                else:
                    weight_data[section['category']]['score'] += total_grade
                         
                sort_homework['graded_sections'][i]['score'] = total_grade
            else:
                sort_homework['graded_sections'][i]['done'] = False
            i += 1
             
    # Sort grades for weight subsections
    total_score = 0.0
    total_weight = 0.0
    for subsection in sort_homework['weight_subsections']:
        if weight_data[subsection['category']]['score'] is None:
            subsection['done'] = False
        subsection['total'] = weight_data[subsection['category']]['total']
        subsection['score'] = weight_data[subsection['category']]['score']
        
        if subsection['score'] is not None:
            total_score += (subsection['score'] / subsection['total']) * subsection['weight']
        
        total_weight += subsection['weight']
        # Clean score
        weight_data[subsection['category']]['score'] = None
        
    sort_homework['weight_subsections'].append({'category': 'Total',
                                                'weight': 1,
                                                'total': total_weight,
                                                'score': total_score,
                                                'done': True })
 
    return sort_homework
    
def get_student_grades_course_struct(full_gc):
    """
    Returns course structure to fill in with student grades
    """
    # Fill sort_homework
    sort_homework = {'graded_sections':[],
                     'weight_subsections':[]}
    weight_data = {}
    index = 0
    for subsection in full_gc['weight_subsections']:
        for grad_section in full_gc['graded_sections']:
            if grad_section['released'] and grad_section['category'] == subsection['category']:
                sort_homework['weight_subsections'].append({'category': subsection['category'],
                                                            'weight': subsection['weight'],
                                                            'total': 0.0,
                                                            'score': None,
                                                            'done': True})
                weight_data[subsection['category']] = {'index': index, 'score': None, 'total': 0.0,
                                                       'weight': subsection['weight']}
                index += 1
                break
         
    for section in full_gc['graded_sections']:
        if section['released']:
            sort_homework['graded_sections'].append({'category': section['category'],
                                                     'label': section['label'],
                                                     'name': section['name'],
                                                     'total': section['max_grade'],
                                                     'score': None,
                                                     'done': True })
            # Add total released
            weight_data[section['category']]['total'] += section['max_grade']
     
    return sort_homework, weight_data


def update_DB_student_grades(course_key):
    """
    Update students grades for given course
    """
    # Update student grade
    course = get_course_module(course_key)
    #print course
    students = get_course_students(course_key)
    full_gc = dump_full_grading_context(course)
    sort_homework_std, weight_data_std = get_student_grades_course_struct(full_gc)
    all_std_grades = copy.deepcopy(sort_homework_std)
    all_std_grades['weight_subsections'].append({'category': 'Total',
                                                'weight': 1,
                                                'total': 1.0,
                                                'score': 0.0,
                                                'done': True })
    prof_std_grades = copy.deepcopy(sort_homework_std)
    prof_std_grades['weight_subsections'].append({'category': 'Total',
                                                'weight': 1,
                                                'total': 1.0,
                                                'score': 0.0,
                                                'done': True })
    pass_std_grades = copy.deepcopy(sort_homework_std)
    pass_std_grades['weight_subsections'].append({'category': 'Total',
                                                'weight': 1,
                                                'total': 1.0,
                                                'score': 0.0,
                                                'done': True })
    fail_std_grades = copy.deepcopy(sort_homework_std)
    fail_std_grades['weight_subsections'].append({'category': 'Total',
                                                'weight': 1,
                                                'total': 1.0,
                                                'score': 0.0,
                                                'done': True })
    all_count = 0
    prof_count = 0
    pass_count = 0
    fail_count = 0
    
    pass_limit = get_course_grade_cutoff(course)
    proficiency_limit = (1 - pass_limit) / 2 + pass_limit
    
    total_aux = 0.0
    
    for student in students:
        std_grades = get_student_grades(course_key, student, full_gc,
                                        copy.deepcopy(sort_homework_std),
                                        copy.deepcopy(weight_data_std))
        
        total_aux = std_grades['weight_subsections'][-1]['total']
        
        # get grade group
        total_grade = std_grades['weight_subsections'][-1]['score']/std_grades['weight_subsections'][-1]['total']
        if total_grade >= proficiency_limit:
            grade_type = 'PROF'
        elif total_grade >= pass_limit:
            grade_type = 'OK'
        else:
            grade_type = 'FAIL'
            
        exists = StudentGrades.objects.filter(course_id=course_key, student_id=student.id)
        if exists.count() > 0:
            exists.update(grades=std_grades, grade_group=grade_type, last_calc=timezone.now())
        else:
            StudentGrades.objects.create(course_id=course_key,
                                         student_id=student.id,
                                         grades=std_grades,
                                         grade_group=grade_type)
        
        # Add grade to groups
        # All
        all_std_grades = add_students_grades(all_std_grades, std_grades)
        all_count += 1
        # Group
        if grade_type == 'PROF':
            prof_std_grades = add_students_grades(prof_std_grades, std_grades)
            prof_count += 1
        elif grade_type == 'OK':
            pass_std_grades = add_students_grades(pass_std_grades, std_grades)
            pass_count += 1
        else:
            fail_std_grades = add_students_grades(fail_std_grades, std_grades)
            fail_count += 1
    
    all_std_grades['weight_subsections'][-1]['total'] = total_aux
    prof_std_grades['weight_subsections'][-1]['total'] = total_aux
    pass_std_grades['weight_subsections'][-1]['total'] = total_aux
    fail_std_grades['weight_subsections'][-1]['total'] = total_aux
    
    # Process mean grade
    all_std_grades = mean_student_grades(all_std_grades, all_count)
    prof_std_grades = mean_student_grades(prof_std_grades, prof_count)
    pass_std_grades = mean_student_grades(pass_std_grades, pass_count)
    fail_std_grades = mean_student_grades(fail_std_grades, fail_count)
    
    # Get all grade_type
    percent = all_std_grades['weight_subsections'][-1]['score']/all_std_grades['weight_subsections'][-1]['total']
    if percent >= proficiency_limit:
        all_grade_type = 'PROF'
    elif percent >= pass_limit:
        all_grade_type = 'OK'
    else:
        all_grade_type = 'FAIL'
    
    # Add groups to DB
    # All
    exists = StudentGrades.objects.filter(course_id=course_key, student_id=StudentGrades.ALL_STUDENTS)
    if exists.count() > 0:
        exists.update(grades=all_std_grades, grade_group=all_grade_type, last_calc=timezone.now())
    else:
        StudentGrades.objects.create(course_id=course_key,
                                     student_id=StudentGrades.ALL_STUDENTS,
                                     grades=all_std_grades,
                                     grade_group=all_grade_type)
    # Proficiency
    exists = StudentGrades.objects.filter(course_id=course_key, student_id=StudentGrades.PROF_GROUP)
    if exists.count() > 0:
        exists.update(grades=prof_std_grades, grade_group='PROF', last_calc=timezone.now())
    else:
        StudentGrades.objects.create(course_id=course_key,
                                     student_id=StudentGrades.PROF_GROUP,
                                     grades=prof_std_grades,
                                     grade_group='PROF')
    # Pass
    exists = StudentGrades.objects.filter(course_id=course_key, student_id=StudentGrades.PASS_GROUP)
    if exists.count() > 0:
        exists.update(grades=pass_std_grades, grade_group='OK', last_calc=timezone.now())
    else:
        StudentGrades.objects.create(course_id=course_key,
                                     student_id=StudentGrades.PASS_GROUP,
                                     grades=pass_std_grades,
                                     grade_group='OK')
    # Fail
    exists = StudentGrades.objects.filter(course_id=course_key, student_id=StudentGrades.FAIL_GROUP)
    if exists.count() > 0:
        exists.update(grades=fail_std_grades, grade_group='FAIL', last_calc=timezone.now())
    else:
        StudentGrades.objects.create(course_id=course_key,
                                     student_id=StudentGrades.FAIL_GROUP,
                                     grades=fail_std_grades,
                                     grade_group='FAIL')
        
            
def add_students_grades(original, new):
    """
    Add grades from 2 different students
    """
    for i in range(len(original['graded_sections'])):
        if new['graded_sections'][i]['score'] is not None:
            if original['graded_sections'][i]['score'] is None:
                original['graded_sections'][i]['score'] = new['graded_sections'][i]['score']
            else:
                original['graded_sections'][i]['score'] += new['graded_sections'][i]['score']
    
    for j in range(len(original['weight_subsections'])):
        if original['weight_subsections'][j]['total'] == 0:
            original['weight_subsections'][j]['total'] = new['weight_subsections'][j]['total']
            
        if new['weight_subsections'][j]['score'] is not None:
            if original['weight_subsections'][j]['score'] is None:
                original['weight_subsections'][j]['score'] = new['weight_subsections'][j]['score']
            else:
                original['weight_subsections'][j]['score'] += new['weight_subsections'][j]['score']
    
    return original


def mean_student_grades(std_grade, number):
    """
    Calculate mean grade for a structure with grades of different students
    """
    if number > 1:
        for section in std_grade['graded_sections']:
            if section['score'] is not None:
                section['score'] = section['score'] / number
        
        for section in std_grade['weight_subsections']:
            if section['score'] is not None:
                section['score'] = section['score'] / number
        
    return std_grade


def get_DB_student_grades(course_key, student_id=None):
    """
    Return students grades from database
    course_key: course id key
    student: if None, function will return all students
    """
    
    # Students grades
    students_grades = {}
    if student_id is None:
        sql_grades = StudentGrades.objects.filter(course_id=course_key)
    else:
        sql_grades = StudentGrades.objects.filter(course_id=course_key, student_id=student_id)
        
    for std_grade in sql_grades:
        students_grades[std_grade.student_id] = ast.literal_eval(std_grade.grades)
        
    return students_grades 


###################################################################     
################### TIME SPENT VISUALIZATION ######################
###################################################################


def create_time_chapters(course_key):
    """
    Creates an array of chapters with times for each one
    """
    
    time_chapters = {}
    
    chapters = CourseStruct.objects.filter(course_id=course_key, section_type='chapter')
    
    for chapter in chapters:
        chapter_elem = {'time_spent': 0,
                        'sequentials': {}}
        sequentials = CourseStruct.objects.filter(course_id=course_key, section_type='sequential', father=chapter)
        for seq in sequentials:
            chapter_elem['sequentials'][seq.id] = {'time_spent': 0}
        time_chapters[chapter.id] = chapter_elem
   
    return time_chapters

### Codigo Javier Orcoyen
def get_student_spent_time(course_key, student, time_chapters=None, course_blocks=None):
    """
    Add student spent time in course in each chapter to a given
    dictionary with times for each section.
    
    course_key: Course opaque key
    student_id: Student ID
    time_chapters: Array with times for each section to fill. If argument
                   not given, create a new array
    course_blocks: Dictionary with all course xblocks ids. If argument not
                   given, create a new dictionary
    """
    
    # Create time chapters & course_blocks if not given
    if time_chapters is None:
        time_chapters = create_time_chapters(course_key)
    if course_blocks is None:
        course_blocks = get_course_blocks(get_course_module(course_key))
    
    # Get events
    time_data = {'current_chapter': None, 'current_seq': None,
                 'initial_time': None, 'last_time': None}
 
    events = get_new_events_sql(course_key, student, 'courseTime')
    #print 'EVENTS'
    #print events
    """for event in events:        
        print ("Event: " + str(i))
        print event
        i += 1 """
    if events != None:
        #print 'HAY EVENTOS'
        for event in events:
            if event.event_source == 'server':
                #print 'server'
                time_data, time_chapters = manage_server_event(time_data, time_chapters, event, course_blocks)
            elif event.event_source == 'browser':
                #print 'browser'
                time_data, time_chapters = manage_browser_event(time_data, time_chapters, event)   
            
        # Close in case user is still browsing
        time_data, time_chapters = activity_close(time_chapters,
                                              time_data,
                                              timezone.now())
    else:
        time_chapters = None

    return time_chapters


def manage_browser_event(time_data, time_chapters, event):
    # Get event location
    #print 'BROWSER'
    #print event.page
    course_key, chapt_key, seq_key = get_locations_from_url(event.page)
    if event.event_type == 'page_close':
        if (time_data['current_chapter'] != None and 
            time_data['current_chapter'] == chapt_key and 
            time_data['current_seq'] == seq_key):
            # Close activity
            time_data, time_chapters = activity_close(time_chapters, time_data, event.dtcreated)
    else:      
        if time_data['current_chapter'] == None:
            # Start activity
            time_data['current_chapter'] = chapt_key
            time_data['current_seq'] = seq_key
            time_data['initial_time'] = event.dtcreated
            time_data['last_time'] = event.dtcreated
        else:
            if (time_data['current_chapter'] == chapt_key and
                time_data['current_seq'] == seq_key):
                # Same sequence and chapter -> Update activity
                time_data, time_chapters = activity_update(time_chapters,
                                                           time_data,
                                                           event.dtcreated)
            else:
                # Sequence changed -> Close activity with new seq
                time_data, time_chapters = activity_close(time_chapters,
                                                          time_data,
                                                          event.dtcreated,
                                                          chapt_key, seq_key)
                
    return  (time_data, time_chapters)


def manage_server_event(time_data, time_chapters, event, course_blocks=None):
    # Get event location
    #print 'eventType'
    #print event.event_type
    course_key, chapt_key, seq_key = get_locations_from_url(event.event_type, course_blocks)
    #print '2) CLAVES(manage_server_event)'
    #print course_key, chapt_key, seq_key
    if ((course_key == None) or
        (chapt_key == None and 
        seq_key == None)):
        # logout / dashboard / load courseware,info, xblock etc -> Close activity
        if time_data['current_chapter'] != None:
            # Close activity
            #print '3) Close Activity'
            #print time_data['current_chapter']
            #print event.dtcreated
            time_data, time_chapters = activity_close(time_chapters, time_data, event.dtcreated)
    else:
        if time_data['current_chapter'] == None:
            # Start activity
            time_data['current_chapter'] = chapt_key
            time_data['current_seq'] = seq_key
            time_data['initial_time'] = event.dtcreated
            time_data['last_time'] = event.dtcreated
        else:
            if (time_data['current_chapter'] == chapt_key and 
                time_data['current_seq'] == seq_key):
                # Same chapter and seq -> Update activity
                time_data, time_chapters = activity_update(time_chapters,
                                                           time_data,
                                                           event.dtcreated)
            else:
                # Sequential or chapter close -> Close activity with new chapter
                time_data, time_chapters = activity_close(time_chapters,
                                                          time_data,
                                                          event.dtcreated,
                                                          chapt_key,
                                                          seq_key)
           
    return (time_data, time_chapters)
    

def activity_close(time_chapters, time_data, current_time, new_chapter=None, new_seq=None):
    # If activity already closed
    #print 'time data'
    #print time_data['last_time']
    #print time_data['initial_time']
    #print time_data['current_chapter']
    if (time_data['last_time'] is None or
        time_data['initial_time'] is None or
        time_data['current_chapter'] is None):
        #print 'Activity close EXCEPTION'
        return (time_data, time_chapters)
    
    # Add activity time
    time = time_data['last_time'] - time_data['initial_time']
    elapsed_time = current_time - time_data['last_time']
    #print '4) Times'
    #print time
    #print time_data['last_time']
    #print '5) Elapsed_time'
    #print current_time
    #print elapsed_time
    if (elapsed_time.days != 0 or 
        elapsed_time.seconds > INACTIVITY_TIME):
        elapsed_time = timedelta(seconds=INACTIVITY_TIME)
        
    time_chapters = add_course_time(time_data['current_chapter'],
                                    time_data['current_seq'],
                                    time + elapsed_time, time_chapters)
    
    if new_seq == None and new_chapter == None:
        # Stop activity
        time_data['current_chapter'] = None
        time_data['current_seq'] = None
        time_data['initial_time'] = None
        time_data['last_time'] = None
    else:
        time_data['current_chapter'] = new_chapter
        time_data['current_seq'] = new_seq
        time_data['initial_time'] = current_time
        time_data['last_time'] = current_time
    
    return (time_data, time_chapters)


def activity_update(time_chapters, time_data, current_time):
    # If activity is closed
    if (time_data['last_time'] is None or
        time_data['initial_time'] is None or
        time_data['current_chapter'] is None):
        return (time_data, time_chapters)
    
    # Update activity
    elapsed_time = current_time - time_data['last_time']
    #print 'UPDATE'
    #print elapsed_time
    if (elapsed_time.days != 0 or 
        elapsed_time.seconds > INACTIVITY_TIME):
        # Inactivity
        time = time_data['last_time'] - time_data['initial_time']
        time = time + timedelta(seconds=INACTIVITY_TIME)  # Add inactivity time
        time_chapters = add_course_time(time_data['current_chapter'],
                                        time_data['current_seq'],
                                        time, time_chapters)
        time_data['initial_time'] = current_time
        time_data['last_time'] = current_time
    else:
        # Update activity
        time_data['last_time'] = current_time  
            
    return (time_data, time_chapters)
    
    
def add_course_time(chapter_key, sequential_key, time, time_chapters):
    time_spent = time.seconds + time.days * 3600 * 24
    #print 'Spent_time'
    #print time_spent
    for chapter_id in time_chapters.keys():
        if (CourseStruct.objects.filter(pk=chapter_id)[0] != None and
            compare_locations(CourseStruct.objects.filter(pk=chapter_id)[0].module_state_key, chapter_key)):
            # Add chapter time
            time_chapters[chapter_id]['time_spent'] = time_chapters[chapter_id]['time_spent'] + time_spent
            if sequential_key != None:
                for sequential_id in time_chapters[chapter_id]['sequentials'].keys():
                    if (CourseStruct.objects.filter(pk=sequential_id)[0] != None and
                        compare_locations(CourseStruct.objects.filter(pk=sequential_id)[0].module_state_key, sequential_key)):
                        # Add sequential time
                        (time_chapters[chapter_id]['sequentials'][sequential_id]['time_spent']) = (time_chapters[chapter_id]['sequentials'][sequential_id]['time_spent'] + time_spent)
    return time_chapters


def add_time_chapter_time(original, new):
    """
    Add time in chapter_time new to chapter_time original
    """
    #Codigo J Antonio Gascon
    if original.keys() != new.keys():
        # # TODO exception
        return
    for ch_id in original.keys():
        #print 'CH_ID'
        #print ch_id
        original[ch_id]['time_spent'] = original[ch_id]['time_spent'] + new[ch_id]['time_spent']
        print 'ORIGINAL Y EL NEW'
        print original[ch_id]['time_spent'],new[ch_id]['time_spent']
        #print original[ch_id]['sequentials'].keys()
        #print new[ch_id]['sequentials'].keys()
        if original[ch_id]['sequentials'].keys() != new[ch_id]['sequentials'].keys():
            # # TODO exception
            #print 'EXCEPTION'
            #return
            new= str(new)
            new = ast.literal_eval(new)
        #print 'Siguen for'
        for seq_id in original[ch_id]['sequentials'].keys():
            original[ch_id]['sequentials'][seq_id]['time_spent'] = (original[ch_id]['sequentials'][seq_id]['time_spent'] + 
                                                                    new[ch_id]['sequentials'][seq_id]['time_spent'])
            #print 'ORIGINAL Y EL NEW'
            #print original[ch_id]['sequentials'][seq_id]['time_spent'],new[ch_id]['sequentials'][seq_id]['time_spent']
    return original

### Codigo Javier Orcoyen
def update_DB_course_spent_time(course_key):
    """
    Recalculate course spent time and update data in database
    """
    
    newEvents = 0
    prof = 0
    ok = 0
    fail = 0

    time_chapters = create_time_chapters(course_key)
    # Student groups time chapters
    time_chapters_all = copy.deepcopy(time_chapters)
    time_chapters_prof = copy.deepcopy(time_chapters)
    time_chapters_ok = copy.deepcopy(time_chapters)
    time_chapters_fail = copy.deepcopy(time_chapters)
    
    students = get_course_students(course_key)
    
    course_blocks = get_course_blocks(get_course_module(course_key))
    
    # Add students time chapters to database
    for student in students:
        time_chapters_student = copy.deepcopy(time_chapters)
        #Dictionary with the new times
        #print 'GET_student'
        time_chapters_student = get_student_spent_time(course_key,
                                                       student,
                                                       time_chapters_student,
                                                       course_blocks)
        #If there are new times 
        print 'Student'
        print student
        #print 'time_chapters_student tiene algo'
        #print time_chapters_student
        if time_chapters_student != None:
            newEvents = 1

            # Update database
            try:
                #Using get beceause there will only be one entry for each student and each course
                filtered_coursetime = CourseTime.objects.get(course_id=course_key, student_id=student.id)
            except ObjectDoesNotExist:
                filtered_coursetime = None

            #Check for existing entry
            if (filtered_coursetime == None):
                # Create entry
                CourseTime.objects.create(student_id=student.id, course_id=course_key,
                                      time_spent=time_chapters_student)
            else:
                #Get the stored times
                #print 'time filter'
                #print filtered_coursetime.time_spent
                original_coursetime = ast.literal_eval(filtered_coursetime.time_spent)
                #d=original_coursetime[67]['sequentials'][76]
                #original_coursetime[67]['sequentials'].pop(76)
                #original_coursetime[67]['sequentials'].update(d)
                #original_coursetime[67]['sequentials'][76]=original_coursetime[67]['sequentials'][77]
                #original_coursetime[67]['sequentials'][76]=original_coursetime[67]['sequentials'].pop(77)
                #print original_coursetime[67]['sequentials'][76]
                print 'OriginalTImes'
                print original_coursetime
                #print d
                #print 'CHapters time'
                #time_chapters_student= str(time_chapters_student)
                #time_chapters_student = compile(time_chapters_student, '<AST>', 'eval')
                #time_chapters_student = eval(time_chapters_student, dict(Decimal=decimal.Decimal))
                #time_chapters_student = ast.literal_eval(time_chapters_student)
                #json_acceptable_string = str(time_chapters_student).replace("'", "\"")
                #print json_acceptable_string
                #Sustituir "" por ''
                #time_chapters_student = json.loads(json_acceptable_string)
                #print time_chapters_student
                #time_chapters_student = ast.literal_eval(time_chapters_student)
                #print type(original_coursetime)
                #print type(time_chapters_student)
                #Add the new times to the stored ones
                total_coursetime = add_time_chapter_time(original_coursetime, time_chapters_student)
                #print 'TotalCOurse'
                #print total_coursetime
                # Update entry
                filtered_coursetime.time_spent = total_coursetime
                filtered_coursetime.last_calc = timezone.now()
                filtered_coursetime.save()
            
            # Add student time to his groups
            time_chapters_all = add_time_chapter_time(time_chapters_all, time_chapters_student)
            filtered_studentgrades = StudentGrades.objects.filter(course_id=course_key, student_id=student.id)
            if filtered_studentgrades.count() > 0:
                grade_group = filtered_studentgrades[0].grade_group
                if grade_group == 'PROF':
                    prof = 1
                    time_chapters_prof = add_time_chapter_time(time_chapters_prof, time_chapters_student)
                elif grade_group == 'OK':
                    ok = 1
                    time_chapters_ok = add_time_chapter_time(time_chapters_ok, time_chapters_student)
                elif grade_group == 'FAIL':
                    fail = 1
                    time_chapters_fail = add_time_chapter_time(time_chapters_fail, time_chapters_student)
    
    # If there have been new events, add group all time chapters to database
    if newEvents == 1:
        print 'newEvents'
        # Update database
        try:
            #Using get beceause there will only be one entry for all students of a curse
            coursetime_filter_all = CourseTime.objects.get(course_id=course_key, student_id=CourseTime.ALL_STUDENTS)
        except ObjectDoesNotExist:
            coursetime_filter_all = None

        #Check for existing entry
        if (coursetime_filter_all == None):
            # Create entry
            CourseTime.objects.create(student_id=CourseTime.ALL_STUDENTS, course_id=course_key, 
                                  time_spent=time_chapters_all)
        else:
            #Get the stored times
            original_all_times = ast.literal_eval(coursetime_filter_all.time_spent)
            
            #Add the new times to the stored ones
            total_all_course_times = add_time_chapter_time(original_all_times, time_chapters_all)
            # Update entry
            coursetime_filter_all.time_spent = total_all_course_times
            coursetime_filter_all.last_calc = timezone.now()
            coursetime_filter_all.save()
    
        if prof == 1:
            print 'prof'
            # Add group prof time chapters to database
            try:
                #Using get beceause there will only be one entry for all students of a curse graded with PROF
                coursetime_filter_prof = CourseTime.objects.get(course_id=course_key, student_id=CourseTime.PROF_GROUP)
            except ObjectDoesNotExist:
                coursetime_filter_prof = None

            #Check for existing entry
            if (coursetime_filter_prof == None):
                # Create entry
                CourseTime.objects.create(student_id=CourseTime.PROF_GROUP,course_id=course_key, 
                                  time_spent=time_chapters_prof)
            else:
                #Get the stored times
                original_prof_times = ast.literal_eval(coursetime_filter_prof.time_spent)
                #Add the new times to the stored ones
                total_prof_course_times = add_time_chapter_time(original_prof_times, time_chapters_prof)
                # Update entry
                coursetime_filter_prof.time_spent = total_prof_course_times
                coursetime_filter_prof.last_calc = timezone.now()
                coursetime_filter_prof.save()
    
        if ok == 1:
            print 'ok'
            # Add group ok time chapters to database
            try:
                #Using get beceause there will only be one entry for all students of a curse graded with OK
                coursetime_filter_pass = CourseTime.objects.get(course_id=course_key, student_id=CourseTime.PASS_GROUP)
            except ObjectDoesNotExist:
                coursetime_filter_pass = None

            #Check for existing entry
            if (coursetime_filter_pass == None):
                # Create entry
                CourseTime.objects.create(student_id=CourseTime.PASS_GROUP, course_id=course_key, 
                                  time_spent=time_chapters_ok)
            else:
                #Get the stored times
                original_pass_times = ast.literal_eval(coursetime_filter_pass.time_spent)
                #Add the new times to the stored ones
                total_pass_course_times = add_time_chapter_time(original_pass_times, time_chapters_ok)
                # Update entry
                coursetime_filter_pass.time_spent = total_pass_course_times
                coursetime_filter_pass.last_calc = timezone.now()
                coursetime_filter_pass.save()
    
        if fail == 1:
            print 'fail'
            # Add group fail time chapters to database
            try:
                #Using get beceause there will only be one entry for all students of a curse graded with FAIL
                coursetime_filter_fail = CourseTime.objects.get(course_id=course_key, student_id=CourseTime.FAIL_GROUP)
            except ObjectDoesNotExist:
                coursetime_filter_fail = None

            #Check for existing entry
            if (coursetime_filter_fail == None):
                # Create entry
                CourseTime.objects.create(student_id=CourseTime.FAIL_GROUP, course_id=course_key, 
                                  time_spent=time_chapters_fail)
            else:
                #Get the stored times
                original_fail_times = ast.literal_eval(coursetime_filter_fail.time_spent)
                #Add the new times to the stored ones
                total_fail_course_times = add_time_chapter_time(original_fail_times, time_chapters_fail)
                # Update entry
                coursetime_filter_fail.time_spent = total_fail_course_times
                coursetime_filter_fail.last_calc = timezone.now()
                coursetime_filter_fail.save()


def get_DB_course_spent_time(course_key, student_id=None):
    """
    Return course spent time from database
    
    course_key: course id key
    student_id: if None, function will return all students
    """
    
    # Course struct
    course_struct = get_DB_course_struct(course_key, include_unreleased=False)
    
    # Students time

    students_time = {}
    if student_id is None:
        sql_time = CourseTime.objects.filter(course_id=course_key)
    else:
        sql_time = CourseTime.objects.filter(course_id=course_key, student_id=student_id)

    for std_time in sql_time:
        students_time[std_time.student_id] = ast.literal_eval(std_time.time_spent)
        
    return course_struct, students_time           
              
              
######################################################################
####################### SECTION ACCESSES #############################
######################################################################


def create_access_chapters(course_key):
    """
    Creates an array of chapters with times for each one
    """
    
    access_chapters = {}
    
    chapters = CourseStruct.objects.filter(course_id=course_key, section_type='chapter')
    
    for chapter in chapters:
        chapter_elem = {'accesses': 0,
                        'sequentials': {}}
        sequentials = CourseStruct.objects.filter(course_id=course_key, section_type='sequential', father=chapter)
        for seq in sequentials:
            chapter_elem['sequentials'][seq.id] = {'accesses': 0,
                                                   'verticals': {},
                                                   'last_vert': 1}
            verticals = CourseStruct.objects.filter(course_id=course_key, section_type='vertical', father=seq)
            for vert in verticals:
                chapter_elem['sequentials'][seq.id]['verticals'][vert.id] = {'accesses': 0}
        access_chapters[chapter.id] = chapter_elem
   
    return access_chapters


### Codigo Javier Orcoyen
def get_student_section_accesses(course_key, student, access_chapters=None):
    """
    Fill course structure with accesses to each section for given course and student
    """
    if access_chapters is None:
        access_chapters = create_access_chapters(course_key)
    events = get_new_events_sql(course_key, student, 'courseAccesses') 
    
    if events != None:

        cur_vert = 0
        cur_chapt = None
        cur_seq = None

        for event in events:
            if event.event_source == 'server':
                course, chapt_key, seq_key = get_locations_from_url(event.event_type)
                # Get chapter and seq id
                if chapt_key is not None and CourseStruct.objects.filter(module_state_key=chapt_key).count() > 0:
                    cur_chapt = CourseStruct.objects.filter(module_state_key=chapt_key)[0].id
                    if seq_key is not None and CourseStruct.objects.filter(module_state_key=seq_key, father_id=cur_chapt).count()>0:
                        cur_seq = CourseStruct.objects.filter(module_state_key=seq_key, father_id=cur_chapt)[0].id
                    else:
                        cur_seq = None
                else:
                    cur_chapt = None
                    cur_seq = None
                
                if course is not None and cur_chapt is not None:
                    if cur_seq is not None:
                        cur_vert = access_chapters[cur_chapt]['sequentials'][cur_seq]['last_vert']
                        # Add sequential access
                        access_chapters = add_course_access(access_chapters, cur_chapt, cur_seq, None)
                        # Add 1st vertical access
                        access_chapters = add_course_access(access_chapters, cur_chapt, cur_seq, cur_vert)
                    else:
                        # Add chapter access
                        access_chapters = add_course_access(access_chapters, cur_chapt, None, None)
                        cur_vert = 0
            else:
                if cur_chapt is not None and cur_seq is not None:
                    event_data = ast.literal_eval(event.event)
                    if ((event.event_type == 'seq_prev' or 
                     event.event_type == 'seq_next' or 
                     event.event_type == 'seq_goto') and
                    event_data['old'] != event_data['new']):
                        cur_vert = event_data['new']
                        access_chapters[cur_chapt]['sequentials'][cur_seq]['last_vert'] = cur_vert
                        # Add vertical access
                        access_chapters = add_course_access(access_chapters, cur_chapt, cur_seq, cur_vert)

    else:
        access_chapters = None

    return access_chapters


def add_student_accesses(original, new):
    """
    Add time in chapter_time new to chapter_time original
    """
    if original.keys() != new.keys():
        ## TODO exception
        return
    
    for ch_id in original.keys():
        original[ch_id]['accesses'] += new[ch_id]['accesses']
        if original[ch_id]['sequentials'].keys() != new[ch_id]['sequentials'].keys():
            new= str(new)
            new = ast.literal_eval(new)
            ## TODO exception
            #return
        for seq_id in original[ch_id]['sequentials'].keys():
            original[ch_id]['sequentials'][seq_id]['accesses'] += new[ch_id]['sequentials'][seq_id]['accesses']
            if original[ch_id]['sequentials'][seq_id]['verticals'].keys() != new[ch_id]['sequentials'][seq_id]['verticals'].keys():
                ## TODO exception
                return
            for vert_id in original[ch_id]['sequentials'][seq_id]['verticals'].keys():
                original[ch_id]['sequentials'][seq_id]['verticals'][vert_id]['accesses'] += new[ch_id]['sequentials'][seq_id]['verticals'][vert_id]['accesses']

    return original


def add_course_access(access_chapters, chapt_id, seq_id=None, vert_pos=None):
    """
    Add access to course section
    """
    if seq_id is None:
        # Chapter access
        access_chapters[chapt_id]['accesses'] += 1
    else:
        if vert_pos is None:
            # Sequential access
            access_chapters[chapt_id]['sequentials'][seq_id]['accesses'] += 1
            # Chapter access
            access_chapters[chapt_id]['accesses'] += 1
        else:
            # Vertical access
            if CourseStruct.objects.filter(father_id=seq_id, index=vert_pos).count() > 0:
                vert_id = CourseStruct.objects.filter(father_id=seq_id, index=vert_pos)[0].id
                access_chapters[chapt_id]['sequentials'][seq_id]['verticals'][vert_id]['accesses'] += 1
                        
    return access_chapters


def update_DB_course_section_accesses(course_key):
    """
    Recalculate course section accesses and update data in database
    """
    
    newEvents = 0
    prof = 0
    ok = 0
    fail = 0

    course_accesses = create_access_chapters(course_key)
    # Student groups time chapters
    course_accesses_all = copy.deepcopy(course_accesses)
    course_accesses_prof = copy.deepcopy(course_accesses)
    course_accesses_ok = copy.deepcopy(course_accesses)
    course_accesses_fail = copy.deepcopy(course_accesses)
    
    students = get_course_students(course_key)
    
    # Add students time chapters to database
    for student in students:
        course_accesses_student = copy.deepcopy(course_accesses)
        #Dictionary with the new accesses
        course_accesses_student = get_student_section_accesses(course_key,
                                                               student,
                                                               course_accesses_student)
        #If there are new accesses
        if course_accesses_student != None:
            
            newEvents = 1

            # Update database
            try:
                #Using get beceause there will only be one entry for each student and each course
                courseaccesses_filtered = CourseAccesses.objects.get(course_id=course_key, student_id=student.id)
            except ObjectDoesNotExist:
                courseaccesses_filtered = None
            
            #Check for existing entry
            if (courseaccesses_filtered == None):
                # Create entry
                CourseAccesses.objects.create(student_id=student.id, course_id=course_key,
                                          accesses=course_accesses_student)
            else:
                #Get the stored accesses
                original_accesses = ast.literal_eval(courseaccesses_filtered.accesses)
                #Add the new accesses to the stored ones
                total_course_accesses = add_student_accesses(original_accesses, course_accesses_student)
                #print 'Total_course_accesses'
                #print total_course_accesses
                # Update entry
                courseaccesses_filtered.accesses = total_course_accesses
                courseaccesses_filtered.last_calc = timezone.now()
                courseaccesses_filtered.save()
        
            # Add student time to his groups
            course_accesses_all = add_student_accesses(course_accesses_all, course_accesses_student)
            studentgrades_filtered = StudentGrades.objects.filter(course_id=course_key, student_id=student.id)
            if studentgrades_filtered.count() > 0:
                grade_group = studentgrades_filtered[0].grade_group
                if grade_group == 'PROF':
                    prof = 1
                    course_accesses_prof = add_student_accesses(course_accesses_prof, course_accesses_student)
                elif grade_group == 'OK':
                    ok = 1
                    course_accesses_ok = add_student_accesses(course_accesses_ok, course_accesses_student)
                elif grade_group == 'FAIL':
                    fail = 1
                    course_accesses_fail = add_student_accesses(course_accesses_fail, course_accesses_student)
    
    # If there have been new events, add group accesses to database
    if newEvents == 1:

        # Update database
        try:
            #Using get beceause there will only be one entry for all students of a curse
            courseaccesses_filter_all = CourseAccesses.objects.get(course_id=course_key, 
                                                            student_id=CourseAccesses.ALL_STUDENTS)
        except ObjectDoesNotExist:
            courseaccesses_filter_all = None
            
        #Check for existing entry
        if (courseaccesses_filter_all == None):
            # Create entry
            CourseAccesses.objects.create(student_id=CourseAccesses.ALL_STUDENTS, course_id=course_key,
                                      accesses=course_accesses_all)
        else:
            #Get the stored accesses
            original_all_accesses = ast.literal_eval(courseaccesses_filter_all.accesses)
            #Add the new accesses to the stored ones
            total_all_course_accesses = add_student_accesses(original_all_accesses, course_accesses_all)
            # Update entry
            courseaccesses_filter_all.accesses = total_all_course_accesses
            courseaccesses_filter_all.last_calc = timezone.now()
            courseaccesses_filter_all.save()
    
        if prof == 1:
            # Add group prof time chapters to database
            try:
                #Using get beceause there will only be one entry for all students of a curse graded with PROF
                courseaccesses_filter_prof = CourseAccesses.objects.get(course_id=course_key, 
                                                             student_id=CourseAccesses.PROF_GROUP)
            except ObjectDoesNotExist:
                courseaccesses_filter_prof = None
            
            #Check for existing entry
            if (courseaccesses_filter_prof == None):
                # Create entry
                CourseAccesses.objects.create(student_id=CourseAccesses.PROF_GROUP, course_id=course_key,
                                      accesses=course_accesses_prof)
            else:
                #Get the stored accesses
                original_prof_accesses = ast.literal_eval(courseaccesses_filter_prof.accesses)
                #Add the new accesses to the stored ones
                total_prof_course_accesses = add_student_accesses(original_prof_accesses, course_accesses_prof)
                # Update entry
                courseaccesses_filter_prof.accesses = total_prof_course_accesses
                courseaccesses_filter_prof.last_calc = timezone.now()
                courseaccesses_filter_prof.save()
    
        if ok == 1:
            # Add group pass time chapters to database
            try:
                #Using get beceause there will only be one entry for all students of a curse graded with OK
                courseaccesses_filter_pass = CourseAccesses.objects.get(course_id=course_key, 
                                                             student_id=CourseAccesses.PASS_GROUP)
            except ObjectDoesNotExist:
                courseaccesses_filter_pass = None
            
            #Check for existing entry 
            if (courseaccesses_filter_pass == None):
                # Create entry
                CourseAccesses.objects.create(student_id=CourseAccesses.PASS_GROUP, course_id=course_key,
                                      accesses=course_accesses_ok)
            else:
                #Get the stored accesses
                original_pass_accesses = ast.literal_eval(courseaccesses_filter_pass.accesses)
                #Add the new accesses to the stored ones
                total_pass_course_accesses = add_student_accesses(original_pass_accesses, course_accesses_ok)
                # Update entry
                courseaccesses_filter_pass.accesses = total_pass_course_accesses
                courseaccesses_filter_pass.last_calc = timezone.now()
                courseaccesses_filter_pass.save()
    
        if fail == 1:
            # Add group fail time chapters to database
            try:
                #Using get beceause there will only be one entry for all students of a curse graded with FAIL
                courseaccesses_filter_fail = CourseAccesses.objects.get(course_id=course_key, 
                                                             student_id=CourseAccesses.FAIL_GROUP)
            except ObjectDoesNotExist:
                courseaccesses_filter_fail = None
            
            #Check for existing entry   
            if (courseaccesses_filter_fail == None):
                # Create entry
                CourseAccesses.objects.create(student_id=CourseAccesses.FAIL_GROUP, course_id=course_key,
                                      accesses=course_accesses_fail)
            else:
                #Get the stored accesses
                original_fail_accesses = ast.literal_eval(courseaccesses_filter_fail.accesses)
                #Add the new accesses to the stored ones
                total_fail_course_accesses = add_student_accesses(original_fail_accesses, course_accesses_fail)
                # Update entry
                courseaccesses_filter_fail.accesses = total_fail_course_accesses
                courseaccesses_filter_fail.last_calc = timezone.now()
                courseaccesses_filter_fail.save()


def get_DB_course_section_accesses(course_key, student_id=None):
    """
    Return course section accesses from database
    
    course_key: course id key
    student_id: if None, function will return all students
    """
    
    # Course struct
    course_struct = get_DB_course_struct(course_key, include_verticals=True, include_unreleased=False)
    # Students time
    students_accesses = {}
    if student_id is None:
        sql_accesses = CourseAccesses.objects.filter(course_id=course_key)
    else:
        sql_accesses = CourseAccesses.objects.filter(course_id=course_key, student_id=student_id)
        
    for std_accesses in sql_accesses:
        students_accesses[std_accesses.student_id] = ast.literal_eval(std_accesses.accesses)
    
    return course_struct, students_accesses
    

######################################################################
####################### PROBLEM PROGRESS #############################
######################################################################


def create_course_progress(course_key):
    """
    Returns course structure and timeline to calculate video and problem
    progress
    """
    course = get_course_module(course_key)
    
    # Get timeline
    timeline = perdelta(course.start, course.end if course.end is not None else timezone.now(), timedelta(days=1))
    # Get course struct
    course_struct = []
    
    full_gc = dump_full_grading_context(course)
    
    index = 0
    for subsection in full_gc['weight_subsections']:
        course_struct.append({'weight': subsection['weight'],
                              'total': 0.0,
                              'score': 0.0,
                              'problems': [] })
        for grad_section in full_gc['graded_sections']:
            if grad_section['released'] and grad_section['category'] == subsection['category']:
                course_struct[index]['total'] += grad_section['max_grade']
                # Add problems ids
                for prob in grad_section['problems']:
                    course_struct[index]['problems'].append(prob.location)
        index += 1
        
    # Delete non released or graded sections
    for section in course_struct:
        if section['total'] == 0:
            course_struct.remove(section)
    
    return course_struct, timeline
    
    
### Codigo Javier Orcoyen
def perdelta(start, end, delta):
    """
    Returns a datatime array starting at start and ending at
    end, with a separation of delta
    """
    timeline = []
    curr = start
    end_loop = end.replace(hour=0, minute=0, second=0, microsecond=0)
    #In case of a one day course
    if start.date() == end.date():
        timeline.append(start)
        timeline.append(end)

    else:

        while curr <= end_loop:

            if curr == start:
                timeline.append(curr)
                curr = curr+timedelta(1)
                curr = curr.replace(hour=0, minute=0, second=0, microsecond=0)
            timeline.append(curr)

            if curr == end_loop and end != end_loop:
                timeline.append(end)
            curr += delta
    return timeline


### Codigo Javier Orcoyen
def get_student_problem_progress(course_key, student, course_struct=None, timeline=None):
    """
    Return problem progress for a given course and student
    """
    if course_struct is None or timeline is None:
        course_struct, timeline = create_course_progress(course_key)
    
    problem_progress = []
    
    events = get_new_events_sql(course_key, student, 'problemProgress')
    if events != None:
        count = 0
        for act_time in timeline:
            # Last date of the course is the end of the loop
            if act_time != timeline[-1]:
                last_time = timeline[count+1]
                count += 1
            filter_events = events.filter(dtcreated__gt = act_time,
                                      dtcreated__lte = last_time)

            # Add grades
            for event in filter_events:
                prob_data = ast.literal_eval(event.event)
                prob_block = course_key.make_usage_key_from_deprecated_string(prob_data['problem_id'])
                for section in course_struct:
                    for prob in section['problems']:
                        
                        if prob == prob_block:
                            if event.event_type == 'problem_check':
                                section['score'] += prob_data['grade']
                            elif event.event_type == 'problem_rescore':
                                section['score'] -= prob_data['orig_score']
                                section['score'] += prob_data['new_score']
                            break
            # Add data
            total = 0.0
            total_weight = 0.0
            for section in course_struct:
                if section['total'] != 0:
                    total += (section['score']/section['total'])*section['weight']
                total_weight += section['weight']

            total = total/total_weight
            total = total*100
            total = int(round(total,0))
            if total > 100:
                total = 100
            problem_progress.append({'score':total, 'time': act_time})
        
    else:
        print 'NO HAY PROGRESO DE PROBLEMAS'
        problem_progress = None
    return problem_progress


def mean_problem_progress_sum(problem_progress, num):
    if num <= 1:
        return problem_progress
    
    for p in problem_progress:
        p['score'] = p['score']/num
        
    return problem_progress 

def add_problem_progress(base, new):
    
    for i in range(len(base)):
        if base[i]['score'] + new[i]['score'] > 100:
            base[i]['score'] = 100
        else:
            base[i]['score'] += new[i]['score']
    return base


def optimize_problem_progress(problem_progress):
    
    time_len = len(problem_progress)
    if time_len == 1:
        return ([problem_progress[0]['score']], problem_progress[0]['time'],
                problem_progress[0]['time'], 0)
    if time_len == 0:
        return ([0], None, None, 0)
    
    # Get start date
    start_index = 0
    
    while (start_index < time_len
           and problem_progress[start_index]['score'] == 0):
        start_index += 1
    
    if start_index == time_len:
        return ([0], None, None, 0)
    
    # Get end date
    last_score = problem_progress[time_len - 1]['score']
    end_index = start_index
    index_found = False
    
    for i in range(start_index,time_len):
        if problem_progress[i]['score'] == last_score:
            if not index_found: 
                end_index = i
                index_found = True
        else:
            end_index = i
            index_found = False
    
    # Get dates
    #start_index = start_index - 1 if (start_index >= 1) else start_index
    end_index = end_index + 1 if (end_index < time_len -1) else end_index
    
    end_date = problem_progress[end_index]['time']
    start_date = problem_progress[start_index]['time']
    
    tdelta =  0 if (start_index == end_index) else (problem_progress[1]['time'] - problem_progress[0]['time'])
    delta = (tdelta.days*60*60*24 + tdelta.seconds) if tdelta is not 0 else 0
    
    # Get progress array
    progress = []
    for i in range(start_index - 1, end_index):
        progress.append(problem_progress[i]['score'])
        
    return progress, start_date, end_date, delta


### Codigo Javier Orcoyen
def progress_to_timelineProgress(timeline, start_date, original_progress, indicator):
    """
    Original progress (list) into progress timeline (dictionary list with 'score' and 'time')
    original_problem_progress is empty at the beggining and then it is filled with data from the original_progress list
    """

    original_timeline_progress = []
    
    for time in timeline:
        if indicator == 'problem':
            original_timeline_progress.append({'score':0, 'time':time})
        elif indicator == 'video':
            original_timeline_progress.append({'percent':0, 'time':time})
        
    index=0
    indexProgress=1

    for time in timeline:
        if time>=start_date:
            if indicator == 'problem':
                original_timeline_progress[index]['score']=original_progress[indexProgress]
            elif indicator == 'video':
                original_timeline_progress[index]['percent']=original_progress[indexProgress]
            indexProgress+=1
            if indexProgress > len(original_progress)-1:
                indexProgress-=1
        index+=1                  

    return original_timeline_progress


### Codigo Javier Orcoyen
def update_DB_course_problem_progress(course_key, course_struct=None, timeline=None):
    """
    Update problem progress in database
    """
    newEvents = 0
    print'Primer IF TIMELINE'
    if course_struct is None or timeline is None:
        course_struct, timeline = create_course_progress(course_key)
    #print 'timeline'
    #print timeline
    print 'FIN PRIMER IF TIMELINE'   
    all_problem_progress = []
    prof_problem_progress = []
    ok_problem_progress = []
    fail_problem_progress = []
    original_problem_progress = []
    original_all_problem_progress = []
    original_prof_problem_progress = []
    original_pass_problem_progress = []
    original_fail_problem_progress = []
    num_all = 0
    num_prof = 0
    num_ok = 0
    num_fail = 0
    prof = 0
    ok = 0
    fail = 0
    
    for time in timeline:
        all_problem_progress.append({'score':0, 'time':time})
        prof_problem_progress.append({'score':0, 'time':time})
        ok_problem_progress.append({'score':0, 'time':time})
        fail_problem_progress.append({'score':0, 'time':time})
        
    students = get_course_students(course_key)
    #print 'students'
    for student in students:
        std_problem_progress = get_student_problem_progress(course_key,
                                                            student,
                                                            copy.deepcopy(course_struct),
                                                            timeline)
       
        #If there are new progresses
        #print 'If there are new progresses'
        #print std_problem_progress
        if std_problem_progress != None:
            
            newEvents = 1
       
            # Add grade to all
            all_problem_progress = add_problem_progress(all_problem_progress, 
                                                    std_problem_progress)
            num_all += 1
            # Add grade to category
            studentgrades_filtered = StudentGrades.objects.filter(course_id=course_key, 
                                                              student_id=student.id)
            if studentgrades_filtered.count() > 0:
                grade_group = studentgrades_filtered[0].grade_group
                if grade_group == 'PROF':
                    prof = 1
                    prof_problem_progress = add_problem_progress(prof_problem_progress,
                                                             std_problem_progress)
                    num_prof += 1
                elif grade_group == 'OK':
                    ok = 1
                    ok_problem_progress = add_problem_progress(ok_problem_progress,
                                                             std_problem_progress)
                    num_ok += 1
                elif grade_group == 'FAIL':
                    fail = 1
                    fail_problem_progress = add_problem_progress(fail_problem_progress,
                                                             std_problem_progress)
                    num_fail += 1
       
            # Update entry
            try:
                #Using get beceause there will only be one entry for each student and each course
                sql_filtered = CourseProbVidProgress.objects.get(course_id=course_key, 
                                                            student_id=student.id, type='PROB')
            except ObjectDoesNotExist:
                sql_filtered = None

            # Create entry
            progress, start_date, end_date, delta = optimize_problem_progress(std_problem_progress)
            if (sql_filtered == None and start_date != None and end_date != None):
                CourseProbVidProgress.objects.create(student_id=student.id,
                                                 course_id=course_key,
                                                 progress=progress,
                                                 type='PROB',
                                                 start_time=start_date,
                                                 end_time=end_date,
                                                 delta=delta)
            else:
                # Check for new events, but no new progress
                if progress == [] or progress == [0]:
                    newEvents = 0

                else:
                    # Get stored progress
                    original_progress = ast.literal_eval(sql_filtered.progress)
                    start_date = sql_filtered.start_time
                
                    # Original progress (list) into progress timeline (dictionary list with 'score' and 'time')
                    original_problem_progress = progress_to_timelineProgress(timeline, start_date, original_progress, 'problem')
 
                    # Add the new progress to the stored one
                    total_progress = add_problem_progress(original_problem_progress, std_problem_progress)

                    progress, start_date, end_date, delta = optimize_problem_progress(total_progress)

                    # Update entry
                    sql_filtered.progress = progress
                    sql_filtered.start_time = start_date
                    sql_filtered.end_time = end_date
                    sql_filtered.delta = delta
                    sql_filtered.last_calc = timezone.now()
                    sql_filtered.save()

        #If there are no new events
        else:

            # Add grade to all, because the mean also takes into account students with 0 progress
            num_all += 1

            # Add grade to category, because the mean also takes into account students with 0 progress
            studentgrades_filtered = StudentGrades.objects.filter(course_id=course_key, 
                                                              student_id=student.id)
            if studentgrades_filtered.count() > 0:
                grade_group = studentgrades_filtered[0].grade_group
                if grade_group == 'PROF':
                    num_prof += 1
                elif grade_group == 'OK':
                    num_ok += 1
                elif grade_group == 'FAIL':
                    num_fail += 1

    # If there have been new events, add group progress to database
    if newEvents == 1:
    
        # New ALL students progress 
        all_problem_progress = mean_problem_progress_sum(all_problem_progress, num_all)
        
        # Update entry
        try:
            #Using get beceause there will only be one entry for each student and each course
            sql_filtered = CourseProbVidProgress.objects.get(course_id=course_key, type='PROB',
                                                        student_id=CourseProbVidProgress.ALL_STUDENTS)
        except ObjectDoesNotExist:
            sql_filtered = None
        
        progress, start_date, end_date, delta = optimize_problem_progress(all_problem_progress)
        #Check for existing entry
        if (sql_filtered == None and start_date != None and end_date != None):
            # Create entry      
            CourseProbVidProgress.objects.create(student_id=CourseProbVidProgress.ALL_STUDENTS,
                                             course_id=course_key, progress=progress,
                                             type='PROB', start_time=start_date,
                                             end_time=end_date, delta=delta)
        elif (progress != [0]):
            # Get stored progress
            original_progress = ast.literal_eval(sql_filtered.progress)
            start_date = sql_filtered.start_time
                
            # New progress (list) into progress timeline (dictionary list with 'score' and 'time')
            original_all_problem_progress = progress_to_timelineProgress(timeline, start_date, original_progress, 'problem')
                
            # Add the new progress to the stored one
            total_progress = add_problem_progress(original_all_problem_progress, all_problem_progress)

            progress, start_date, end_date, delta = optimize_problem_progress(total_progress)

            # Update entry
            sql_filtered.progress = progress
            sql_filtered.start_time = start_date
            sql_filtered.end_time = end_date
            sql_filtered.delta = delta
            sql_filtered.last_calc = timezone.now()
            sql_filtered.save()
           
        if prof == 1:
            # New PROFICIENCY students progress to database
            prof_problem_progress = mean_problem_progress_sum(prof_problem_progress, num_prof)
        
            # Update entry
            try:
                #Using get beceause there will only be one entry for each student and each course
                sql_filtered = CourseProbVidProgress.objects.get(course_id=course_key, type='PROB',
                                                        student_id=CourseProbVidProgress.PROF_GROUP)
            except ObjectDoesNotExist:
                sql_filtered = None

            progress, start_date, end_date, delta = optimize_problem_progress(prof_problem_progress)
            #Check for existing entry
            if (sql_filtered == None and start_date != None and end_date != None):
                # Create entry
                
                CourseProbVidProgress.objects.create(student_id=CourseProbVidProgress.PROF_GROUP,
                                             course_id=course_key, progress=progress,
                                             type='PROB', start_time=start_date,
                                             end_time=end_date, delta=delta)
            elif (progress != [0]):
                # Get stored progress
                original_progress = ast.literal_eval(sql_filtered.progress)
                start_date = sql_filtered.start_time
                
                # New progress (list) into progress timeline (dictionary list with 'score' and 'time')
                original_prof_problem_progress = progress_to_timelineProgress(timeline, start_date, original_progress, 'problem')
                
                # Add the new progress to the stored one
                total_progress = add_problem_progress(original_prof_problem_progress, prof_problem_progress)

                progress, start_date, end_date, delta = optimize_problem_progress(total_progress)

                # Update entry
                sql_filtered.progress = progress
                sql_filtered.start_time = start_date
                sql_filtered.end_time = end_date
                sql_filtered.delta = delta
                sql_filtered.last_calc = timezone.now()
                sql_filtered.save()
    
        if ok == 1:
            # New PASS students progress to database
            ok_problem_progress = mean_problem_progress_sum(ok_problem_progress, num_ok)

            # Update entry
            try:
                #Using get beceause there will only be one entry for each student and each course
                sql_filtered = CourseProbVidProgress.objects.get(course_id=course_key, type='PROB',
                                                        student_id=CourseProbVidProgress.PASS_GROUP)
            except ObjectDoesNotExist:
                sql_filtered = None

            progress, start_date, end_date, delta = optimize_problem_progress(ok_problem_progress)
            #Check for existing entry
            if (sql_filtered == None and start_date != None and end_date != None):
                # Create entry   
                CourseProbVidProgress.objects.create(student_id=CourseProbVidProgress.PASS_GROUP,
                                             course_id=course_key, progress=progress,
                                             type='PROB', start_time=start_date,
                                             end_time=end_date, delta=delta)
            elif (progress != [0]):
                # Get stored progress
                original_progress = ast.literal_eval(sql_filtered.progress)
                start_date = sql_filtered.start_time
                
                # New progress (list) into progress timeline (dictionary list with 'score' and 'time')
                original_pass_problem_progress = progress_to_timelineProgress(timeline, start_date, original_progress, 'problem')
                
                # Add the new progress to the stored one
                total_progress = add_problem_progress(original_pass_problem_progress, ok_problem_progress)

                progress, start_date, end_date, delta = optimize_problem_progress(total_progress)

                # Update entry
                sql_filtered.progress = progress
                sql_filtered.start_time = start_date
                sql_filtered.end_time = end_date
                sql_filtered.delta = delta
                sql_filtered.last_calc = timezone.now()
                sql_filtered.save()

        if fail == 1:
            # New FAIL students progress to database
            fail_problem_progress = mean_problem_progress_sum(fail_problem_progress, num_fail)
        
            # Update entry
            try: 
                #Using get beceause there will only be one entry for each student and each course
                sql_filtered = CourseProbVidProgress.objects.get(course_id=course_key, type='PROB',
                                                        student_id=CourseProbVidProgress.FAIL_GROUP)
            except ObjectDoesNotExist:
                sql_filtered = None

            progress, start_date, end_date, delta = optimize_problem_progress(fail_problem_progress)
            #Check for existing entry
            if (sql_filtered == None and start_date != None and end_date != None):
                # Create entry    
                CourseProbVidProgress.objects.create(student_id=CourseProbVidProgress.FAIL_GROUP,
                                             course_id=course_key, progress=progress,
                                             type='PROB', start_time=start_date,
                                             end_time=end_date, delta=delta)
            elif (progress != [0]):
                # Get stored progress
                original_progress = ast.literal_eval(sql_filtered.progress)
                start_date = sql_filtered.start_time
                
                # New progress (list) into progress timeline (dictionary list with 'score' and 'time')
                original_fail_problem_progress = progress_to_timelineProgress(timeline, start_date, original_progress, 'problem')
                
                # Add the new progress to the stored one
                total_progress = add_problem_progress(original_fail_problem_progress, fail_problem_progress)

                progress, start_date, end_date, delta = optimize_problem_progress(total_progress)
 
                # Update entry
                sql_filtered.progress = progress
                sql_filtered.start_time = start_date
                sql_filtered.end_time = end_date
                sql_filtered.delta = delta
                sql_filtered.last_calc = timezone.now()
                sql_filtered.save()


######################################################################
######################## VIDEO PROGRESS ##############################
######################################################################


### Codigo Javier Orcoyen
def get_student_video_progress(course, student, timeline=None):
    """
    Get video progress for a given course and student
    """
    if timeline is None:
        timeline = create_course_progress(course.location.course_key)[1]
    
    video_progress = []
    
    (video_module_ids, video_durations) = get_info_videos(course)[1:3]
    #print 'get_info_videos'
    #print get_info_videos(course)[1:3]
    events = get_new_events_sql(course.location.course_key, student, 'videoProgress1')
   
    if events is not None:
        first_event = events[0].time
        last_event = events[events.count() - 1].time
        
        last_percent = 0
        last_percent2 = 0

        count = 0

        for act_time in timeline:

            # Last date of the course is the end of the loop
            if act_time != timeline[-1]:
                last_time = timeline[count+1]
                count += 1

            if (first_event is None or
                (act_time < first_event and
                (first_event - act_time).days > 0)):
                video_progress.append({'percent': 0, 
                                   'time': act_time})
            elif (act_time > last_event and
                  act_time.date() != last_event.date()):
                video_progress.append({'percent': last_percent, 
                                   'time': act_time})
            else:
                last_percent2 = last_percent
                last_percent = student_total_video_percent(course, student, video_module_ids, video_durations, last_time)
                if last_percent == 0:
                    last_percent = last_percent2
                if last_percent != last_percent2:
                    last_percent = last_percent+last_percent2
                    if last_percent > 100:
                        last_percent = 100
                video_progress.append({'percent': last_percent, 
                                   'time': act_time})
    else:
        print 'video_progress vacio con events= None'
        print events
        video_progress = None     
    
    return video_progress


def student_total_video_percent(course, user, video_module_ids = None, video_durations = None, last_date = None):
    """
        based in HECTOR's video_consumption 
        Returns video consumption in the form of video names, percentages
        per video seen and total time spent per video for a certain user
    """
    if video_module_ids is None or video_durations is None:
        (video_module_ids, video_durations) = get_info_videos(course)[1:2]
    
    # Non-overlapped video time
    stu_video_seen = []
    # Video length seen based on tracking-log events (best possible measure)
    for video_module_id in video_module_ids:
        [aux_start, aux_end] = video_len_watched_lastdate(course.location.course_key, user, video_module_id, last_date)
        interval_sum = 0
        for start, end in zip(aux_start,aux_end):
            interval_sum += end - start
        stu_video_seen.append(interval_sum)
   
    if sum(stu_video_seen) <= 0:
        return 0
        
    video_percentages = map(truediv, stu_video_seen, video_durations)
    video_percentages = [val*100 for val in video_percentages]
    video_percentages = [int(round(val,0)) for val in video_percentages]
    # Ensure artificially percentages do not surpass 100%, which
    # could happen slightly from the 1s adjustment in id_to_length function
    for i in range(0,len(video_percentages)):
        if video_percentages[i] > 100:
            video_percentages[i] = 100
            
    total_percent = sum(video_percentages)/len(video_percentages)
  
    return total_percent


def mean_video_progress_sum(video_progress, num):
    if num <= 1:
        return video_progress
    
    for p in video_progress:
        p['percent'] = p['percent']/num
        
    return video_progress 

def add_video_progress(base, new):
    
    for i in range(len(base)):
        if base[i]['percent'] + new[i]['percent'] > 100:
            base[i]['percent'] = 100
        else:
            base[i]['percent'] += new[i]['percent']
    return base


def optimize_video_progress(video_progress):
    time_len = len(video_progress)
    #print 'time_len'
    #print time_len
    if time_len == 1:
        return ([video_progress[0]['percent']], video_progress[0]['time'],
                video_progress[0]['time'], 0)
    if time_len == 0:
        print 'EXCEPTION'
        return ([0], None, None, 0)
    
    # Get start date
    start_index = 0
    
    while (start_index < time_len
           and video_progress[start_index]['percent'] == 0):
        start_index += 1
    
    if start_index == time_len:
        print 'EXCEPTION start_index == time_len'
        return ([0], None, None, 0)
    
    # Get end date
    last_percent = video_progress[time_len - 1]['percent']
    end_index = start_index
    index_found = False
    
    for i in range(start_index,time_len):
        if video_progress[i]['percent'] == last_percent:
            if not index_found: 
                end_index = i
                index_found = True
        else:
            end_index = i
            index_found = False
    
    # Get dates
    #start_index = start_index - 1 if (start_index >= 1) else start_index
    end_index = end_index + 1 if (end_index < time_len -1) else end_index
    
    end_date = video_progress[end_index]['time']
    start_date = video_progress[start_index]['time']
    
    tdelta =  0 if (start_index == end_index) else (video_progress[1]['time'] - video_progress[0]['time'])
    delta = (tdelta.days*60*60*24 + tdelta.seconds) if tdelta is not 0 else 0
    
    # Get progress array
    progress = []
    for i in range(start_index - 1, end_index):
        progress.append(video_progress[i]['percent'])
    print 'progress'
    print progress    
    return progress, start_date, end_date, delta


### Codigo Javier Orcoyen
def update_DB_course_video_progress(course_key, timeline=None):
    
    newEvents = 0

    if timeline is None:
        timeline = create_course_progress(course_key)[1]
        
    all_video_progress = []
    prof_video_progress = []
    ok_video_progress = []
    fail_video_progress = []
    original_video_progress = []
    original_all_video_progress = []
    original_prof_video_progress = []
    original_pass_video_progress = []
    original_fail_video_progress = []
    num_all = 0
    num_prof = 0
    num_ok = 0
    num_fail = 0
    prof = 0
    ok = 0
    fail = 0
    
    for time in timeline:
        all_video_progress.append({'percent':0, 'time':time})
        prof_video_progress.append({'percent':0, 'time':time})
        ok_video_progress.append({'percent':0, 'time':time})
        fail_video_progress.append({'percent':0, 'time':time})
        
    students = get_course_students(course_key)
    course = get_course_module(course_key)
    
    for student in students:
    
        std_video_progress = get_student_video_progress(course, student, timeline)
        
        #If there are new progresses
        if std_video_progress != None:

            newEvents = 1

            # Add grade to all
            all_video_progress = add_video_progress(all_video_progress, 
                                                std_video_progress)
            num_all += 1
            # Add grade to category
            studentgrades_filtered =  StudentGrades.objects.filter(course_id=course_key, student_id=student.id)
            if studentgrades_filtered.count() > 0:
                grade_group = studentgrades_filtered[0].grade_group
                if grade_group == 'PROF':
                    prof = 1
                    prof_video_progress = add_video_progress(prof_video_progress,
                                                         std_video_progress)
                    num_prof += 1
                elif grade_group == 'OK':
                    ok = 1
                    ok_video_progress = add_video_progress(ok_video_progress,
                                                       std_video_progress)
                    num_ok += 1
                elif grade_group == 'FAIL':
                    fail = 1
                    fail_video_progress = add_video_progress(fail_video_progress,
                                                         std_video_progress)
                    num_fail += 1
        
            # Update entry
            try:
                #Using get beceause there will only be one entry for each student and each course
                #sql_filtered = CourseProbVidProgress.objects.get(course_id=course_key, student_id=student.id, type='VID')
                #Codigo Gascon
                sql_filtered = CourseProbVidProgress.objects.get(course_id=course_key, student_id=student.id, type='VID')
                
            except ObjectDoesNotExist:
                print 'EXCEPTION sql_filtered = None'
                sql_filtered = None
            #print 'video progress'
            #print std_video_progress
            progress, start_date, end_date, delta = optimize_video_progress(std_video_progress)
            print 'start_date students'
            print   start_date
            print 'end_date students'
            print end_date 
            # Create entry
            if (sql_filtered == None and start_date != None and end_date != None):
                CourseProbVidProgress.objects.create(student_id=student.id, course_id=course_key, progress=progress, 
                                                 type='VID', start_time=start_date,  end_time=end_date, delta=delta)
            else:
                # Check for new events, but no new progress
                if progress == [] or progress == [0]:
                    print 'PROGRESS VACIO'
                    newEvents = 0

                else:
                    # Get stored progress
                    print 'sql_filtered.progress'
                    print sql_filtered.progress
                    original_progress = ast.literal_eval(sql_filtered.progress)
                    start_date = sql_filtered.start_time
                
                    # Original progress (list) into progress timeline (dictionary list with 'percent' and 'time')        
                    original_video_progress = progress_to_timelineProgress(timeline, start_date, original_progress, 'video')
                           
                    # Add the new progress to the stored one
                    total_progress = add_video_progress(original_video_progress, std_video_progress)
                    
                    progress, start_date, end_date, delta = optimize_video_progress(total_progress)
                    
                    # Update entry
                    sql_filtered.progress = progress
                    sql_filtered.start_time = start_date
                    sql_filtered.end_time = end_date
                    sql_filtered.delta = delta
                    sql_filtered.last_calc = timezone.now()
                    sql_filtered.save()

        #If there are no new events
        else:

            # Add grade to all, because the mean also takes into account students with 0 progress
            num_all += 1

            # Add grade to category, because the mean also takes into account students with 0 progress
            studentgrades_filtered = StudentGrades.objects.filter(course_id=course_key, 
                                                              student_id=student.id)
            if studentgrades_filtered.count() > 0:
                grade_group = studentgrades_filtered[0].grade_group
                if grade_group == 'PROF':
                    num_prof += 1
                elif grade_group == 'OK':
                    num_ok += 1
                elif grade_group == 'FAIL':
                    num_fail += 1

    # If there have been new events, add group progress to database
    if newEvents == 1:
    
        # New ALL students progress 
        
        all_video_progress = mean_video_progress_sum(all_video_progress, num_all)
     
        # Update entry
        try:
            #Using get beceause there will only be one entry for each student and each course
            sql_filtered = CourseProbVidProgress.objects.get(course_id=course_key, type='VID',
                                                        student_id=CourseProbVidProgress.ALL_STUDENTS)
        except ObjectDoesNotExist:
            sql_filtered = None

        progress, start_date, end_date, delta = optimize_video_progress(all_video_progress)
        print 'start_date newEvents'
        print   start_date
        print 'end_date newEvents'
        print end_date 
        # Create entry
        if (sql_filtered == None and start_date != None and end_date != None):
            CourseProbVidProgress.objects.create(student_id=CourseProbVidProgress.ALL_STUDENTS,
                                             course_id=course_key, progress=progress,
                                             type='VID', start_time=start_date,
                                             end_time=end_date, delta=delta)
        elif (progress != [0]):
            # Get stored progress
            original_progress = ast.literal_eval(sql_filtered.progress)
            start_date = sql_filtered.start_time
                
            # New progress (list) into progress timeline (dictionary list with 'score' and 'time')
            original_all_video_progress = progress_to_timelineProgress(timeline, start_date, original_progress, 'video')
        
            # Add the new progress to the stored one
            total_progress = add_video_progress(original_all_video_progress, all_video_progress)

            progress, start_date, end_date, delta = optimize_video_progress(total_progress)

            # Update entry
            sql_filtered.progress = progress
            sql_filtered.start_time = start_date
            sql_filtered.end_time = end_date
            sql_filtered.delta = delta
            sql_filtered.last_calc = timezone.now()
            sql_filtered.save()
        
        if prof == 1:
            # New PROFICIENCY students progress to database
            prof_video_progress = mean_video_progress_sum(prof_video_progress, num_prof)
        
            # Update entry
            try:
                #Using get beceause there will only be one entry for each student and each course
                sql_filtered = CourseProbVidProgress.objects.get(course_id=course_key, type='VID',
                                                        student_id=CourseProbVidProgress.PROF_GROUP)
            except ObjectDoesNotExist:
                sql_filtered = None

            progress, start_date, end_date, delta = optimize_video_progress(prof_video_progress)
            print 'start_date prof'
            print   start_date
            print 'end_date prof'
            print end_date
            # Create entry
            if (sql_filtered == None and start_date != None and end_date != None):
                CourseProbVidProgress.objects.create(student_id=CourseProbVidProgress.PROF_GROUP,
                                             course_id=course_key, progress=progress,
                                             type='VID', start_time=start_date,
                                             end_time=end_date, delta=delta)
            elif (progress != [0]):
                # Check for new events, but no new progress
                # Get stored progress
                original_progress = ast.literal_eval(sql_filtered.progress)
                start_date = sql_filtered.start_time
                
                # New progress (list) into progress timeline (dictionary list with 'score' and 'time')
                original_prof_video_progress = progress_to_timelineProgress(timeline, start_date, original_progress, 'video')
                
                # Add the new progress to the stored one
                total_progress = add_video_progress(original_prof_video_progress, prof_video_progress)

                progress, start_date, end_date, delta = optimize_video_progress(total_progress)

                # Update entry
                sql_filtered.progress = progress
                sql_filtered.start_time = start_date
                sql_filtered.end_time = end_date
                sql_filtered.delta = delta
                sql_filtered.last_calc = timezone.now()
                sql_filtered.save()

        if ok == 1:
            # New PASS students progress to database
            ok_video_progress = mean_video_progress_sum(ok_video_progress, num_ok)
            # Update entry
            try:
                #Using get beceause there will only be one entry for each student and each course
                sql_filtered = CourseProbVidProgress.objects.get(course_id=course_key, type='VID',
                                                        student_id=CourseProbVidProgress.PASS_GROUP)
            except ObjectDoesNotExist:
                sql_filtered = None

            progress, start_date, end_date, delta = optimize_video_progress(ok_video_progress)
            # Create entry
            if (sql_filtered == None and start_date != None and end_date != None):
                CourseProbVidProgress.objects.create(student_id=CourseProbVidProgress.PASS_GROUP,course_id=course_key, progress=progress,type='VID', start_time=start_date,end_time=end_date, delta=delta)
            elif (progress != [0]):
                # Get stored progress
                original_progress = ast.literal_eval(sql_filtered.progress)
                start_date = sql_filtered.start_time
                
                # New progress (list) into progress timeline (dictionary list with 'score' and 'time')
                original_pass_video_progress = progress_to_timelineProgress(timeline, start_date, original_progress, 'video')
                
                # Add the new progress to the stored one
                total_progress = add_video_progress(original_pass_video_progress, ok_video_progress)

                progress, start_date, end_date, delta = optimize_video_progress(total_progress)

                # Update entry
                sql_filtered.progress = progress
                sql_filtered.start_time = start_date
                sql_filtered.end_time = end_date
                sql_filtered.delta = delta
                sql_filtered.last_calc = timezone.now()
                sql_filtered.save()

        if fail == 1:
            # New FAIL students progress to database
            fail_video_progress = mean_video_progress_sum(fail_video_progress, num_fail)
        
            # Update entry
            try: 
                #Using get beceause there will only be one entry for each student and each course
                sql_filtered = CourseProbVidProgress.objects.get(course_id=course_key, type='VID',
                                                        student_id=CourseProbVidProgress.FAIL_GROUP)
            except ObjectDoesNotExist:
                sql_filtered = None

            progress, start_date, end_date, delta = optimize_video_progress(fail_video_progress)
            # Create entry
            if (sql_filtered == None and start_date != None and end_date != None):
                CourseProbVidProgress.objects.create(student_id=CourseProbVidProgress.FAIL_GROUP,
                                             course_id=course_key, progress=progress,
                                             type='VID', start_time=start_date,
                                             end_time=end_date, delta=delta)
            elif (progress != [0]):
                # Get stored progress
                original_progress = ast.literal_eval(sql_filtered.progress)
                start_date = sql_filtered.start_time
            
                # New progress (list) into progress timeline (dictionary list with 'score' and 'time')
                original_fail_video_progress = progress_to_timelineProgress(timeline, start_date, original_progress, 'video')
                
                # Add the new progress to the stored one
                total_progress = add_video_progress(original_fail_video_progress, fail_video_progress)

                progress, start_date, end_date, delta = optimize_video_progress(total_progress)

                # Update entry
                sql_filtered.progress = progress
                sql_filtered.start_time = start_date
                sql_filtered.end_time = end_date
                sql_filtered.delta = delta
                sql_filtered.last_calc = timezone.now()
                sql_filtered.save()


def get_DB_course_video_problem_progress(course_key, student_id=None):
    """
    Return course problem and video progress from database
    
    course_key: course id key
    student_id: if None, function will return all students
    """
    
    # Students progress
    students_vidprob_progress = {}
    if student_id is None:
        sql_progress = CourseProbVidProgress.objects.filter(course_id=course_key)
    else:
        sql_progress = CourseProbVidProgress.objects.filter(course_id=course_key, student_id=student_id)
    for prob_progress in sql_progress.filter(type='PROB'):
        vid_progress = sql_progress.filter(type='VID', student_id=prob_progress.student_id)[0]# C. J. Gascon CODIGO REAL CON DATOS
        #vid_progress = sql_progress.filter(type='VID', student_id=prob_progress.student_id)
        # Start time
        if prob_progress.start_time is None:
            start_datetime = vid_progress.start_time
        elif vid_progress.start_time is None:
            start_datetime = prob_progress.start_time
        else:
            start_datetime = min(prob_progress.start_time, vid_progress.start_time)
        # End time
        if prob_progress.end_time is None:
            end_datetime = vid_progress.end_time
        elif vid_progress.end_time is None:
            end_datetime = prob_progress.end_time
        else:
            end_datetime = max(prob_progress.end_time, vid_progress.end_time)
        
        if prob_progress.delta == 0 or vid_progress.delta == 0:
            delta_l = prob_progress.delta if prob_progress.delta != 0 else vid_progress.delta 
        else:
            delta_l = min(prob_progress.delta, vid_progress.delta)
        delta = timedelta(seconds=delta_l)
        
        prob_data = ast.literal_eval(prob_progress.progress)
        vid_data = ast.literal_eval(vid_progress.progress)
        
        index_prob = 0
        index_vid = 0
        
        students_vidprob_progress[prob_progress.student_id] = []
        
        if (start_datetime is None or
            end_datetime is None or 
            delta == 0):
            return students_vidprob_progress
        
        for time in perdelta(start_datetime, end_datetime, delta):
            prob_result = 0
            if (prob_progress.start_time is not None and
                prob_progress.start_time <= time):
                if time <= prob_progress.end_time:
                    # time in problem timeline
                    prob_result = prob_data[index_prob]
                    index_prob += 1
                else:
                    # time > problem timeline
                    prob_result = prob_data[-1]
            else:
                # time < problem timeline
                prob_result = 0
                
            vid_result = 0
            if (vid_progress.start_time is not None and
                vid_progress.start_time <= time):
                if time <= vid_progress.end_time:
                    # time in video timeline
                    vid_result = vid_data[index_vid]
                    index_vid += 1
                else:
                    # time > video timeline
                    vid_result = vid_data[-1]
            else:
                # time < video timeline
                vid_result = 0
            
            # Add data
            students_vidprob_progress[prob_progress.student_id].append({'problems': prob_result,
                                                                        'videos': vid_result,
                                                                        'time': time.strftime("%d/%m/%Y")})
    return students_vidprob_progress


def to_iterable_module_id(block_usage_locator):
  
    iterable_module_id = []
    iterable_module_id.append(block_usage_locator.org)
    iterable_module_id.append(block_usage_locator.course)
    #iterable_module_id.append(block_usage_locator.run)
    iterable_module_id.append(block_usage_locator.branch)
    iterable_module_id.append(block_usage_locator.version_guid)
    iterable_module_id.append(block_usage_locator.block_type)
    iterable_module_id.append(block_usage_locator.block_id)    
    
    return iterable_module_id


##########################################################################
######################## TIME SCHEDULE ###################################
##########################################################################


### Codigo Javier Orcoyen
def time_schedule(course_id):
    students = get_course_students(course_id)
    
    newEvents = 0

    morningTimeStudentCourse = 0
    afternoonTimeStudentCourse = 0
    nightTimeStudentCourse = 0
    
    for student in students:

        firstEventOfSeries = None
        previousEvent = None     
        
        morningTimeStudent = 0
        afternoonTimeStudent = 0
        nightTimeStudent = 0
        
        currentSchedule = ""
        
        studentEvents = get_new_events_sql(course_id, student, 'timeSchedule')
        
        #If there are new events
        if studentEvents != None:      
            
            newEvents = 1

            for currentEvent in studentEvents:
            
                if(currentSchedule == ""):
                    currentSchedule = current_schedule(currentEvent.dtcreated.hour)
                    if(previousEvent == None):                    
                        firstEventOfSeries = currentEvent
                    else:
                        firstEventOfSeries = previousEvent
                else:
                    if((minutes_between(previousEvent.dtcreated,currentEvent.dtcreated) >= 30) or currentSchedule != current_schedule(currentEvent.dtcreated.hour)):
                        print 'currentEvent'
                        print currentEvent                    
                        if(currentSchedule == "morning"):
                            morningTimeStudent += minutes_between(firstEventOfSeries.dtcreated, previousEvent.dtcreated)
                        elif(currentSchedule == "afternoon"):
                            afternoonTimeStudent += minutes_between(firstEventOfSeries.dtcreated, previousEvent.dtcreated)
                            print 'afternoonTimeStudent'
                            print afternoonTimeStudent
                        elif(currentSchedule == "night"):
                            nightTimeStudent += minutes_between(firstEventOfSeries.dtcreated, previousEvent.dtcreated)
                        
                        currentSchedule = ""
                            
                previousEvent = currentEvent
            
            if(currentSchedule == "morning"):
                morningTimeStudent += minutes_between(firstEventOfSeries.dtcreated, previousEvent.dtcreated)
            elif(currentSchedule == "afternoon"):
                afternoonTimeStudent += minutes_between(firstEventOfSeries.dtcreated, previousEvent.dtcreated)
                print 'afternoonTimeStudent'
                print afternoonTimeStudent
            elif(currentSchedule == "night"):
                nightTimeStudent += minutes_between(firstEventOfSeries.dtcreated, previousEvent.dtcreated)
        
            morningTimeStudentCourse += morningTimeStudent
            afternoonTimeStudentCourse += afternoonTimeStudent
            nightTimeStudentCourse += nightTimeStudent
        
            timeSchedule = {'morningTime' : morningTimeStudent,
                        'afternoonTime' : afternoonTimeStudent,
                        'nightTime' : nightTimeStudent}
            
            # Update database
            try:
                #Using get beceause there will only be one entry for each student and each course
                studentTimeSchedule = TimeSchedule.objects.get(course_id=course_id, student_id=student.id)
            except ObjectDoesNotExist:
                studentTimeSchedule = None
            
            #Check for existing entry
            if studentTimeSchedule == None:
                # Create entry
                TimeSchedule.objects.create(student_id=student.id, course_id=course_id, time_schedule=timeSchedule)
            else:
                # Update entry
                print 'Update entry'
                print timeSchedule['afternoonTime']
                print afternoonTimeStudentCourse
                studentTimeScheduleValue = ast.literal_eval(studentTimeSchedule.time_schedule)
                print studentTimeScheduleValue['afternoonTime']
                totalTimeSchedule = {'morningTime' : studentTimeScheduleValue['morningTime']+timeSchedule['morningTime'],
                          'afternoonTime' : studentTimeScheduleValue['afternoonTime']+timeSchedule['afternoonTime'],
                          'nightTime' : studentTimeScheduleValue['nightTime']+timeSchedule['nightTime']} 

                studentTimeSchedule.time_schedule = totalTimeSchedule
                studentTimeSchedule.last_calc = datetime.datetime.now()
                studentTimeSchedule.save()
    
    timeScheduleCourse = {'morningTime' : morningTimeStudentCourse,
                          'afternoonTime' : afternoonTimeStudentCourse,
                          'nightTime' : nightTimeStudentCourse}
    
    #If there have been new events processed, update the total value in the database
    if newEvents == 1:

        # Update database
        try:
            #Using get beceause there will only be one entry for each student and each course
            courseTimeSchedule = TimeSchedule.objects.get(course_id=course_id, student_id=TimeSchedule.ALL_STUDENTS)
        except ObjectDoesNotExist:
            courseTimeSchedule = None

        #Check for existing entry
        if(courseTimeSchedule == None):
            # Create entry
            TimeSchedule.objects.create(student_id=TimeSchedule.ALL_STUDENTS, course_id=course_id, time_schedule=timeScheduleCourse)
        else:
            # Update entry
            courseTimeScheduleValue= ast.literal_eval(courseTimeSchedule.time_schedule)
            totalTimeScheduleCourse = {'morningTime' : courseTimeScheduleValue['morningTime']+timeScheduleCourse['morningTime'],
                          'afternoonTime' : courseTimeScheduleValue['afternoonTime']+timeScheduleCourse['afternoonTime'],
                          'nightTime' : courseTimeScheduleValue['nightTime']+timeScheduleCourse['nightTime']}
        
            courseTimeSchedule.time_schedule = totalTimeScheduleCourse
            courseTimeSchedule.last_calc = datetime.datetime.now()
            courseTimeSchedule.save()
    


def current_schedule(hour):
    """
    Returns if the hour is in the morning, afternoon or night schedule
    hour: the hour of the time
    """ 
    currentSchedule = ""
    print 'hour timeschedule'
    print hour
    if( 6 < hour and hour < 14 ):
        currentSchedule = "morning"
    elif( 14 <= hour and hour < 21):
        currentSchedule = "afternoon"
    elif( hour <= 6 or hour == 21 or hour == 22 or hour == 23 or hour == 0):
        currentSchedule = "night"
    
    return currentSchedule

def get_DB_time_schedule(course_key, student_id=None):
    """
    Return course section accesses from database
    
    course_key: course id key
    student_id: if None, function will return all students
    """
    print 'student_id get_DB_time_schedule'
    print student_id
    student_time_schedule = {}
    if student_id is None:
        sql_time_schedule = TimeSchedule.objects.filter(course_id=course_key)
    else:
        sql_time_schedule = TimeSchedule.objects.filter(course_id=course_key, student_id=student_id)
        
    for std_time_schedule in sql_time_schedule:
        student_time_schedule[std_time_schedule.student_id] = ast.literal_eval(std_time_schedule.time_schedule)
    
    return student_time_schedule


##########################################################################
############## DAILY TIME ON PROBLEMS AND VIDEOS #########################
##########################################################################


#Codigo Javier Orcoyen
def add_dates_and_time_per_date(original_dates, original_time_per_date, new_dates, new_time_per_date):

    total_dates = []
    total_time_per_date = []

    # Check if new dates has 1 date (if it is empty, len will be 0) and if last day of original dates is the same as the new date 
    if len(new_dates) == 1 and (original_dates[-1] == new_dates[0]):
        # Dates stay the same because we are still in the same day
        total_dates = original_dates
        # Add new value to original value
        if len(original_dates) == 1:
            total_time_per_date = []
            total_time_per_date.append(original_time_per_date[0]+new_time_per_date[0])
        else:
            value=[]
            value.append(original_time_per_date[-1]+new_time_per_date[0])
            total_time_per_date = original_time_per_date[:-1]+value
    # Check if new dates has more than 1 date and if last day of original dates is the same as the first one of new dates
    elif len(new_dates) > 1 and (original_dates[-1] == new_dates[0]):
        # Add the new days without adding again the first one (which is the same as the last original one)
        total_dates = original_dates+new_dates[1:]
        value=[]
        value.append(original_time_per_date[-1]+new_time_per_date[0])
        total_time_per_date = original_time_per_date[:-1]+value+new_time_per_date[1:] 
    # New days or day but the last original one is not the same as the first new one 
    else:
        total_dates = original_dates+new_dates
        total_time_per_date = original_time_per_date+new_time_per_date

    return total_dates, total_time_per_date


# Codigo Javier Orcoyen
def update_DB_daily_time_prob_and_vids(course_key=None):
# course_key should be a course_key
    
    kw_daily_consumption = {
        'student': '',
        'course_key': course_key,
        'module_type': '',
        'dates': '',
        'time_per_date': '',        
    }

    if course_key is not None:
        # update data for the provided course
        
        course = get_course_by_id(course_key, depth=None)
        usernames_in = [x.username.encode('utf-8') for x in CourseEnrollment.objects.users_enrolled_in(course_key)]#Codigo J.A. Gascon
        videos_in, problems_in = videos_problems_in(course)
        video_names, video_module_keys, video_durations = get_info_videos_descriptors(videos_in)
        problem_names = [x.display_name_with_default.encode('utf-8') for x in problems_in]
        problem_ids = [x.location for x in problems_in]
        
        # List of UserVideoIntervals
        users_video_intervals = []
        users_with_video_events = []
        # List of UserTimeOnProblems
        users_time_on_problems = []
        users_with_problem_events = []
        
        for username_in in usernames_in:
            for video_module_key in video_module_keys:
                interval_start, interval_end, vid_start_time, vid_end_time = find_video_intervals(course_key, username_in, video_module_key, 'videoDailyTime')
                # Just users with video events
                if interval_start is not None and interval_end is not None and vid_start_time is not None and vid_end_time is not None:
                    # If a user has events for more than one video, his name will be repeated in users_with_video_events
                    users_with_video_events.append(username_in)
                    disjointed_start, disjointed_end = video_len_watched(interval_start, interval_end)
                    users_video_intervals.append(UserVideoIntervals(username_in, video_module_key, 
                                                               interval_start, interval_end,
                                                               vid_start_time, vid_end_time,
                                                               disjointed_start, disjointed_end))    
 
            for problem_id in problem_ids:
                problem_time, days, daily_time = time_on_problem(course_key, username_in, problem_id, 'problemDailyTime')
                # Just users with problem events
                if problem_time is not None and days is not None and daily_time is not None:
                    # If a user has events for more than one problem, his name will be repeated in users_with_problem_events
                    users_with_problem_events.append(username_in)
                    users_time_on_problems.append(UserTimeOnProblems(username_in, problem_id, 
                                                                 problem_time, days, daily_time))   
        # DailyConsumption table data
        accum_vid_days = []
        accum_vid_daily_time = []
        accum_prob_days = []
        accum_prob_daily_time = []

        # Delete repeated values
        sorted_users_with_video_events = sorted(set(users_with_video_events))

        for username_in in sorted_users_with_video_events:
            low_index = users_with_video_events.index(username_in)
            high_index = low_index + users_with_video_events.count(username_in)
            video_days, video_daily_time = daily_time_on_videos(users_video_intervals[low_index:high_index])
            if video_days is not None and video_daily_time is not None:
                video_days = datelist_to_isoformat(video_days)
                if len(video_days) > 0:
                    accum_vid_days += video_days
                    accum_vid_daily_time += video_daily_time
                # save to DailyConsumption table
                kw_daily_consumption['student'] = username_in
                kw_daily_consumption['module_type'] = 'video'
                kw_daily_consumption['dates'] = json.dumps(video_days)
                kw_daily_consumption['time_per_date'] = json.dumps(video_daily_time)
                try:
                    new_entry = DailyConsumption.objects.get(student=kw_daily_consumption['student'], course_key=kw_daily_consumption['course_key'], module_type=kw_daily_consumption['module_type'])
                
                    total_dates, total_time_per_date = add_dates_and_time_per_date(ast.literal_eval(new_entry.dates), ast.literal_eval(new_entry.time_per_date), video_days, video_daily_time)

                    new_entry.dates = json.dumps(total_dates)
                    new_entry.time_per_date = json.dumps(total_time_per_date)

                except DailyConsumption.DoesNotExist:
                    new_entry = DailyConsumption(**kw_daily_consumption)
                new_entry.save()            
       
        # Delete repeated values
        sorted_users_with_problem_events = sorted(set(users_with_problem_events))
        
        for username_in in sorted_users_with_problem_events:
            low_index = users_with_problem_events.index(username_in)
            high_index = low_index + users_with_problem_events.count(username_in)   
            problem_days, problem_daily_time = time_on_problems(users_time_on_problems[low_index:high_index])
            if problem_days is not None and problem_daily_time is not None:
                problem_days = datelist_to_isoformat(problem_days)
                if len(problem_days) > 0:
                    accum_prob_days += problem_days
                    accum_prob_daily_time += problem_daily_time
                # save to DailyConsumption table
                kw_daily_consumption['student'] = username_in
                kw_daily_consumption['module_type'] = 'problem'
                kw_daily_consumption['dates'] = json.dumps(problem_days)
                kw_daily_consumption['time_per_date'] = json.dumps(problem_daily_time)
                try:
                    new_entry = DailyConsumption.objects.get(student=kw_daily_consumption['student'], course_key=kw_daily_consumption['course_key'], module_type=kw_daily_consumption['module_type'])

                    total_dates, total_time_per_date = add_dates_and_time_per_date(ast.literal_eval(new_entry.dates), ast.literal_eval(new_entry.time_per_date), problem_days, problem_daily_time)

                    new_entry.dates = json.dumps(total_dates)
                    new_entry.time_per_date = json.dumps(total_time_per_date)

                except DailyConsumption.DoesNotExist:
                    new_entry = DailyConsumption(**kw_daily_consumption)            
                new_entry.save()

        # Average values
        kw_daily_consumption['student'] = '#average'
        kw_daily_consumption['module_type'] = 'problem'

        problem_days, problem_daily_time = class_time_on(accum_prob_days, accum_prob_daily_time)
        if problem_days is not None and problem_daily_time is not None:
            kw_daily_consumption['dates'] = json.dumps(problem_days)
            kw_daily_consumption['time_per_date'] = json.dumps(problem_daily_time)
            try:
                new_entry = DailyConsumption.objects.get(student=kw_daily_consumption['student'], course_key=kw_daily_consumption['course_key'], module_type=kw_daily_consumption['module_type'])

                total_dates, total_time_per_date = add_dates_and_time_per_date(ast.literal_eval(new_entry.dates), ast.literal_eval(new_entry.time_per_date), problem_days, problem_daily_time)

                new_entry.dates = json.dumps(total_dates)
                new_entry.time_per_date = json.dumps(total_time_per_date)

            except DailyConsumption.DoesNotExist:
                new_entry = DailyConsumption(**kw_daily_consumption)        
            new_entry.save()

        kw_daily_consumption['module_type'] = 'video'

        video_days, video_daily_time = class_time_on(accum_vid_days, accum_vid_daily_time)
        if video_days is not None and video_daily_time is not None:
            kw_daily_consumption['dates'] = json.dumps(video_days)
            kw_daily_consumption['time_per_date'] = json.dumps(video_daily_time)
            try:
                new_entry = DailyConsumption.objects.get(student=kw_daily_consumption['student'], course_key=kw_daily_consumption['course_key'], module_type=kw_daily_consumption['module_type'])

                total_dates, total_time_per_date = add_dates_and_time_per_date(ast.literal_eval(new_entry.dates), ast.literal_eval(new_entry.time_per_date), video_days, video_daily_time)

                new_entry.dates = json.dumps(total_dates)
                new_entry.time_per_date = json.dumps(total_time_per_date)

            except DailyConsumption.DoesNotExist:
                new_entry = DailyConsumption(**kw_daily_consumption)
            new_entry.save()    
    else:
        pass        


##########################################################################
################## PROBLEM TIME DISTRIBUTION #############################
##########################################################################


# Codigo Javier Orcoyen
def update_DB_problem_time_distribution(course_key=None):
# course_key should be a course_key
  
    kw_consumption_module = {
        'student': '',
        'course_key': course_key,
        'module_type': '',
        'module_key': '',
        'display_name': '',
        'total_time': 0,
    }
    
    if course_key is not None:
        # update data for the provided course
        
        course = get_course_by_id(course_key, depth=None)
        usernames_in = [x.username.encode('utf-8') for x in CourseEnrollment.objects.users_enrolled_in(course_key)]#Codigo J.A. Gascon
        problems_in = videos_problems_in(course)[1]
        problem_names = [x.display_name_with_default.encode('utf-8') for x in problems_in]
        problem_ids = [x.location for x in problems_in]
        #print 'problems_ids 1'
        #print problem_ids
        # List of UserTimeOnProblems
        users_time_on_problems = []
        users_with_problem_events = []
        users_with_problem_events_problem_ids = []
        users_with_problem_events_problem_names = []
        indexes = []

        for username_in in usernames_in:
            #print 'users'
            #print 'problems_ids 1'
            #print problem_ids
            for problem_id in problem_ids:
                #print 'PROBLEMS_IDS 2'
                #print problem_id
                problem_time, days, daily_time = time_on_problem(course_key, username_in, problem_id, 'problemTimeDistribution')
                #print 'TIMES todos vacios'
                #print problem_time
                #print days
                #print daily_time
                # Just users with problem events
                if problem_time is not None and days is not None and daily_time is not None:
                    

                    # If a user has events for more than one problem, his name will be repeated in users_with_problem_events
                    users_with_problem_events.append(username_in)
                    # Problem info will be in the same index in as problem_id in problem_id
                    index_problem = problem_ids.index(problem_id)
                    indexes.append(index_problem)
                    # Save the id of problems with new events
                    users_with_problem_events_problem_ids.append(problem_ids[index_problem])
                    # Save the name of problems with new events
                    users_with_problem_events_problem_names.append(problem_names[index_problem])
                    #print 'USERNAME problem_time'
                    #print problem_time
                    users_time_on_problems.append(UserTimeOnProblems(username_in, problem_id, problem_time, days, daily_time))   
                    #print 'USERNAME'
                    #print username_in  
                    #print users_time_on_problems     
        # ConsumptionModule table data
        accum_problem_time = [0] * len(problem_ids)

        # Delete repeated values
        sorted_users_with_problem_events = sorted(set(users_with_problem_events))
        """print 'SORTED'
        print sorted_users_with_problem_events
        print 'users_with_problem_events'
        print users_with_problem_events
        print 'USERNAMES_IN'
        print usernames_in"""
        for username_in in sorted_users_with_problem_events:
            kw_consumption_module['student'] = username_in
            #problem modules
            kw_consumption_module['module_type'] = 'problem'
            low_index = users_with_problem_events.index(username_in)
            high_index = low_index + users_with_problem_events.count(username_in)   
            time_x_problem = problem_consumption(users_time_on_problems[low_index:high_index])
            user_problem_ids = users_with_problem_events_problem_ids[low_index:high_index]
            user_problem_names = users_with_problem_events_problem_names[low_index:high_index]
            problem_indexes = indexes[low_index:high_index]
            #print 'time_x_problem'
            #print username_in
            #print low_index
            #print high_index
            #print user_problem_ids
            #print time_x_problem
            if time_x_problem is not None:
                for j in range(0,len(problem_indexes)):
                    #print 'USERNAME IN TIMEXPROBLEM'
                    #print username_in
                    accum_problem_time[problem_indexes.index(j)] += time_x_problem[j]
                    
                for i in range(0,len(user_problem_ids)):
                    kw_consumption_module['module_key'] = user_problem_ids[i]
                    kw_consumption_module['display_name'] = user_problem_names[i]
                    kw_consumption_module['total_time'] = time_x_problem[i]       
                    try:
                        new_entry = ConsumptionModule.objects.get(student=kw_consumption_module['student'], module_key=kw_consumption_module['module_key'])

                        new_entry.total_time = new_entry.total_time + kw_consumption_module['total_time']

                    except ConsumptionModule.DoesNotExist:
                        new_entry = ConsumptionModule(**kw_consumption_module)                    
                    new_entry.save()
       
        # average values
        if accum_problem_time != [0] * len(problem_ids):
            kw_consumption_module['student'] = '#average'
            kw_consumption_module['module_type'] = 'problem'
            for i in range(0,len(accum_problem_time)):
                if accum_problem_time[i] != 0:
                    # Commented because we do not want the mean here but the total time
                    #accum_problem_time[i] = truediv(accum_problem_time[i],len(usernames_in))
                    kw_consumption_module['module_key'] = problem_ids[i]
                    kw_consumption_module['display_name'] = problem_names[i]
                    kw_consumption_module['total_time'] = accum_problem_time[i]
                    try:
                        new_entry = ConsumptionModule.objects.get(student=kw_consumption_module['student'], module_key=kw_consumption_module['module_key'])

                        new_entry.total_time = new_entry.total_time + kw_consumption_module['total_time']

                    except ConsumptionModule.DoesNotExist:
                        new_entry = ConsumptionModule(**kw_consumption_module)            
                    new_entry.save()
    else:
        print 'EXCEPTION'
        pass


##########################################################################
################### VIDEO TIME DISTRIBUTION ##############################
##########################################################################


# Codigo Javier Orcoyen
def update_DB_video_time_distribution(course_key=None):
    # course_key should be a course_key
  
    kw_consumption_module = {
        'student': '',
        'course_key': course_key,
        'module_type': '',
        'module_key': '',
        'display_name': '',
        'total_time': 0,
    }
    
    if course_key is not None:
        # update data for the provided course
        
        course = get_course_by_id(course_key, depth=None)
        usernames_in = [x.username.encode('utf-8') for x in CourseEnrollment.objects.users_enrolled_in(course_key)]#Codigo J.A.Gascon
        videos_in = videos_problems_in(course)[0]
        video_names, video_module_keys, video_durations = get_info_videos_descriptors(videos_in)
        print 'VIDEO DURATIONS'
        print video_durations
        # List of UserVideoIntervals
        users_video_intervals = []
        users_with_video_events = []
        users_with_video_events_video_ids = []
        users_with_video_events_video_names = []
        users_with_video_events_video_durations = []
        indexes = []
        
        for username_in in usernames_in:
            for video_module_key in video_module_keys:
                interval_start, interval_end, vid_start_time, vid_end_time = find_video_intervals(course_key,username_in, video_module_key, 'videoTimeDistribution')
                # Just users with video events
                if interval_start is not None and interval_end is not None and vid_start_time is not None and vid_end_time is not None:
                    # If a user has events for more than one video, his name will be repeated in users_with_video_events
                    users_with_video_events.append(username_in)
                    # Video info will be in the same index in as video_module_key in video_module_keys
                    index_video = video_module_keys.index(video_module_key)
                    indexes.append(index_video)
                    # Save the id of the video for which the user has new events
                    users_with_video_events_video_ids.append(video_module_keys[index_video])
                    # Save the name of the video for which the user has new events
                    users_with_video_events_video_names.append(video_names[index_video])
                    # Save the duration of the video for which the user has new events
                    users_with_video_events_video_durations.append(video_durations[index_video])
                    disjointed_start, disjointed_end = video_len_watched(interval_start, interval_end)
                    users_video_intervals.append(UserVideoIntervals(username_in, video_module_key, 
                                                               interval_start, interval_end,
                                                               vid_start_time, vid_end_time,
                                                               disjointed_start, disjointed_end))         
        # ConsumptionModule table data
        accum_all_video_time = [0] * len(video_module_keys)

        # Delete repeated values
        sorted_users_with_video_events = sorted(set(users_with_video_events))
        
        for username_in in sorted_users_with_video_events:
            kw_consumption_module['student'] = username_in
            #video modules
            kw_consumption_module['module_type'] = 'video'          
            # all_video_time (in seconds)
            low_index = users_with_video_events.index(username_in)
            high_index = low_index + users_with_video_events.count(username_in)
            # Video id, name and duration of each video for which the user has new events
            user_video_ids = users_with_video_events_video_ids[low_index:high_index]
            user_video_names = users_with_video_events_video_names[low_index:high_index]
            video_durations = users_with_video_events_video_durations[low_index:high_index]
            video_indexes = indexes[low_index:high_index]
            all_video_time = video_consumption(users_video_intervals[low_index:high_index], video_durations)[1]
            
            if all_video_time is not None:
                for i in range(0,len(user_video_ids)):
                    accum_all_video_time[video_indexes[i]] += all_video_time[i]
                    kw_consumption_module['module_key'] = user_video_ids[i]
                    kw_consumption_module['display_name'] = user_video_names[i]
                    kw_consumption_module['total_time'] = all_video_time[i]
                    try:
                        new_entry = ConsumptionModule.objects.get(student=kw_consumption_module['student'], module_key=kw_consumption_module['module_key'])

                        new_entry.total_time = new_entry.total_time + kw_consumption_module['total_time'] 

                    except ConsumptionModule.DoesNotExist:
                        new_entry = ConsumptionModule(**kw_consumption_module)
                    new_entry.save()
        
        # average values
        if accum_all_video_time != [0] * len(video_module_keys):
            kw_consumption_module['student'] = '#average'
            kw_consumption_module['module_type'] = 'video'
                        
            for i in range(0,len(accum_all_video_time)):
                if accum_all_video_time[i] != 0:
                    #accum_all_video_time[i] = int(round(truediv(accum_all_video_time[i],len(usernames_in)),0))
                    kw_consumption_module['module_key'] = video_module_keys[i]
                    kw_consumption_module['display_name'] = video_names[i]
                    kw_consumption_module['total_time'] = accum_all_video_time[i]
                    try:
                        new_entry = ConsumptionModule.objects.get(student=kw_consumption_module['student'], module_key=kw_consumption_module['module_key'])

                        new_entry.total_time = new_entry.total_time + kw_consumption_module['total_time']

                    except ConsumptionModule.DoesNotExist:
                        new_entry = ConsumptionModule(**kw_consumption_module)            
                    new_entry.save()
    else:
        pass


##########################################################################
################## VIDEO EVENTS DISTRIBUTION #############################
##########################################################################


# Codigo Javier Orcoyen
def update_DB_video_events(course_key=None):
    # course_key should be a course_key
  
    kw_video_events = {
        'student': '',
        'course_key': course_key,
        'module_key': '',          
        'display_name': '',
        'play_events' : '',
        'pause_events' : '',
        'change_speed_events' : '',
        'seek_from_events' : '',
        'seek_to_events' : '',
    }
    
    if course_key is not None:
        # update data for the provided course
        
        course = get_course_by_id(course_key, depth=None)
        usernames_in = [x.username.encode('utf-8') for x in CourseEnrollment.objects.users_enrolled_in(course_key)]#Codigo J.A.Gascon
        videos_in = videos_problems_in(course)[0]
        video_names, video_module_keys, video_durations = get_info_videos_descriptors(videos_in)
        print 'VIDEO DURATIONS'
        print video_durations       
        # VideoEvents table data
        VIDEO_EVENTS = ['play', 'pause', 'change_speed', 'seek_from', 'seek_to']
        class_events_times = [[],[],[],[],[]]
        for username_in in usernames_in:
            kw_video_events['student'] = username_in
            for video_module_key in video_module_keys:
                kw_video_events['module_key'] = video_module_key
                kw_video_events['display_name'] = video_names[video_module_keys.index(video_module_key)]
                events_times = get_video_events_times(course_key, username_in, video_module_key)
                print 'EVENT TIMES'
                print events_times
                if events_times is None:
                    continue
                for event in VIDEO_EVENTS:
                    kw_video_events[event + '_events'] = events_times[VIDEO_EVENTS.index(event)]
                try:
                    new_entry = VideoEvents.objects.get(student=kw_video_events['student'], module_key=kw_video_events['module_key'])
                    # Add new values to original ones
                    play_events = ast.literal_eval(new_entry.play_events) + kw_video_events['play_events']
                    pause_events = ast.literal_eval(new_entry.pause_events) + kw_video_events['pause_events']
                    change_speed_events = ast.literal_eval(new_entry.change_speed_events) + kw_video_events['change_speed_events']
                    seek_from_events = ast.literal_eval(new_entry.seek_from_events) + kw_video_events['seek_from_events']
                    seek_to_events = ast.literal_eval(new_entry.seek_to_events) + kw_video_events['seek_to_events']   
                    print 'play_events'
                    print play_events
                    print change_speed_events
                    print seek_from_events
                    # Total values
                    new_entry.play_events = json.dumps(play_events)
                    new_entry.pause_events = json.dumps(pause_events)
                    new_entry.change_speed_events = json.dumps(change_speed_events)
                    new_entry.seek_from_events = json.dumps(seek_from_events)
                    new_entry.seek_to_events = json.dumps(seek_to_events)
                    
                except VideoEvents.DoesNotExist:
                    new_entry = VideoEvents(**kw_video_events)                
                new_entry.save()
    else:
        pass


##########################################################################
################ REPETITION OF VIDEO INTERVALS ###########################
##########################################################################


# Codigo Javier Orcoyen
# Add new histogram to the original one
def total_intervals (original_hist_xaxis, original_hist_yaxis, new_hist_xaxis, new_hist_yaxis):

    total_interval_start = []
    total_interval_end = []
    total_times_viewed = []
        
    # original_interval and new_interval will always have 2 elements [start, end]
    original_interval = []
    new_interval = []
    
    for index in range(0,len(new_hist_xaxis)-1):
        new_interval.append(new_hist_xaxis[index])
        new_interval.append(new_hist_xaxis[index+1])
        new_times_viewed = new_hist_yaxis[index]

        for index in range(0,len(original_hist_xaxis)-1):
            original_interval.append(original_hist_xaxis[index])
            original_interval.append(original_hist_xaxis[index+1])
            original_times_viewed = original_hist_yaxis[index]

            # new_interval inside original interval, for example [0,14] inside [0,15]
            if new_interval[0] >= original_interval[0] and new_interval[1] <= original_interval[1]:
                total_interval_start.append(new_interval[0])
                total_interval_end.append(new_interval[1])
                total_times_viewed.append(original_times_viewed+new_times_viewed)

            # new_interval partially outside original_interval, for example [10,20] partially inside [5,15]
            elif new_interval[0] >= original_interval[0] and new_interval[0] < original_interval[1] and new_interval[1] > original_interval[1]:
                total_interval_start.append(new_interval[0])
                total_interval_end.append(original_interval[1])
                total_times_viewed.append(original_times_viewed+new_times_viewed)

            # new_interval partially inside original_intervall, for example [0,10] partially inside [5,15] 
            elif new_interval[0] < original_interval[0] and new_interval[1] > original_interval[0] and new_interval[1] <= original_interval[1]:
                total_interval_start.append(original_interval[0])
                total_interval_end.append(new_interval[1])
                total_times_viewed.append(original_times_viewed+new_times_viewed)

            # new_interval contains original_interval, for example [0,20] contains [5,15]
            elif new_interval[0] < original_interval[0] and new_interval[1] > original_interval[1]:
                total_interval_start.append(original_interval[0])
                total_interval_end.append(original_interval[1])
                total_times_viewed.append(original_times_viewed+new_times_viewed)

            original_interval=[]
        new_interval=[]

    total_interval = total_interval_start + total_interval_end
    total_interval = list(set(total_interval))
    total_interval.sort()

    return total_interval, total_times_viewed


# Codigo Javier Orcoyen
# Add the new disjointed intervals to the original ones, indicating by id which student has seen each interval
# It is used in the one_stu_one_time entry of the table
def one_stu_one_time(original_ids, original_interval_start, original_interval_end, new_ids, new_interval_start, new_interval_end):
    
    # original_interval and new_interval will always have 2 elements [start, end]
    original_interval = []
    new_interval = []
    total_interval_start = []
    total_interval_end = []
    total_ids = []

    for new_index in range(0,len(new_ids)):
        new_interval.append(new_interval_start[new_index])
        new_interval.append(new_interval_end[new_index])
        new_id = new_ids[new_index]
        id_found = 0
        for original_index in range(0,len(original_ids)):
            original_id=original_ids[original_index]
            original_interval.append(original_interval_start[original_index])
            original_interval.append(original_interval_end[original_index])
            if new_id == original_id:
                id_found = 1
                # Interval inside another one, [10,20] in [0,30], [0,30] saved
                if new_interval[0] >= original_interval[0] and new_interval[1] <= original_interval[1]:
                    total_interval_start.append(original_interval[0])
                    total_interval_end.append(original_interval[1])
                    total_ids.append(new_id)

                # Interval inside and outside another one, [40,60] in [20,50], [20,60] saved
                elif new_interval[0] >= original_interval[0] and new_interval[0] < original_interval[1] and new_interval[1] > original_interval[1]:
                    total_interval_start.append(original_interval[0])
                    total_interval_end.append(new_interval[1])
                    total_ids.append(new_id)

                # Interval outside and inside another one, [0,30] in [20,50], [0,50] saved
                elif new_interval[0] < original_interval[0] and new_interval[1] > original_interval[0] and new_interval[1] <= original_interval[1]:
                    total_interval_start.append(new_interval[0])
                    total_interval_end.append(original_interval[1])
                    total_ids.append(new_id)

                # Interval contains another one, [0,50] in [20,30], [0,50] saved
                elif new_interval[0] < original_interval[0] and new_interval[1] > original_interval[1]:
                    total_interval_start.append(new_interval[0])
                    total_interval_end.append(new_interval[1])
                    total_ids.append(new_id)

                # Interval outside another one, [10,20] in [0,5], [10,20] and [0,5] saved
                else:
                    total_interval_start.append(new_interval[0])
                    total_interval_end.append(new_interval[1])
                    total_ids.append(new_id)
                    total_interval_start.append(original_interval[0])
                    total_interval_end.append(original_interval[1])
                    total_ids.append(original_id)

            # Rest of original intervals 
            else:
                total_interval_start.append(original_interval[0])
                total_interval_end.append(original_interval[1])
                total_ids.append(original_id)

            original_interval = []

        # Rest of new intervals
        if id_found == 0:
            total_interval_start.append(new_interval[0])
            total_interval_end.append(new_interval[1])
            total_ids.append(new_id)
           
        new_interval = []  

    # Check for repeated intervals (same id, interval_start and interval_end)
    total_interval_start, total_interval_end, total_ids = zip(*sorted(set(zip(total_interval_start, total_interval_end,total_ids))))
    total_interval_start = list(total_interval_start)
    total_interval_end = list(total_interval_end)
    total_ids = list(total_ids)    

    return total_interval_start, total_interval_end, total_ids


# Codigo Javier Orcoyen
# Check that there are no repeated intervals (starting with the same value) as only time wathed counts, not repetitions
# It is used in the one_stu_one_time entry of the table
def check_repeated_intervals_start (total_interval_start, total_interval_end, total_ids):

    final_total_interval_start=[]
    final_total_interval_end=[]
    final_total_ids = []

    set_total_ids = list(set(total_ids))

    for total_id in set_total_ids:
        
        filter_total_ids = [i for i, x in enumerate(total_ids) if total_ids.count(x) > 1 and total_ids[i] == total_id]
      
        if filter_total_ids != []:

            filter_total_interval_start = [total_interval_start[i] for i in filter_total_ids]
           
            set_filter_total_interval_start = list(set(filter_total_interval_start))
            set_filter_total_interval_start.sort()
   
            filter_total_interval_end = [total_interval_end[i] for i in filter_total_ids]

            for filter_total_interval_s in set_filter_total_interval_start:

                filter_total_interval_start_indexes = [i for i, x in enumerate(filter_total_interval_start) if filter_total_interval_start.count(x) > 1 and filter_total_interval_start[i] == filter_total_interval_s]

                if filter_total_interval_start_indexes != []:

                    filter_total_interval_end_repeated = [filter_total_interval_end[i] for i in filter_total_interval_start_indexes]

                    max_end = max(filter_total_interval_end_repeated)
                
                    final_total_ids.append(total_id)
                    final_total_interval_start.append(filter_total_interval_s)
                    final_total_interval_end.append(max_end)

                else: 
                    final_total_ids.append(total_id)
                    final_total_interval_start.append(filter_total_interval_s)
                    final_total_interval_end.append(filter_total_interval_end[set_filter_total_interval_start.index(filter_total_interval_s)])

        else:
            final_total_ids.append(total_id)
            final_total_interval_start.append(total_interval_start[total_ids.index(total_id)])
            final_total_interval_end.append(total_interval_end[total_ids.index(total_id)])

    final_total_interval_start, final_total_interval_end, final_total_ids = sort_intervals_ids(final_total_interval_start, final_total_interval_end, final_total_ids)
 
    return final_total_interval_start, final_total_interval_end, final_total_ids


# Codigo Javier Orcoyen
# Check that there are no repeated intervals (ending in the same value) as only time wathed counts, not repetitions
# It is used in the one_stu_one_time entry of the table
def check_repeated_intervals_end (total_interval_start, total_interval_end, total_ids):

    final_total_interval_start=[]
    final_total_interval_end=[]
    final_total_ids = []

    set_total_ids = list(set(total_ids))

    for total_id in set_total_ids:
        
        filter_total_ids = [i for i, x in enumerate(total_ids) if total_ids.count(x) > 1 and total_ids[i] == total_id]
      
        if filter_total_ids != []:

            filter_total_interval_end = [total_interval_end[i] for i in filter_total_ids]
           
            set_filter_total_interval_end = list(set(filter_total_interval_end))
            set_filter_total_interval_end.sort()
   
            filter_total_interval_start = [total_interval_start[i] for i in filter_total_ids]

            for filter_total_interval_e in set_filter_total_interval_end:

                filter_total_interval_end_indexes = [i for i, x in enumerate(filter_total_interval_end) if filter_total_interval_end.count(x) > 1 and filter_total_interval_end[i] == filter_total_interval_e]

                if filter_total_interval_end_indexes != []:

                    filter_total_interval_start_repeated = [filter_total_interval_start[i] for i in filter_total_interval_end_indexes]

                    min_start = min(filter_total_interval_start_repeated)
                  
                    final_total_ids.append(total_id)
                    final_total_interval_start.append(min_start)
                    final_total_interval_end.append(filter_total_interval_e)
                    
                else: 
                    final_total_ids.append(total_id)
                    final_total_interval_start.append(filter_total_interval_start[set_filter_total_interval_end.index(filter_total_interval_e)])
                    final_total_interval_end.append(filter_total_interval_e)

        else:
            final_total_ids.append(total_id)
            final_total_interval_start.append(total_interval_start[total_ids.index(total_id)])
            final_total_interval_end.append(total_interval_end[total_ids.index(total_id)])

    final_total_interval_start, final_total_interval_end, final_total_ids = sort_intervals_ids(final_total_interval_start, final_total_interval_end, final_total_ids)
 
    return final_total_interval_start, final_total_interval_end, final_total_ids


# Codigo Javier Orcoyen
def update_DB_repetition_video_intervals(course_key=None):
    # course_key should be a course_key

    kw_video_intervals = {
        'student': '',
        'course_key': course_key,
        'module_key': '',        
        'display_name': '',
        'hist_xaxis': '',
        'hist_yaxis': '', 
        'interval_start':'',
        'interval_end':'',
        'ids':'',       
    }
    
    if course_key is not None:
        # update data for the provided course
        
        course = get_course_by_id(course_key, depth=None)
        usernames_in = [x.username.encode('utf-8') for x in CourseEnrollment.objects.users_enrolled_in(course_key)]#Codigo J.A.Gascon
        ids_in = [x.id for x in CourseEnrollment.objects.users_enrolled_in(course_key)]#Codigo J.A.Gascon
        videos_in = videos_problems_in(course)[0]
        video_names, video_module_keys, video_durations = get_info_videos_descriptors(videos_in)
        
        # List of UserVideoIntervals
        users_video_intervals = []
        users_with_video_events = []
        users_with_video_events_video_ids = []
        users_with_video_events_video_names = []
        users_with_video_events_ids = []
        users_intervals_ids = []
        
        for username_in in usernames_in:
            for video_module_key in video_module_keys:
                interval_start, interval_end, vid_start_time, vid_end_time = find_video_intervals(course_key,username_in, video_module_key, 'videoIntervalsRepetition')
                if interval_start is not None and interval_end is not None and vid_start_time is not None and vid_end_time is not None:
                    # If a user has events for more than one video, his name will be repeated in users_with_video_events
                    users_with_video_events.append(username_in)
                    # If a user has events for more than one video, his id will be repeated in users_with_video_events_ids
                    users_with_video_events_ids.append(ids_in[usernames_in.index(username_in)])
                    # Video info will be in the same index in as video_module_key in video_module_keys
                    index_video = video_module_keys.index(video_module_key)
                    # Save the id of the video for which the user has new events
                    users_with_video_events_video_ids.append(video_module_keys[index_video])
                    # Save the name of the video for which the user has new events
                    users_with_video_events_video_names.append(video_names[index_video])
                    disjointed_start, disjointed_end = video_len_watched(interval_start, interval_end)
                    users_video_intervals.append(UserVideoIntervals(username_in, video_module_key, 
                                                               interval_start, interval_end,
                                                               vid_start_time, vid_end_time,
                                                               disjointed_start, disjointed_end))      

        # VideoIntervals table data
        for video_name, video_id in zip(video_names, video_module_keys):
            accum_interval_start = []
            accum_interval_end = []
            accum_disjointed_start = []
            accum_disjointed_end = []          
            kw_video_intervals['module_key'] = video_id
            kw_video_intervals['display_name'] = video_name
            for index, username_in in enumerate(users_with_video_events):
                kw_video_intervals['student'] = username_in      
                if video_id==users_with_video_events_video_ids[index] and video_name==users_with_video_events_video_names[index]:
                    new_interval_start = users_video_intervals[index].interval_start
                    new_interval_end = users_video_intervals[index].interval_end
                    accum_interval_start += new_interval_start
                    accum_interval_end += new_interval_end
                    accum_disjointed_start += users_video_intervals[index].disjointed_start
                    accum_disjointed_end += users_video_intervals[index].disjointed_end 
                    for i in range(0,len(users_video_intervals[index].disjointed_start)):
                        users_intervals_ids.append(users_with_video_events_ids[index])               
                    new_hist_xaxis, new_hist_yaxis = histogram_from_intervals(new_interval_start, new_interval_end, video_durations[video_module_keys.index(video_id)])

                    kw_video_intervals['hist_xaxis'] = json.dumps(new_hist_xaxis)
                    kw_video_intervals['hist_yaxis'] = json.dumps(new_hist_yaxis)

                    if new_hist_xaxis != [] and new_hist_yaxis != []: 

                        try:
                            new_entry = VideoIntervals.objects.get(student=kw_video_intervals['student'], module_key=kw_video_intervals['module_key'])
                         
                            total_hist_xaxis, total_hist_yaxis = total_intervals(ast.literal_eval(new_entry.hist_xaxis), ast.literal_eval(new_entry.hist_yaxis), new_hist_xaxis, new_hist_yaxis)
                        
                            new_entry.hist_xaxis = json.dumps(total_hist_xaxis)
                            new_entry.hist_yaxis = json.dumps(total_hist_yaxis)

                        except VideoIntervals.DoesNotExist:
                            new_entry = VideoIntervals(**kw_video_intervals)        
                        new_entry.save()

            # Total times these video intervals have been viewed
            kw_video_intervals['student'] = '#class_total_times'
            
            if accum_interval_start != [] and accum_interval_end != []:
                new_interval_start, new_interval_end = sort_intervals(accum_interval_start, accum_interval_end)
                new_hist_xaxis, new_hist_yaxis = histogram_from_intervals(new_interval_start, new_interval_end, video_durations[video_module_keys.index(video_id)])
               
                kw_video_intervals['hist_xaxis'] = json.dumps(new_hist_xaxis)
                kw_video_intervals['hist_yaxis'] = json.dumps(new_hist_yaxis)

                try:
                    new_entry = VideoIntervals.objects.get(student=kw_video_intervals['student'], module_key=kw_video_intervals['module_key'])
      
                    total_hist_xaxis, total_hist_yaxis = total_intervals(ast.literal_eval(new_entry.hist_xaxis), ast.literal_eval(new_entry.hist_yaxis), new_hist_xaxis, new_hist_yaxis)
                    
                    new_entry.hist_xaxis = json.dumps(total_hist_xaxis)
                    new_entry.hist_yaxis = json.dumps(total_hist_yaxis)

                except VideoIntervals.DoesNotExist:
                    new_entry = VideoIntervals(**kw_video_intervals)                    
                new_entry.save()
            
            # Total times these video intervals have been viewed
            # Every student counts a single time
            kw_video_intervals['student'] = '#one_stu_one_time'
            
            if accum_disjointed_start != [] and accum_disjointed_end != []:
                new_interval_start, new_interval_end, new_ids = sort_intervals_ids(accum_disjointed_start, accum_disjointed_end, users_intervals_ids)
               
                kw_video_intervals['interval_start'] = json.dumps(new_interval_start)
                kw_video_intervals['interval_end'] = json.dumps(new_interval_end)
                kw_video_intervals['ids'] = json.dumps(new_ids)

                new_hist_xaxis, new_hist_yaxis = histogram_from_intervals(new_interval_start, new_interval_end, video_durations[video_module_keys.index(video_id)])
                
                kw_video_intervals['hist_xaxis'] = json.dumps(new_hist_xaxis)
                kw_video_intervals['hist_yaxis'] = json.dumps(new_hist_yaxis)

                try:
                    new_entry = VideoIntervals.objects.get(student=kw_video_intervals['student'], module_key=kw_video_intervals['module_key'])
         
                    total_interval_start, total_interval_end, total_ids = one_stu_one_time(ast.literal_eval(new_entry.ids), ast.literal_eval(new_entry.interval_start), ast.literal_eval(new_entry.interval_end), new_ids, new_interval_start, new_interval_end)

                    total_interval_start, total_interval_end, total_ids = sort_intervals_ids(total_interval_start, total_interval_end, total_ids)

                    total_interval_start, total_interval_end, total_ids = check_repeated_intervals_start (total_interval_start, total_interval_end, total_ids)

                    total_interval_start, total_interval_end, total_ids = check_repeated_intervals_end (total_interval_start, total_interval_end, total_ids)

                    total_hist_xaxis, total_hist_yaxis = histogram_from_intervals(total_interval_start, total_interval_end, video_durations[video_module_keys.index(video_id)])

                    new_entry.hist_xaxis = json.dumps(total_hist_xaxis)
                    new_entry.hist_yaxis = json.dumps(total_hist_yaxis)
                    new_entry.interval_start = json.dumps(total_interval_start)
                    new_entry.interval_end = json.dumps(total_interval_end)
                    new_entry.ids = json.dumps(total_ids)

                except VideoIntervals.DoesNotExist:
                    new_entry = VideoIntervals(**kw_video_intervals)                    
                new_entry.save()

                kw_video_intervals['interval_start'] = ''
                kw_video_intervals['interval_end'] = ''
                kw_video_intervals['ids'] = ''

            users_intervals_ids=[]

    else:
        pass


##########################################################################
###################### VIDEO TIME WATCHED ################################
##########################################################################


# Codigo Javier Orcoyen
def find_new_intervals(original_interval_start, original_interval_end, new_interval_start, new_interval_end):
    
    # original_interval and new_interval will always have 2 elements [start, end]
    original_interval = []
    new_interval = []
    total_interval_start = []
    total_interval_end = []

    for new_index in range(0,len(new_interval_start)):
        new_interval.append(new_interval_start[new_index])
        new_interval.append(new_interval_end[new_index])
        is_new_interval = 0
        
        for original_index in range(0,len(original_interval_start)):
            original_interval.append(original_interval_start[original_index])
            original_interval.append(original_interval_end[original_index])
           
            # Interval inside another one, [10,20] in [0,30], skip
            #if new_interval[0] >= original_interval[0] and new_interval[1] <= original_interval[1]:
              
            # Interval inside and outside another, [40,60] in [20,50], [50,60] saved
            if new_interval[0] > original_interval[0] and new_interval[0] <= original_interval[1] and new_interval[1] > original_interval[1]:
                total_interval_start.append(original_interval[1])
                total_interval_end.append(new_interval[1])
                    
            # Interval outside and inside another one, [0,30] in [20,50], [0,20] saved
            elif new_interval[0] < original_interval[0] and new_interval[1] >= original_interval[0] and new_interval[1] < original_interval[1]:
                total_interval_start.append(new_interval[0])
                total_interval_end.append(original_interval[0])
                
            # Interval contains another one, [0,50] in [20,30], [0,20] and [30,50] saved
            elif new_interval[0] < original_interval[0] and new_interval[1] > original_interval[1]:
                total_interval_start.append(new_interval[0])
                total_interval_end.append(original_interval[0])
                total_interval_start.append(original_interval[1])
                total_interval_end.append(new_interval[1])
                   
            # Interval outside another one, [10,20] in [0,5], [10,20] saved
            elif new_interval[1] < original_interval[0] or new_interval[0] > original_interval[1]:
                is_new_interval+=1

            original_interval = []

        # Check for adding a complete new interval ([10,20] in [0,5], save [10,20]
        if is_new_interval == len(original_interval_start):
             total_interval_start.append(new_interval[0])
             total_interval_end.append(new_interval[1])
           
        new_interval = []      

    indexes = []

    # If there are new viewed intervals
    if total_interval_start != [] and total_interval_end != []:

        if len(total_interval_start) > 1 and len(total_interval_end) > 1:
            # Save the indexes of values that neeed to be removed
            for index in range(0,len(total_interval_start)-1):
                if total_interval_end[index] > total_interval_start[index+1]:
                    indexes.append(index)
        
            # Remove indexes in idx for total_interval_start and total_interval_end backwards (reverse order for not reindexing)
            for i in sorted(indexes, reverse=True):
                del total_interval_start[i+1]
                del total_interval_end[i]

    else:
        total_interval_start = None
        total_interval_end = None
   
    return total_interval_start, total_interval_end   


# Codigo Javier Orcoyen
def add_intervals(original_interval_start, original_interval_end, new_interval_start, new_interval_end):
  
    # original_interval and new_interval will always have 2 elements [start, end]
    original_interval = []
    new_interval = []
    total_interval_start = []
    total_interval_end = []

    for new_index in range(0,len(new_interval_start)):
        new_interval.append(new_interval_start[new_index])
        new_interval.append(new_interval_end[new_index])
        is_new_interval = 0
       
        for original_index in range(0,len(original_interval_start)):
            original_interval.append(original_interval_start[original_index])
            original_interval.append(original_interval_end[original_index])
            
            # Intervalo dentro de otro, [10,20] en [0,30], se queda [0,30]
            if new_interval[0] >= original_interval[0] and new_interval[1] <= original_interval[1]:
                
                total_interval_start.append(original_interval[0])
                total_interval_end.append(original_interval[1])
    
            # Intervalo dentro y fuera de otro, [40,60] en [20,50], quedaria [20,60]
            elif new_interval[0] >= original_interval[0] and new_interval[0] < original_interval[1] and new_interval[1] > original_interval[1]:
                
                total_interval_start.append(original_interval[0])
                total_interval_end.append(new_interval[1])
                    
            # Intervalo fuera y dentro de otro, [0,30] en [20,50], quedaria [0,50]
            elif new_interval[0] < original_interval[0] and new_interval[1] > original_interval[0] and new_interval[1] <= original_interval[1]:
                
                total_interval_start.append(new_interval[0])
                total_interval_end.append(original_interval[1])
                
            # Intervalo contiene a otro, [0,50] en [20,30], quedaria [0,50]
            elif new_interval[0] < original_interval[0] and new_interval[1] > original_interval[1]:
                
                total_interval_start.append(new_interval[0])
                total_interval_end.append(new_interval[1])
                   
            # Intervalo fuera de otro, [10,20] en [0,5], quedaria [10,20] y [0,5]
            else:
               
                is_new_interval+=1
                total_interval_start.append(original_interval[0])
                total_interval_end.append(original_interval[1])

            original_interval = []
   
        if is_new_interval == len(original_interval_start):
             total_interval_start.append(new_interval[0])
             total_interval_end.append(new_interval[1])
           
        new_interval = []      

    # Repeated intervals
    total_interval_start, total_interval_end = zip(*sorted(set(zip(total_interval_start, total_interval_end))))
    total_interval_start = list(total_interval_start)
    total_interval_end = list(total_interval_end)

    # Intervals starting with the same value
    final_total_interval_start=[]
    final_total_interval_end=[]

    set_total_interval_start = list(set(total_interval_start))
    set_total_interval_start.sort()
    
    for total_interval_s in set_total_interval_start:

        total_interval_start_indexes = [i for i, x in enumerate(total_interval_start) if total_interval_start.count(x) > 1 and total_interval_start[i] == total_interval_s]
      
        if total_interval_start_indexes != []:

            total_interval_end_repeated = [total_interval_end[i] for i in total_interval_start_indexes]
            
            max_end = max(total_interval_end_repeated)

            final_total_interval_start.append(total_interval_s)
            final_total_interval_end.append(max_end)

        else: 
            final_total_interval_start.append(total_interval_s)
            final_total_interval_end.append(total_interval_end[total_interval_start.index(total_interval_s)])

    # Intervals ending in the same value
    final_total_interval_start_final=[]
    final_total_interval_end_final=[]

    set_total_interval_end = list(set(total_interval_end))
    set_total_interval_end.sort()
    
    for total_interval_e in set_total_interval_end:

        total_interval_end_indexes = [i for i, x in enumerate(total_interval_end) if total_interval_end.count(x) > 1 and total_interval_end[i] == total_interval_e]
      
        if total_interval_end_indexes != []:

            total_interval_start_repeated = [total_interval_start[i] for i in total_interval_end_indexes]
            
            min_start = min(total_interval_start_repeated)

            final_total_interval_start_final.append(min_start)
            final_total_interval_end_final.append(total_interval_e)

        else:
            final_total_interval_start_final.append(total_interval_start[total_interval_end.index(total_interval_e)])
            final_total_interval_end_final.append(total_interval_e)

    # Make intervals into disjointed intervals
    indexes = []

    if len(final_total_interval_start_final) > 1 and len(final_total_interval_end_final) > 1:
        # Save the indexes of values that neeed to be removed
        for index in range(0,len(final_total_interval_start_final)-1):
            if final_total_interval_end_final[index] == final_total_interval_start_final[index+1]:
                indexes.append(index)
        
        # Remove indexes in idx for total_interval_start and total_interval_end backwards (reverse order for not reindexing)
        for i in sorted(indexes, reverse=True):
            del final_total_interval_start_final[i+1]
            del final_total_interval_end_final[i]

    return final_total_interval_start_final, final_total_interval_end_final



# Codigo Javier Orcoyen
# Returns video consumption non-overlapped (%) 
# for a certain student relative time watched for 
# a video with a certain duration
def video_percentage(disjointed_start, disjointed_end, video_duration):
    
    # Non-overlapped video time
    stu_video_seen = []   
    interval_sum = 0
    for start, end in zip(disjointed_start,disjointed_end):
        interval_sum += end - start           
    stu_video_seen = interval_sum
        
    video_percentage = truediv(stu_video_seen, video_duration)
    video_percentage = int(round(video_percentage*100,0)) 

    # Artificially ensures percentages do not surpass 100%, which
    # could happen slightly from the 1s adjustment in id_to_length function
    if video_percentage > 100:
        video_percentage = 100
  
    return video_percentage


# Codigo Javier Orcoyen
def update_DB_video_time_watched(course_key=None):
    # course_key should be a course_key
  
    kw_video_time_watched = {
        'student': '',
        'course_key': course_key,
        'module_key': '',
        'display_name': '',
        'percent_viewed': 0,
        'total_time': 0,
        'disjointed_start': '',
        'disjointed_end': '',
    }
    
    if course_key is not None:
        # update data for the provided course
        
        course = get_course_by_id(course_key, depth=None)
        usernames_in = [x.username.encode('utf-8') for x in CourseEnrollment.objects.users_enrolled_in(course_key)]#Codigo J.A.Gascon
        videos_in = videos_problems_in(course)[0]
        #print 'videos_IN'
        #print videos_in
        video_names, video_module_keys, video_durations = get_info_videos_descriptors(videos_in)
        #print 'VIDEOS'
        #print video_names 
        #print video_module_keys
        #print video_durations
        # List of UserVideoIntervals
        users_video_intervals = []
        users_with_video_events = []
        users_with_video_events_video_ids = []
        users_with_video_events_video_names = []
        users_with_video_events_video_durations = []
        indexes = []
        
        for username_in in usernames_in:
            for video_module_key in video_module_keys:
                interval_start, interval_end, vid_start_time, vid_end_time = find_video_intervals(course_key,username_in, video_module_key, 'videoTimeWatched')
                # Just users with video events
                if interval_start is not None and interval_end is not None and vid_start_time is not None and vid_end_time is not None:
                    # If a user has events for more than one video, his name will be repeated in users_with_video_events
                    users_with_video_events.append(username_in)
                    # Video info will be in the same index in as video_module_key in video_module_keys
                    index_video = video_module_keys.index(video_module_key)
                    indexes.append(index_video)
                    #print 'INDEX_VIDEO'
                    #print index_video
                    # Save the id of the video for which the user has new events
                    users_with_video_events_video_ids.append(video_module_keys[index_video])
                    # Save the name of the video for which the user has new events
                    users_with_video_events_video_names.append(video_names[index_video])
                    # Save the duration of the video for which the user has new events
                    users_with_video_events_video_durations.append(video_durations[index_video])
                    disjointed_start, disjointed_end = video_len_watched(interval_start, interval_end)
                    users_video_intervals.append(UserVideoIntervals(username_in, video_module_key, 
                                                               interval_start, interval_end,
                                                               vid_start_time, vid_end_time,
                                                               disjointed_start, disjointed_end))         
        # VideoTimeWatched table data
        accum_video_percentages = [0] * len(video_module_keys)
        accum_all_video_time = [0] * len(video_module_keys)
        
        # Delete repeated values
        sorted_users_with_video_events = sorted(set(users_with_video_events))
        
        for username_in in sorted_users_with_video_events:
            kw_video_time_watched['student'] = username_in     
            # video_percentages (in %), all_video_time (in seconds)
            low_index = users_with_video_events.index(username_in)
            high_index = low_index + users_with_video_events.count(username_in)
            
            # Video id, name and duration of each video for which the user has new events
            user_video_ids = users_with_video_events_video_ids[low_index:high_index]
            user_video_names = users_with_video_events_video_names[low_index:high_index]
            video_durations = users_with_video_events_video_durations[low_index:high_index]
            video_indexes = indexes[low_index:high_index]
            user_video_intervals = users_video_intervals[low_index:high_index]

            video_percentages, all_video_time = video_consumption(users_video_intervals[low_index:high_index], video_durations)

            if video_percentages is not None and all_video_time is not None:
                for i in range(0,len(user_video_ids)):
                    
                    kw_video_time_watched['module_key'] = user_video_ids[i]
                    kw_video_time_watched['display_name'] = user_video_names[i]
                    kw_video_time_watched['percent_viewed'] = video_percentages[i]
                    kw_video_time_watched['total_time'] = all_video_time[i]
                    kw_video_time_watched['disjointed_start'] = json.dumps(user_video_intervals[i].disjointed_start)
                    kw_video_time_watched['disjointed_end'] =  json.dumps(user_video_intervals[i].disjointed_end)

                    try:
                        new_entry = VideoTimeWatched.objects.get(student=kw_video_time_watched['student'], module_key=kw_video_time_watched['module_key'])
 
                        new_disjointed_start, new_disjointed_end = find_new_intervals(ast.literal_eval(new_entry.disjointed_start), ast.literal_eval(new_entry.disjointed_end), user_video_intervals[i].disjointed_start, user_video_intervals[i].disjointed_end)
                        
                        if new_disjointed_start != None and new_disjointed_end != None:
                            
                            # funcion video_percentage calcula tiempo total, no progreso en el video.
                            # Para calcular el progreso del vide, necesitas intervalos e intervalos nuevos, no puedes sumar porcentajes (ESTO PARECE Q ESTA BIEN)
                            new_percentage_viewed = video_percentage(new_disjointed_start, new_disjointed_end, video_durations[i])
                        
                            new_entry.percent_viewed = new_entry.percent_viewed + new_percentage_viewed
                            new_entry.total_time = new_entry.total_time + kw_video_time_watched['total_time']

                            total_disjointed_start, total_disjointed_end = add_intervals(ast.literal_eval(new_entry.disjointed_start), ast.literal_eval(new_entry.disjointed_end), new_disjointed_start, new_disjointed_end)
                    
                            new_entry.disjointed_start = json.dumps(total_disjointed_start)
                            new_entry.disjointed_end = json.dumps(total_disjointed_end)

                            accum_video_percentages[video_indexes[i]] += new_percentage_viewed

                    except VideoTimeWatched.DoesNotExist:
                        new_entry = VideoTimeWatched(**kw_video_time_watched)
                        accum_video_percentages[video_indexes[i]] += video_percentages[i]

                    new_entry.save()
                  
                    accum_all_video_time[video_indexes[i]] += all_video_time[i]

        # average values
        if accum_video_percentages != [] and accum_all_video_time != []:
            kw_video_time_watched['student'] = '#average'               
            for i in range(0,len(accum_all_video_time)):
                if accum_all_video_time[i] != 0:
                    #accum_all_video_time[i] = int(round(truediv(accum_all_video_time[i],len(usernames_in)),0))
                    kw_video_time_watched['module_key'] = video_module_keys[i]
                    kw_video_time_watched['display_name'] = video_names[i]                 
                    accum_video_percentages[i] = int(round(truediv(accum_video_percentages[i],len(usernames_in)),0))
                    kw_video_time_watched['percent_viewed'] = accum_video_percentages[i]
                    kw_video_time_watched['total_time'] = accum_all_video_time[i]
                    kw_video_time_watched['disjointed_start'] = ''
                    kw_video_time_watched['disjointed_end'] = ''
                    try:
                        new_entry = VideoTimeWatched.objects.get(student=kw_video_time_watched['student'], module_key=kw_video_time_watched['module_key'])

                        new_entry.percent_viewed = new_entry.percent_viewed + kw_video_time_watched['percent_viewed']
                        new_entry.total_time = new_entry.total_time + kw_video_time_watched['total_time']

                    except VideoTimeWatched.DoesNotExist:
                        new_entry = VideoTimeWatched(**kw_video_time_watched)            
                    new_entry.save()
    else:
        pass


############################# VIDEO EVENTS ###############################
 

# Given a video descriptor returns ORDERED the video intervals a student has seen
# A timestamp of the interval points is also recorded.
def find_video_intervals(course_key, student, video_module_id, indicator):
    
    #event flags to check for duplicity
    play_flag = False # True: last event was a play_videoid
    seek_flag = False # True: last event was a seek_video
    saved_video_flag = False # True: last event was a saved_video_position
    
    interval_start = []
    interval_end = []
    vid_start_time = [] # timestamp for interval_start
    vid_end_time = []   # timestamp for interval_end
    
    events = get_new_module_events_sql(course_key, student, video_module_id, indicator, None)
    
    last_viewing_end_event = None
    viewing = None
    #import ciso8601
    #for event in events:
    #    print event

    #print 'events FINDVIDEOINTERVALS'
    #print events
    if events is None:
        return None, None, None, None

    if events.count() <= 0:
        # return description: [interval_start, interval_end, vid_start_time, vid_end_time]
        # return list types: [int, int, datetime.date, datetime.date]
        return None, None, None, None
    #guarantee the list of events starts with a play_video
    while events[0].event_type != 'play_video':
        events = events[1:]
        if len(events) < 2:
            return None, None, None, None
    for event in events:
        if event.event_type == 'play_video':
            if play_flag: # two consecutive play_video events. Second is the relevant one (loads saved_video_position).
                interval_start.pop() #removes last element
                vid_start_time.pop()
            if not seek_flag:
                interval_start.append(eval(event.event)['currentTime'])
                vid_start_time.append(event.time)
            play_flag = True
            seek_flag = False
            saved_video_flag = False
        elif event.event_type == 'seek_video':
            if seek_flag:
                interval_start.pop()
                vid_start_time.pop()
            elif play_flag:
                interval_end.append(eval(event.event)['old_time'])
                vid_end_time.append(event.time)
            interval_start.append(eval(event.event)['new_time'])
            vid_start_time.append(event.time)
            play_flag = False
            seek_flag = True
            saved_video_flag = False
        else: # .../save_user_state
            if play_flag:
                interval_end.append(hhmmss_to_secs(eval(event.event)['POST']['saved_video_position'][0]))
                vid_end_time.append(event.time)
            elif seek_flag:
                interval_start.pop()
                vid_start_time.pop()
            play_flag = False
            seek_flag = False
            saved_video_flag = True
    interval_start = [int(math.floor(val)) for val in interval_start]
    interval_end   = [int(math.floor(val)) for val in interval_end]
    #remove empty intervals (start equals end) and guarantee start < end 
    interval_start1 = []
    interval_end1 = []
    vid_start_time1 = []
    vid_end_time1 = []
    for start_val, end_val, start_time, end_time in zip(interval_start, interval_end, vid_start_time, vid_end_time):
        if start_val < end_val:
            interval_start1.append(start_val)
            interval_end1.append(end_val)
            vid_start_time1.append(start_time)
            vid_end_time1.append(end_time)
        elif start_val > end_val: # case play from video end
            interval_start1.append(0)
            interval_end1.append(end_val)
            vid_start_time1.append(start_time)
            vid_end_time1.append(end_time)            
    # sorting intervals
    if len(interval_start1) <= 0:
        return None, None, None, None
    [interval_start, interval_end, vid_start_time, vid_end_time] = zip(*sorted(zip(interval_start1, interval_end1, vid_start_time1, vid_end_time1)))
    interval_start = list(interval_start)
    interval_end = list(interval_end)
    vid_start_time = list(vid_start_time)
    vid_end_time = list(vid_end_time)
    
    # return list types: [int, int, datetime.date, datetime.date]
    return interval_start, interval_end, vid_start_time, vid_end_time    
    

# Obtain list of events relative to videos and their relative position within the video
# For a single student
# CT Current time
# Return format: [[CTs for play], [CTs for pause], [CTs for speed changes], [old_time list], [new_time list]]
# Returns None if there are no events matching criteria
def get_video_events_times(course_key, student, video_module_id):

    INVOLVED_EVENTS = [
        'play_video',
        'pause_video',
        'speed_change_video',
        'seek_video'
    ]
  
    events = get_new_module_events_sql(course_key, student, video_module_id, 'videoEvents', None)

    if events is None:
        return None
    
    # List of lists. A list for every event type containing the video relative time    
    events_times = []
    for event in INVOLVED_EVENTS + ['list for seek new_time']:
        events_times.append([])
        
    for event in events:
        currentTime = get_current_time(event)
        events_times[INVOLVED_EVENTS.index(event.event_type)].append(currentTime[0])
        if len(currentTime) > 1: # save new_time for seek_video event
            events_times[-1].append(currentTime[1])
    
    return events_times

    
##########################################################################
############################ PROBLEM EVENTS ##############################
##########################################################################  
    

# Computes the time a student has dedicated to a problem in seconds
#TODO Does it make sense to change the resolution to minutes?
# Returns also daily time spent on a problem by the user
def time_on_problem(course_key, student, problem_module_id, indicator):
    
    INVOLVED_EVENTS = [
        'seq_goto',
        'seq_prev',
        'seq_next',
        'page_close'
    ]
    #print course_key
    #print student
    #print problem_module_id
    #print indicator
    events = get_new_module_events_sql(course_key, student, problem_module_id, indicator, None)
    #print 'events'
    #print events
    if events is None:
        #print 'EXCEPTION'
        return None, None, None
    #Codigo J Antonio Gascon
    if len(events) <= 0:
        # return description: [problem_time, days, daily_time]
        # return list types: [int, datetime.date, int]
        return None, None, None
    
    # Ensure pairs problem_get - INVOLVED_EVENTS (start and end references)
    event_pairs = []
    # Flag to control the pairs. get_problem = True means get_problem event expected
    get_problem = True
    for event in events:
        #print 'event_type'
        #print event.event_type
        if get_problem: # looking for a get_problem event
            #print re.search('problem_get$',event.event_type)
            if re.search('problem_get$',event.event_type) is not None:

                event_pairs.append(event.time)
                #print 'Consigue problem_get'
                #print event_pairs
                #print event.time
                get_problem = False
        else:# looking for an event in INVOLVED_EVENTS
            if event.event_type in INVOLVED_EVENTS: 
                #print 'Consigue otros seq_goto,seq_prev, seq_next o page_close'
                event_pairs.append(event.time)
                #print event_pairs
                #print event.time 
                get_problem = True
        #print 'EVENTOS DE TIEMPO'
        #print 'event_type'
        #print event.event_type
        #print event_pairs
        #print event.time
        
    problem_time = 0
    """
    if len(event_pairs) > 0:
        for index in range(0, len(event_pairs), 2):
    """
    i = 0
    while i < len(event_pairs) - 1:        
        time_fraction = (event_pairs[i+1] - event_pairs[i]).total_seconds()
        print 'EVENTOS'
        print student
        print event_pairs[i+1]
        print event_pairs[i]
        print time_fraction
        #TODO Bound time fraction to a reasonable value. Here 2 hours. What would be a reasonable maximum?
        time_fraction = 2*60*60 if time_fraction > 2*60*60 else time_fraction
        problem_time += time_fraction
        i += 2
            
    # Daily info
    days = [event_pairs[0].date()] if len(event_pairs) >= 2 else []
#    for event in event_pairs:
#        days.append(event.date())
    daily_time = [0]
    i = 0
    while i < len(event_pairs) - 1:
        if days[-1] == event_pairs[i].date(): # another interval to add to the same day
            if event_pairs[i+1].date() == event_pairs[i].date(): # the interval belongs to a single day
                daily_time[-1] += (event_pairs[i+1] - event_pairs[i]).total_seconds()
            else: # interval extrems lay on different days. E.g. starting on day X at 23:50 and ending the next day at 0:10. 
                daily_time[-1] += 24*60*60 - event_pairs[i].hour*60*60 - event_pairs[i].minute*60 - event_pairs[i].second
                days.append(event_pairs[i+1].date())
                daily_time.append(event_pairs[i+1].hour*60*60 + event_pairs[i+1].minute*60 + event_pairs[i+1].second)
        else:
            days.append(event_pairs[i].date())
            daily_time.append(0)
            if event_pairs[i+1].date() == event_pairs[i].date(): # the interval belongs to a single day
                daily_time[-1] += (event_pairs[i+1] - event_pairs[i]).total_seconds()
            else: # interval extrems lay on different days. E.g. starting on day X at 23:50 and ending the next day at 0:10.
                daily_time[-1] += 24*60*60 - event_pairs[i].hour*60*60 - event_pairs[i].minute*60 - event_pairs[i].second
                days.append(event_pairs[i+1].date())
                daily_time.append(event_pairs[i+1].hour*60*60 + event_pairs[i+1].minute*60 + event_pairs[i+1].second)            
        i += 2
    return problem_time, days, daily_time


##########################################################################
##########################################################################
##########################################################################


# Codigo Javier Orcoyen
# Get info for Problem and Video time distribution charts
def get_module_consumption(username, course_id, module_type):
  
    #shortlist criteria
    shortlist = Q(student=username, course_key=course_id, module_type = module_type)
    consumption_modules = ConsumptionModule.objects.filter(shortlist)
    module_names = []
    total_times = []    
    
    for consumption_module in consumption_modules:
        module_names.append(consumption_module.display_name)
        
        # From minutes to seconds              
        total_times.append(round(truediv(consumption_module.total_time,60),2))
            
    if sum(total_times) <= 0:
        total_times = []

    return module_names, total_times


# Codigo Javier Orcoyen
# Get info for Video time watched chart
def get_video_time_watched(username, course_id):
  
    course = get_course_by_id(course_id, depth=None)
    videos_in = videos_problems_in(course)[0]
    video_names = get_info_videos_descriptors(videos_in)[0]

    #shortlist criteria
    shortlist = Q(student=username, course_key=course_id)
    consumption_modules = VideoTimeWatched.objects.filter(shortlist)
    module_names = []
    #NO SALE ERROR PERO SIGUE SIN CALCULARLO BIEN
    total_times = [0]*len(video_names)    
    video_percentages = [0]*len(video_names)

    for k,consumption_module in enumerate(consumption_modules):

        index = video_names.index(consumption_module.display_name)
        #print 'index'
        #print index
        module_names.append(consumption_module.display_name)               
        video_percentages[index]=consumption_module.percent_viewed
        if(username == '#average'):
            # Dividing total time between the number of students to get avg time on video which is used in video progress
            total_times[index]=int(round(truediv(consumption_module.total_time,len(CourseEnrollment.objects.users_enrolled_in(course_id))),0))
        else:
            total_times[index]=consumption_module.total_time
    
    if len(module_names) < len(video_names):
        total_total_times = [0]*len(video_names)
        total_video_percentages = [0]*len(video_names)
        
        indexes = [video_names.index(i) for i in module_names]
        print 'indexes'
        print indexes
        print total_total_times
        print total_times
        for i in indexes:
            total_total_times[i] = total_times[i]
            total_video_percentages[i] = video_percentages[i]
    else:
        total_total_times = total_times
        total_video_percentages = video_percentages
            
    if sum(total_total_times) <= 0:
        total_total_times = []
        total_video_percentages = []
    return video_names, total_total_times, total_video_percentages


# Get info for Daily time on video and problems chart
# Daily time spent on video and problem resources
def get_daily_consumption(username, course_id, module_type):

    #shortlist criteria
    #shortlist = Q(student=username, course_key=course_id, module_type = module_type)
    try:
        daily_consumption = DailyConsumption.objects.get(student=username, course_key=course_id, module_type = module_type)
        jsonDec = json.decoder.JSONDecoder()
        days = jsonDec.decode(daily_consumption.dates)
        # From minutes to seconds
        daily_time = jsonDec.decode(daily_consumption.time_per_date)
        daily_time_min =  []
        for day_time in daily_time:
            daily_time_min.append(truediv(day_time, 60))        
    except DailyConsumption.DoesNotExist:
        days, daily_time_min = [], []
    """
    for daily_consumption in daily_consumptions:
        days.append(jsonDec.decode(daily_consumption.dates))
        daily_time.append(jsonDec.decode(daily_consumption.time_per_date))
    """
    return days, daily_time_min


# Get info for Video events dispersion within video length chart
# At what time the user did what along the video?
def get_video_events_info(username, video_id):
  
    if username == '#average':
        shortlist = Q(module_key = video_id)
    else:
        shortlist = Q(student=username, module_key = video_id)
    video_events = VideoEvents.objects.filter(shortlist)
    jsonDec = json.decoder.JSONDecoder()
    events_times = [[],[],[],[],[]]
    for user_video_events in video_events:
        events_times[0] += jsonDec.decode(user_video_events.play_events)
        events_times[1] += jsonDec.decode(user_video_events.pause_events)
        events_times[2] += jsonDec.decode(user_video_events.change_speed_events)
        events_times[3] += jsonDec.decode(user_video_events.seek_from_events)
        events_times[4] += jsonDec.decode(user_video_events.seek_to_events)
  
    if events_times != [[],[],[],[],[]]:
        scatter_array = video_events_to_scatter_chart(events_times)
    else:
        scatter_array = json.dumps(None)
    
    return scatter_array
    

# Get info for Repetitions per video intervals chart
# How many times which video intervals have been viewed?
def get_user_video_intervals(username, video_id):

    try:
        video_intervals = VideoIntervals.objects.get(student=username, module_key = video_id)
    except VideoIntervals.DoesNotExist:
        #print 'EXCEPTION'
        return json.dumps(None)
    
    jsonDec = json.decoder.JSONDecoder()
    hist_xaxis = jsonDec.decode(video_intervals.hist_xaxis)
    hist_yaxis = jsonDec.decode(video_intervals.hist_yaxis)
    num_gridlines = 0
    vticks = []
    
    # Interpolation to represent one-second-resolution intervals
    if sum(hist_yaxis) > 0:
        maxRepetitions = max(hist_yaxis)
        num_gridlines = maxRepetitions + 1 if maxRepetitions <= 3 else 5
        vticks = determine_repetitions_vticks(maxRepetitions)
        ordinates_1s = []
        abscissae_1s = list(range(0,hist_xaxis[-1]+1))
        #ordinates_1s.append([])
        for j in range(0,len(hist_xaxis)-1):
            while len(ordinates_1s) <= hist_xaxis[j+1]:
                ordinates_1s.append(hist_yaxis[j])
                
        # array to be used in the arrayToDataTable method of Google Charts
        # actually a list of lists where the first one represent column names and the rest the rows
        video_intervals_array = [['Time (s)', 'Times']]
        for abscissa_1s, ordinate_1s in zip(abscissae_1s, ordinates_1s):
            video_intervals_array.append([str(abscissa_1s), ordinate_1s])
    else:
        video_intervals_array = None
    interval_chart_data = {
        'video_intervals_array': video_intervals_array,
        'num_gridlines': num_gridlines,
        'vticks': vticks,
    }    
    
    return json.dumps(interval_chart_data)
