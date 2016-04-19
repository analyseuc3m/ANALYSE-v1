// Load the Visualization API and the piechart package.
google.load('visualization', '1.0', {'packages':['corechart']});

var LA_chapter_time = (function(){
	var CHART_ID = 9;
	
	var ALL_STUDENTS = -1;
   	var PROF_GROUP = -2;
    var PASS_GROUP = -3;
    var FAIL_GROUP = -4;

    var colorgraded=document.getElementById('gradedTime').value;
    var colorungraded=document.getElementById('ungradedTime').value;
    var colorchapter=document.getElementById('chapterTime').value;
    var DEFAULT_COLORS = [colorgraded,colorungraded,colorchapter];

	var data = null;
	var options = null;
	var def_data = null;
	var time_json = null;
	var expanded = false;
	// Callback that creates and populates a data table, 
	// instantiates the pie chart, passes in the data and
	// draws it.
	var drawChart = function() {

		if(data == null){

			// Default data
			time_json = TIME_DUMP[getSelectedUser()];
			if (time_json == null){
				var node = document.createTextNode("No data to display.");
			    var noData = document.createElement("p");
			    noData.appendChild(node);
			    document.getElementById('chart_chapter_time').innerHTML = "";
			    document.getElementById('chart_chapter_time').appendChild(noData);
			}else{
				var time_array = [['Chapter','Graded time','Ungraded time','Chapter time'],];
				var empty = true;
				for(var i = 0; i < time_json.length; i++){
				    var graded = parseFloat((time_json[i]['graded_time']).toFixed(2));
	                var ungraded = parseFloat((time_json[i]['ungraded_time']).toFixed(2));
	                var chapt = parseFloat((time_json[i]['total_time'] - graded - ungraded).toFixed(2));

					time_array.push([time_json[i]['name'],graded, ungraded,chapt]);
					console.log('time_json');
	                console.log(time_json);
	                console.log(time_json[i]['total_time']);
					if(time_json[i]['total_time'] > 0){
						empty = false;
					}
				}
				def_data = google.visualization.arrayToDataTable(time_array);
				data = def_data;
				options = {
				    colors: DEFAULT_COLORS,
					legend: {position: 'none'},
					isStacked: true,
				};
				console.log('time_array');
                console.log(time_array);
				// Select callbacks
				setSelectCallback();

			}
		}
		
		var chart = new google.visualization.BarChart(document.getElementById('chart_chapter_time'));
		
	    var formatter = new google.visualization.NumberFormat(
	    	      {suffix: ' min', pattern:'#,###', fractionDigits: '2'});
	    formatter.format(data, 1);
		chart.draw(data, options);

	};


	var updateChart = function(event) {
		var sel_user = getSelectedUser();
		
		$.ajax({
			// the URL for the request
			url: "/courses/learning_analytics/chart_update",
			
			// the data to send (will be converted to a query string)
			data: {
				user_id   : sel_user,
				course_id : COURSE_ID,
				chart : CHART_ID
			},
			
			// whether to convert data to a query string or not
			// for non convertible data should be set to false to avoid errors
			processData: true,
			
			// whether this is a POST or GET request
			type: "GET",
			
			// the type of data we expect back
			dataType : "json",
			
			// code to run if the request succeeds;
			// the response is passed to the function
			success: function( json ) {
				TIME_DUMP = json;
				change_data();
			},
		
			// code to run if the request fails; the raw request and
			// status codes are passed to the function
			error: function( xhr, status, errorThrown ) {
				// TODO dejar selectores como estaban
				console.log( "Error: " + errorThrown );
				console.log( "Status: " + status );
				console.dir( xhr );
			},
		
			// code to run regardless of success or failure
			complete: function( xhr, status ) {
			}      
		});
	};
	
	var getSelectedUser = function(){
		if(SU_ACCESS){
			var selectOptions = document.getElementById('chapter_time_options');
			var selectStudent = document.getElementById('chapter_time_student');
			var selectGroup = document.getElementById('chapter_time_group');
			var selection = selectOptions.options[selectOptions.selectedIndex].value;
				
			switch(selection){
				case "all":
					selectStudent.style.display="none";
					selectGroup.style.display="none";
					return ALL_STUDENTS;
				case "student":
					selectStudent.style.display="";
					selectGroup.style.display="none";
					return selectStudent.options[selectStudent.selectedIndex].value;
				case "group":
					selectStudent.style.display="none";
					selectGroup.style.display="";
					switch(selectGroup.options[selectGroup.selectedIndex].value){
						case "prof":
							return PROF_GROUP;
						case "pass":
							return PASS_GROUP;
						case "fail":
							return FAIL_GROUP;
					}
			}		
		}else{
			return USER_ID;
		}

	};
	
	var setSelectCallback = function(){
		// Set selectors callbacks
		var selectOptions = document.getElementById('chapter_time_options');
		var selectStudent = document.getElementById('chapter_time_student');
		var selectGroup = document.getElementById('chapter_time_group');
			
		selectOptions.onchange = function(){
			var selection = selectOptions.options[selectOptions.selectedIndex].value;
			
			switch(selection){
				case "all":
					selectStudent.style.display="none";
					selectGroup.style.display="none";
					updateChart();
					break;
				case "student":
					selectStudent.style.display="";
					selectGroup.style.display="none";
					updateChart();
					break;
				case "group":
					selectStudent.style.display="none";
					selectGroup.style.display="";
					updateChart();
					break;
			}
			if(!SU_ACCESS){
				selectOptions.style.display="none";
				selectStudent.style.display="none";
				selectGroup.style.display="none";
			}
		};
		
		selectStudent.onchange = function(){
			updateChart();
		};
		
		selectGroup.onchange = function(){
			updateChart();
		};
	};
	
	var change_data = function(){
		data = null;
		options = null;
		def_data = null;
		def_names = [];
		time_json = null;
		expanded = false;
		data = null;
		LA_chapter_time.drawChart();
	};
	
	return {
		drawChart: drawChart,
	};
})();

// Set a callback to run when the Google Visualization API is loaded.
google.setOnLoadCallback(LA_chapter_time.drawChart);