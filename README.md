This repository contains the Open edX platform release "hotfix-2016-03-17" with ANALYSE module.

Overview of ANALYSE
------------------

ANALYSE is learning analytics tool developed for Open edX. This is a beta release which extends the learning analytics functionality of Open edX with 12 new visualizations. A new tab has been addded in the course dashboard to access ANALYSE. Some of the features are the next:

<ul>
<li>The learning analytics dashboard has 3 visualizations related to exercises, 4 related to videos and 4 related to general course activity</li>
<li>The instructors of a course can access the information about the aggregate of all students in a course an also each student individually. That allows instructor to keep track about how the course is progressing and control each student separately</li>
<li>The students in a course can access their own information only which can be used for self-awareness and reflect on their learning process</li>
<li>The different indicators are processed in background in regular intervals of time as schedule jobs by the use of Celery Beat</li>
</ul>

<p>For more information you can visit <a href="http://www.it.uc3m.es/pedmume/ANALYSE/">ANALYSE</a> </p>

Improvements over the previous version
------------
- In this version, we have solved several bugs in the metrics, e.g. we have corrected the visualizations when the data are null and we have adapted the code to release Cypress and Dogwood.
- Now, the scalability of the module is improved, making a distinction between new events and already processed  events. The code is executed only when there are new  events, instead of taking into account all events (old and new). 
- In addition, we have improved scalability in different charts to avoid overlap of different values.
- We have used two palette with 6 primary colors, one for course activity and video activity and another for video events.


Installation
------------
For the installation of ANALYSE, you have two options:

<ul>
<li>Option 1: Use this full repository of Open edX which has the both the "hotfix-2016-03-17" release and ANALYSE module.</li>
<br />
<li>Option 2: Take ANALYSE code and insert it in a different Open edX release. The ANALYSE tool has been tested in the last two releases: Cypress and Dogwood. We have not tested it in other releases.</li>

<br />
The functionality of ANALYSE has been added as a new django application. If you want to add ANALYSE in Open edX in your Open edX release, you have to add different files and folders of this repository:
<ul>
<li>/lms/djangoapps/learning_analytics/*</li>
<li>/lms/static/js/learning_analytics/*</li>
<li>/lms/static/sass/course/learning_analytics/_learning_analytics.scss</li>
<li>/lms/templates/learning_analytics/*</li>
<li>/lms/envs/devstack_analytics.py</li>
</ul>
<br />
Moreover, you have to replace the files from Open edX that has been modified to introduce ANALYSE:
<ul>
<li>/setup.py</li>
<li>/lms/djangoapps/courseware/tabs.py</li>
<li>/common/lib/xmodule/xmodule/tabs.py</li>
<li>/lms/static/sass/_build-course.scss</li>
<li>/lms/urls.py</li>
<li>/common/djangoapps/track/backends/django.py</li>
</ul>
<br />
Finally, you have to modify a file of configurartion because edX doesn't actually use the MySQL tracking backend:
<ul>
<li> /edx/app/edxapp/lms.auth.json . You can use sudo nano /edx/app/edxapp/lms.auth.json and then add the next lines:<br />
<br />
<i>- "TRACKING_BACKENDS": { 
        "sql": { 
            "ENGINE": "track.backends.django.DjangoBackend" 
        } 
    }, </i>
    <br />
    <br />
    <i>
    - "EVENT_TRACKING_BACKENDS": { 
        "sql": { 
            "ENGINE": "track.backends.django.DjangoBackend" 
      } 
    },</i>
<br />
<br />
You can add this code between the lines ' <i>"CREDIT_PROVIDER_SECRET_KEYS": {}, </i>' and ' <i>"DATABASES": { </i>' . 
</li>
</ul>

<br />
In order for the high level indicators to be calculated, we will not be doing it in real time as it would mean a lot of processing and extremely high amounts of data managing, and it would slow down the platform. We compute them using the Celery Beat scheduler, which starts task at regular intervals. We will use this tool so as to calculate every indicator in the module every 30 seconds. Celery Beat needs to be activated and configured so that it run the task which updates the indicators in background.
</ul>
License
-------

The code in this repository is licensed under version 3 of the AGPL unless
otherwise noted. Please see the
[`LICENSE`](https://github.com/edx/edx-platform/blob/master/LICENSE) file
for details with. The next additional term should be also taken into account:
</br>
<ul style="text-align: justify">
<li>
Required to preserve the author attributions on the new added work for the development of ANALYSE
</li>
</ul>

Getting Help
------------

If you're having trouble with the installation or how to use ANALYSE feel free to <a href="mailto:jgascon@pa.uc3m.es">contact</a> and we will do our best to help you out.

Contributions are welcomed
-----------------

If you are interested in contributing to the development of ANALYSE we will be happy to help. For bug solving changes feel free to send a pull request. In case you would like to make a major change or to develop new functionality, please <a href="mailto:jgascon@pa.uc3m.es">contact</a> before starting your development, so that we can find the best way to make it work.


Developed by
--------------
<p> ANALYSE has been developed in the <a href="http://gradient.it.uc3m.es/">Gradient</a> lab, which is the e-learning laboratory inside the <a href="http://www.gast.it.uc3m.es/">GAST</a> group, as a part of the <a href="http://www.it.uc3m.es/vi/">Department of Telematic Engineering</a>, at the <a href="http://www.uc3m.es/">University Carlos III of Madrid</a> (Spain). The main people involved in the design and implementation of this tool have been the following: </p>
<ul style="text-align: justify" value="circle">
        <li>
        José Antonio Gascón Pinedo - Universidad Carlos III de Madrid - jgascon@pa.uc3m.es
        </li>
        <li>
        José Antonio Ruipérez Valiente - IMDEA Networks Institute and Universidad Carlos III de Madrid- jruipere@it.uc3m.es
        </li>
        <li>
        Pedro Jose Muñoz Merino - Universidad Carlos III de Madrid - pedmume@it.uc3m.es
        </li>
        <li>
        Héctor Javier Pijeira Díaz - Universidad Carlos III de Madrid (by implementing his Final Year Project)
        </li>
        <li>
        Javier Santofimia Ruiz - Universidad Carlos III de Madrid (by implementing his Final Year Project)
        </li>
        <li>
        Carlos Delgado Kloos - Universidad Carlos III de Madrid
        </li>
        </ul>
Acknowledgements. This work has been supported by:
<ul>
<li>
The "eMadrid" project (Regional Government of Madrid) under grant S2013/ICE-2715
</li>
 <li>
The RESET project (Ministry of Economy and Competiveness) under grant TIN2014-53199-C3-1-R
</li>
        </ul>
