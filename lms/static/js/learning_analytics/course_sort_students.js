// Load the Visualization API and the piechart package.

google.load('visualization', '1.0', {'packages':['corechart']});

var LA_course_sort_students = (function(){
	//Colors
    var COLOR_NOT = document.getElementById('colorNOT').value;
    var COLOR_FAIL = document.getElementById('colorFAIL').value;
    var COLOR_OK = document.getElementById('colorOK').value;
    var COLOR_PROF = document.getElementById('colorPROF').value;

	var DEF_TITLE = "Grade categories";
	var expanded = false;
	var all_sections = null;
	var wss = null;
	var gs = null;
	var wss_array = null;
	var options = null;
	var chart = null;
	var data = null;
	
	// Callback that creates and populates a data table, 
	// instantiates the pie chart, passes in the data and
	// draws it.
	var drawChart = function() {

		if (data == null){
			// Parse JSON
			all_sections = JSON.parse(SORT_STD_DUMP.replace(/&quot;/ig,'"'));
			if(all_sections['weight_subsections'].length == 0){
			    var node = document.createTextNode("No data to display.");
			    var noData = document.createElement("p");
			    noData.appendChild(node);
			    document.getElementById('chart_course_sort_students').innerHTML = "";
			    document.getElementById('chart_course_sort_students').appendChild(noData);
			}else{
                wss = all_sections['weight_subsections'];
                gs = all_sections['graded_sections'];

                // Make data array
                wss_array = [['Category','Proficiency','Pass','Fail','Not Done'],];
                for(var i = 0; i < wss.length; i++){
                    var total = wss[i]['PROFICIENCY'] + wss[i]['OK'] + wss[i]['FAIL'] + wss[i]['NOT'];
                    wss_array.push([wss[i]['category'],
                        (wss[i]['PROFICIENCY']/total)*100,
                        (wss[i]['OK']/total)*100,
                        (wss[i]['FAIL']/total)*100,
                        (wss[i]['NOT']/total)*100]
                    );
                }

                // Data
                data = wss_array;
                // Options
                options = {
                    colors: [COLOR_PROF, COLOR_OK, COLOR_FAIL, COLOR_NOT],
                    legend: {position: 'none'},
                    isStacked: true,
                };

                document.getElementById('legend_title').innerHTML = DEF_TITLE;
	    	}
		}
		// Make DataTable
	    var dt = google.visualization.arrayToDataTable(data);

		// Format data as xxx%
		var formatter = new google.visualization.NumberFormat({suffix: '%', fractionDigits: 1});
		formatter.format(dt,1);
		formatter.format(dt,2);
		formatter.format(dt,3);
		formatter.format(dt,4);	
	
		// Draw chart
	    chart = new google.visualization.BarChart(window.document.getElementById('chart_course_sort_students'));
	    chart.draw(dt, options);
	  
	    // Event handlers
		google.visualization.events.addListener(chart, 'select', selectHandler);
		
		function selectHandler() {
			if (expanded){
				data = wss_array;
				drawChart();
				expanded = false;
				document.getElementById('legend_title').innerHTML = DEF_TITLE;
			}else {
				var selection = chart.getSelection();
				if (selection != null  && selection.length > 0){
					var row = selection[0].row;
					if (row != null){
						setRowData(row);
						drawChart();
						expanded = true;
					}
					
				}
			}
			
		}
	};

	var setRowData = function(row){
		var isTotal = row >= (wss.length - 1);
		if (isTotal){
			var category = 'All sections';
		}else{
			var category = wss[row]['category'];
		}
		cat_array = [[category,'Proficiency','Pass','Fail','Not Done'],];
		for(var i = 0; i < gs.length; i++){
			if (isTotal || gs[i]['category'] == category){
				var total = gs[i]['PROFICIENCY'] + gs[i]['OK'] + gs[i]['FAIL'] + gs[i]['NOT'];
				cat_array.push([gs[i]['label'],
					(gs[i]['PROFICIENCY']/total)*100,
					(gs[i]['OK']/total)*100,
					(gs[i]['FAIL']/total)*100,
					(gs[i]['NOT']/total)*100]
				);
			}
		}
		
		data = cat_array;
		document.getElementById('legend_title').innerHTML = category;
	};
	
	return{
		drawChart: drawChart,
	};
})();

// Set a callback to run when the Google Visualization API is loaded.
google.setOnLoadCallback(LA_course_sort_students.drawChart);
