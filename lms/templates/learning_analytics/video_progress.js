<%page args="video_prog_json"/>

// Graph for video percentage as well as total video time seen.

// Load the Visualization API and the chart package. Currently done on the HTML page.
//google.load('visualization', '1.0', {'packages':['corechart']});

// Set a callback to run when the Google Visualization API is loaded.
google.setOnLoadCallback(
  function() {
	localStorage['foo'] = JSON.stringify( ${video_prog_json} );
    drawChart1(${video_prog_json});
}
);

// Callback that creates and populates a data table,
// instantiates the chart, passes in the data and
// draws it.
function drawChart1(json_data) {

  var PROGRESS_NON_OVERLAPPED = document.getElementById('vidRepetition').value;
  var PROGRESS_OVERLAPPED = document.getElementById('vidActivity').value;
  // Instantiate and draw our chart, passing in some options.
  var chart = new google.visualization.BarChart(document.getElementById('video_prog_chart'));
  
  if (json_data != null && json_data.length > 0) {
    
    // Create the data table.
	var longitud= json_data.length;
	var json_data2=[];
	var datos = json_data[0];
	for (i=0;i<longitud;i++){
		json_data2[i]=json_data[i+1];
	}

	var json_limit= [];
    var cont=1;
    json_limit [0] = json_data[0];
    var cent=1;
    for (var i=1;i<json_data.length; i++) {
        if(cent<9){
            json_limit [cent] = json_data[i];
            cent=1+cent;
        }

    }

    var data = new google.visualization.arrayToDataTable(json_limit);
    var formatter = new google.visualization.NumberFormat(
  	      {suffix: '%', fractionDigits: 0});
    formatter.format(data, 1);
    formatter.format(data, 2);

    // Set chart options
    var options = {colors: [PROGRESS_NON_OVERLAPPED, PROGRESS_OVERLAPPED],
    		       legend: {position: 'none'},
    		       vAxis: {minValue: 0,
    		    	   	   maxValue: 100}
    
    };
    
    chart.draw(data, options);
    
  } else {   

    var node = document.createTextNode("No data to display.");
    var noData = document.createElement("p");
    noData.appendChild(node);
    document.getElementById('video_prog_chart').innerHTML = "";
    document.getElementById('video_prog_chart').appendChild(noData);
    
  }    

}